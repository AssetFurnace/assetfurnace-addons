import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import find_dead as fd  # noqa: E402


def entry(i, repo="https://github.com/ann/x.git"):
    return {"id": i, "repo": repo, "commit": "a" * 40}


def run(entries, answers):
    calls = []

    def status(url):
        calls.append(url)
        a = answers[len(calls) - 1] if len(calls) <= len(answers) else answers[-1]
        return a
    return fd.find_dead(entries, status=status, sleep=lambda s: None), calls


def test_a_clear_not_found_twice_is_dead():
    dead, calls = run([entry("a")], [404, 404])
    assert [d["id"] for d in dead] == ["a"] and len(calls) == 2


def test_found_is_alive():
    assert run([entry("a")], [200])[0] == []


def test_a_busy_or_unreachable_server_is_never_dead():
    for answer in (500, 503, 403, 429, None):
        assert run([entry("a")], [answer])[0] == []


def test_one_not_found_then_found_is_alive():
    assert run([entry("a")], [404, 200])[0] == []


def test_non_github_repos_are_skipped():
    dead, calls = run([entry("a", repo="https://gitlab.com/ann/x.git")], [404])
    assert dead == [] and calls == []


def test_report_names_each_dead_entry_in_plain_words():
    text = fd.report([{"id": "a", "repo": "https://github.com/ann/x.git", "commit": "b" * 40, "reason": "gone"}])
    assert "**a**" in text and "bbbbbbb" in text and "a person decides" in text
