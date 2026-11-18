import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sandbox_exec as ex  # noqa: E402
import sandbox_plan as sp  # noqa: E402
import sandbox_verdict as sv  # noqa: E402

ENTRY = {"id": "cool", "repo": "https://github.com/ann/cool.git", "commit": "a" * 40}
TOOL = {"id": "build", "makes": "glb", "run": ["{blender}", "-b"], "inputs": [
    {"id": "height", "type": "number", "min": 0.1, "max": 2.0}, {"id": "steps", "type": "number", "min": 1, "max": 10},
    {"id": "style", "type": "choice", "choices": ["round", "square"]}, {"id": "name", "type": "text"}, {"id": "shiny", "type": "toggle"}]}
MANIFEST = {"id": "cool", "needs": {"blender": ">=4.2"}, "models": [], "tools": [TOOL]}


def glb(triangles=12, version=2, length_off=0):
    gltf = {"asset": {"version": "2.0"}, "accessors": [{"count": triangles * 3}], "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 0}]}]}
    body = json.dumps(gltf).encode()
    body += b" " * (-len(body) % 4)
    total = 12 + 8 + len(body)
    return b"glTF" + struct.pack("<II", version, total + length_off) + struct.pack("<II", len(body), 0x4E4F534A) + body


# ---- plan

def test_inputs_get_plain_test_values():
    plan = sp.make_plan(ENTRY, MANIFEST)
    assert plan["runnable"] and plan["blender"] == "4.2"
    assert plan["runs"] == [{"tool": "build", "inputs": {"height": "1.05", "steps": "5", "style": "round", "name": "test", "shiny": "false"}}]


def test_models_files_newer_blender_and_other_outputs_are_not_runnable():
    assert "models" in sp.make_plan(ENTRY, {**MANIFEST, "models": [{"id": "m"}]})["reason"]
    picture = {**TOOL, "inputs": [{"id": "p", "type": "picture"}]}
    assert "file as input" in sp.make_plan(ENTRY, {**MANIFEST, "tools": [picture]})["reason"]
    assert sp.make_plan(ENTRY, {**MANIFEST, "tools": [{**picture, "inputs": [{"id": "p", "type": "picture", "optional": True}]}]})["runnable"]
    assert "newer Blender" in sp.make_plan(ENTRY, {**MANIFEST, "needs": {"blender": ">=5.0"}})["reason"]
    assert ".fbx" in sp.make_plan(ENTRY, {**MANIFEST, "tools": [{**TOOL, "makes": "fbx"}]})["reason"]
    assert not sp.make_plan(ENTRY, {**MANIFEST, "tools": []})["runnable"]


def test_no_blender_needed_means_none_is_installed():
    plain = {**TOOL, "run": ["python3", "make.py"]}
    assert sp.make_plan(ENTRY, {"models": [], "tools": [plain]})["blender"] is None


# ---- the model check

def test_a_real_model_passes_and_broken_ones_do_not():
    assert sv.check_glb(glb()) == []
    assert sv.check_glb(b"not a model at all, just text") != []
    assert "empty" in sv.check_glb(glb(triangles=0))[0]
    assert "header" in sv.check_glb(glb(version=1))[0]
    assert "header" in sv.check_glb(glb(length_off=4))[0]
    assert "MB" in sv.check_glb(glb() + b"0" * sv.GLB_MAX_BYTES)[0]


# ---- the sandbox's own claims are read strictly

def test_run_json_keeps_only_expected_fields(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"install_exit": 0, "evil": "x", "runs": [{"tool": "build", "exit": 0, "files": ["run0-0.glb", "../../etc/passwd", "x.txt"], "extra": 1}]}))
    assert sv.read_run(tmp_path / "run.json") == {"install_exit": 0, "runs": [{"tool": "build", "exit": 0, "files": ["run0-0.glb"]}]}
    for bad in ('{"install_exit": "0", "runs": []}', '{"runs": []}', "[]", "nope"):
        (tmp_path / "run.json").write_text(bad)
        assert sv.read_run(tmp_path / "run.json") is None
    assert sv.read_run(tmp_path / "missing.json") is None


# ---- the verdict

PLAN = sp.make_plan(ENTRY, MANIFEST)


def result(tmp_path, install=0, exit_=0, files=("run0-0.glb",), data=None):
    (tmp_path / "run.json").write_text(json.dumps({"install_exit": install, "runs": [{"tool": "build", "exit": exit_, "files": list(files)}]}))
    for f in files:
        (tmp_path / f).write_bytes(glb() if data is None else data)
    return tmp_path


def test_a_clean_run_passes(tmp_path):
    assert sv.judge(PLAN, result(tmp_path))["status"] == "passed"


def test_each_way_to_fail_says_why(tmp_path):
    cases = {
        "install": (dict(install=1), "install"),
        "exit": (dict(exit_=1), "failed"),
        "nofile": (dict(files=()), "no .glb"),
        "liar": (dict(data=b"liar liar"), "not a real"),
    }
    for name, (kw, word) in cases.items():
        folder = tmp_path / name
        folder.mkdir()
        v = sv.judge(PLAN, result(folder, **kw))
        assert v["status"] == "failed" and word in v["problems"][0], name
    silent = tmp_path / "silent"
    silent.mkdir()
    assert sv.judge(PLAN, silent)["status"] == "failed"


def test_a_symlinked_model_is_refused(tmp_path):
    result(tmp_path)
    (tmp_path / "run0-0.glb").unlink()
    (tmp_path / "elsewhere.glb").write_bytes(glb())
    (tmp_path / "run0-0.glb").symlink_to(tmp_path / "elsewhere.glb")
    assert sv.judge(PLAN, tmp_path)["status"] == "failed"


def test_an_untestable_add_on_is_not_run_not_failed(tmp_path):
    v = sv.judge(sp.make_plan(ENTRY, {**MANIFEST, "models": [{"id": "m"}]}), tmp_path)
    assert v["status"] == "not_run" and "models" in v["reason"]


def test_the_sandbox_cannot_skip_a_tool(tmp_path):
    two = {**PLAN, "runs": PLAN["runs"] + [{"tool": "other", "inputs": {}}]}
    assert "not every tool" in sv.judge(two, result(tmp_path))["problems"][0]


# ---- the machine-side runner (with a fake add-on command)

def test_exec_installs_runs_and_collects_models(tmp_path):
    calls = []

    class Done:
        def __init__(self, code=0): self.returncode, self.stdout, self.stderr = code, b"ok", b""

    def runner(argv, env, **kw):
        calls.append(argv)
        if "run" in argv:
            d = Path(env["OUTPUT_DIR"]) / "cool"
            d.mkdir(parents=True, exist_ok=True)
            (d / "r.glb").write_bytes(glb())
        return Done()

    out = tmp_path / "out"
    out.mkdir()
    res = ex.execute(PLAN, Path("/lab"), out, runner=runner)
    assert res["install_exit"] == 0 and res["runs"][0]["files"] == ["run0-0.glb"]
    assert "--unlisted" in calls[0] and f"{ENTRY['repo']}@{ENTRY['commit']}" in calls[0]
    assert "height=1.05" in calls[1]
    assert (out / "run0-0.glb").is_file() and not (out / "work").exists()
    (out / "run.json").write_text(json.dumps(res))
    assert sv.judge(PLAN, out)["status"] == "passed"


def test_exec_stops_when_install_fails(tmp_path):
    class Done:
        returncode, stdout, stderr = 1, b"boom", b""
    out = tmp_path / "out"
    out.mkdir()
    res = ex.execute(PLAN, Path("/lab"), out, runner=lambda *a, **k: Done())
    assert res["install_exit"] == 1 and res["runs"] == []


# ---- recording the result

import sandbox_record as sr  # noqa: E402
import check_entry as ce  # noqa: E402


def test_only_passed_and_not_run_are_recorded_and_a_forged_record_is_replaced():
    forged = {**ENTRY, "run_check": {"status": "passed", "date": "1999-01-01"}}
    assert sr.record(forged, {"status": "not_run", "reason": "it downloads models"}, "2026-11-18")["run_check"] == {"status": "not_run", "date": "2026-11-18", "reason": "it downloads models"}
    assert sr.record(ENTRY, {"status": "passed"}, "2026-11-18")["run_check"] == {"status": "passed", "date": "2026-11-18"}
    try:
        sr.record(ENTRY, {"status": "failed"}, "2026-11-18")
        raise AssertionError("a failure must never be recorded")
    except ValueError:
        pass


def test_the_entry_checker_knows_run_check():
    good = {**ENTRY, "name": "Cool", "author": {"name": "A"}, "summary": "s"}
    assert ce.check_entry(Path("addons/cool.json"), {**good, "run_check": {"status": "passed"}}) == []
    assert any("run_check" in p for p in ce.check_entry(Path("addons/cool.json"), {**good, "run_check": {"status": "great"}}))


def test_the_workflow_installs_the_blender_version_the_plan_assumes():
    text = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "sandbox.yml").read_text()
    assert f"Blender{sp.BLENDER}/" in text and f"blender-{sp.BLENDER}." in text
