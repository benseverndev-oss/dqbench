---
layout: default
title: Leaderboard
nav_order: 6
---

# DQBench Leaderboard

The published leaderboard ([`LEADERBOARD.md`](../LEADERBOARD.md)) ranks data quality
tools across all five categories. Results are committed to the repository under
`leaderboard/results/<category>.json` and the Markdown board is regenerated from them.

## Acceptance policy: results must reproduce

**A result is only accepted if a GitHub Action can reproduce it.** Every entry on the
board is backed by a *manifest* — a small JSON file under `leaderboard/submissions/`
that declares exactly how to run the benchmark (tool, category, adapter, pinned
packages). When you open a pull request, CI re-runs each changed manifest on a clean
runner and rejects the entry if the committed numbers don't match what it reproduces.

This means you cannot hand-edit a score onto the board — the number has to come from a
reproducible run of the actual tool on the standard datasets.

The board is seeded with the Golden suite reference tools — **GoldenCheck** (Detect),
**GoldenFlow** (Transform), **GoldenMatch** (ER), **GoldenPipe** (Pipeline) — plus
Pandera and Soda baselines for Detect. **OCR Company** is open: there's no installable
third-party tool yet, so the first reproducible submission seeds it.

## How scoring works

Each entry carries the tier-weighted composite **score** (0-100) for one category plus
the per-tier metric (issue F1 for Detect, accuracy for Transform, pair F1 for ER,
composite for Pipeline and OCR Company). Entries are ranked by score, descending.

## Submitting a tool

1. **Write a manifest** at `leaderboard/submissions/<id>.json`:

   ```json
   {
     "id": "detect-mytool",
     "category": "detect",
     "tool": "MyTool (best-effort)",
     "adapter": "mypackage.adapters:MyToolAdapter",
     "install": ["mytool==1.2.3"],
     "submitter": "Your Name or Org",
     "source": "reproduced",
     "notes": "Optional: config, caveats."
   }
   ```

   - `adapter` is a built-in adapter name (e.g. `pandera-best`), a `module:Class`
     reference to an installed adapter, or use `adapter_file` to point at an adapter
     `.py` file you include in the PR.
   - `tool` **must** equal the adapter's reported name (it is checked on reproduction).
   - **Pin your versions** in `install` so the run is deterministic — CI installs
     exactly these packages before reproducing.

2. **Reproduce locally and record the result:**

   ```bash
   dqbench reproduce leaderboard/submissions/detect-mytool.json --write
   ```

   This runs the benchmark, writes the entry into `leaderboard/results/detect.json`,
   and regenerates `LEADERBOARD.md`. Confirm it reproduces:

   ```bash
   dqbench verify leaderboard/submissions/detect-mytool.json
   ```

3. **Open a pull request** with the manifest, `leaderboard/results/*.json`, and
   `LEADERBOARD.md`. CI runs two gates:
   - `dqbench publish --check` — every entry has a manifest and the board is in sync.
   - `dqbench verify` on each changed manifest — the numbers actually reproduce.

## Determinism

DQBench datasets are deterministic (`random.Random(42)`), so a tool that is itself
deterministic produces identical numbers on every run. Tools whose runs vary between
invocations (e.g. sampling-based profilers) cannot be accepted until their adapter is
made deterministic — the reproducibility gate will reject them. CI reproduces runs on
**Python 3.11**; pin your `install` versions so numbers don't drift.

## Result sources

| `--result-source` / `source` | Meaning |
|-------------------------------|---------|
| `reproduced`      | Run on the standard DQBench datasets (default). |
| `vendor-reported` | Reported by the tool's vendor; still must pass the gate to be listed. |
| `third-party`     | Reproduced by someone other than the tool's authors. |

## Commands

```bash
dqbench reproduce <manifest>            # run the manifest, print the run JSON
dqbench reproduce <manifest> --write    # run + record into the store + republish
dqbench verify <manifest>               # reproduce and confirm the committed entry matches
dqbench publish                         # rewrite LEADERBOARD.md from the store
dqbench publish --check                 # CI: validate store + manifests + board freshness
dqbench leaderboard --source repo       # view the published board in the console
```
