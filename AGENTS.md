# Notes for agents

The AssetFurnace add-ons list. One file per add-on in `addons/`; `index.json` is built from them.

- Run the tests before every change: `python -m pytest -q`.
- Add a line to `CHANGELOG.md` under `[Unreleased]` for every change.
- One change per commit, Conventional Commits (`feat:`, `fix:`, `docs:`).
- Verified means we read the code, ran it and checked its licences. Never set it any other way.
