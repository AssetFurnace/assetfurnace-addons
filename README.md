# AssetFurnace add-ons list

The list of add-ons for [AssetFurnace](https://github.com/Bingeljell/image-to-3dlab). One file per add-on in
`addons/`. This repo is what the studio and the add-ons page read.

Add-ons run code on your machine. Read the labels.

| Label | What it means |
|-------|---------------|
| **Verified** | We read the code, ran it and checked its licences. Pinned to that exact version. A new version is checked again. |
| **Listed** | The author sent it in and it passed automatic checks: its entry and its `addon.json` at that exact version passed our automatic checks, and we test-ran it on a clean machine and it made a real model. We did **not** read the code. If we could not test-run it (it downloads models, or every tool needs a file as input), it says **not run-checked**. If only some tools could be run, it says **partly run-checked** and names the ones that were not. Use at your own risk. |
| **Unknown** | Not on this list. We have never looked at it. |

## Submit your add-on

Submit at **[assetfurnace.com/add-ons/submit](https://assetfurnace.com/add-ons/submit)**. Sign in with GitHub, send your
repo link, the full 40-character version code and a picture (PNG or JPG, under 600 KB). Our bot opens the pull request
here for you, taking your name and profile link from your GitHub account. Pull requests opened by anyone else are
closed automatically.

1. **Build and test it.** Follow the [author guide](https://github.com/Bingeljell/image-to-3dlab/blob/main/docs/add-ons.md).
   Install it from your own repo with `./lab addon add --unlisted <repo>@<commit>` and run it in the studio.
2. **Send it** on the page above. The name, summary, licence and `runs` come from your `addon.json` at that version.
3. **Checks run on their own,** then your add-on is installed and run on a throwaway machine with plain test values. If it all passes, it is merged and you are Listed. If not, the pull request says what to fix.
4. **Want Verified?** Tick the box on the page. We read the code and run it on test inputs; until then it stays Listed.

A new version of your add-on is a new submission. Nothing updates by itself. A new version of a Verified add-on is not
merged until we have read it, and users keep the version we checked.

## Rules

- Only the owner of the repo, or a public member of its organisation, may submit it. The first person to use an id keeps it.
- Pin a full commit. No branches, no tags.
- No code that updates itself or downloads more code after install.
- Say what it does: network use (including sending models off the user's machine), shell commands, files it writes, models it downloads and their licences.
- Every model it uses needs its licence named in `addon.json`.
- No compiled binaries we cannot read.
- Don't impersonate AssetFurnace or another author.
- Only we set `"tier": "verified"`. A submission that sets it waits for a person.
- If your repo or pinned commit disappears, or a problem is reported and goes unanswered, we can remove the entry.

Paid add-ons are a deal between you and the user. We only check that they work.

## Report a problem

Open an issue here with the add-on's name and what went wrong.

## Check an entry yourself

```
python scripts/check_entry.py addons/your-id.json
```

## How the test run works

A fresh machine is started for each submission and deleted afterwards. It has no passwords or access to anything of
ours. Your add-on is installed with the studio's own `addon add` command and each tool is run once with plain test
values (the middle of a number's range, the first choice, `test` for text). The model it makes is then checked on a
separate machine: it must be a real `.glb` with something in it. A tool that needs a picture or model file as input
cannot be given one, so it is left out of the run and named in the result (a **partial** test run); the add-on's other
tools are still tested.
Add-ons that download models, need a newer Blender than the test machine's, make something other than `.glb`, or have
no tool that can be run without a file cannot be run this way, so they are listed as **not run-checked**.
