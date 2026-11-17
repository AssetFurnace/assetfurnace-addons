# AssetFurnace add-ons list

The list of add-ons for [AssetFurnace](https://github.com/Bingeljell/image-to-3dlab). One file per add-on in
`addons/`. This repo is what the studio and the add-ons page read.

Add-ons run code on your machine. Read the labels.

| Label | What it means |
|-------|---------------|
| **Verified** | We read the code, ran it and checked its licences. Pinned to that exact version. A new version is checked again. |
| **Listed** | The author sent it in and it passed automatic checks: it installs, runs and makes a valid model. We did **not** read it. Use at your own risk. |
| **Unknown** | Not on this list. We have never looked at it. |

## Submit your add-on

1. **Build and test it.** Follow the [author guide](https://github.com/Bingeljell/image-to-3dlab/blob/main/docs/add-ons.md).
   Install it from your own repo with `./lab addon add --unreviewed <repo>@<commit>` and run it in the studio.
2. **Fork this repo** and add one file, `addons/<your-id>.json`. Copy `addons/pedestal.json` and change it:
   - `id`, `name`, `summary`: the same as in your `addon.json`.
   - `repo`: your public GitHub link. `commit`: the full 40-character version code.
   - `author`: your name and a link to your page.
   - `links`: at least `repo`. Optional: a page for your add-on.
3. **Open a pull request.** Checks run on their own and tell you in plain words what to fix.
4. **If the checks pass, it is merged and you are Listed.**
5. **Want Verified?** Say so in the pull request. We read the code and run it on test inputs. Free for now.

A new version of your add-on is a new pull request that changes `commit`. Nothing updates by itself.

## Rules

- Only the owner of an add-on, or a major contributor, may submit it.
- Pin a full commit. No branches, no tags.
- No code that updates itself or downloads more code after install.
- Say what it does on your machine: network use, shell commands, files it writes, models it downloads and their licences.
- Every model it uses needs its licence named in `addon.json`.
- No compiled binaries we cannot read.
- Don't impersonate AssetFurnace or another author.
- Only we set `"tier": "verified"`. If a pull request sets it, we change it to `listed`.
- If your repo or pinned commit disappears, or a problem is reported and goes unanswered, we can remove the entry.

Paid add-ons are a deal between you and the user. We only check that they work.

## Report a problem

Open an issue here with the add-on's name and what went wrong.

## Check an entry yourself

```
python scripts/check_entry.py addons/your-id.json
```
