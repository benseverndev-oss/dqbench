---
layout: default
title: Leaderboard
nav_order: 6
---

# DQBench Leaderboard

The published leaderboard ([`LEADERBOARD.md`](../LEADERBOARD.md)) ranks data quality
tools across all five categories. Results are committed to the repository under
`leaderboard/results/<category>.json` and the Markdown board is regenerated from them.

Anyone can add their tool's results by opening a pull request.

## How scoring works

Each entry carries the tier-weighted composite **score** (0-100) for one category plus
the per-tier metric (issue F1 for Detect, accuracy for Transform, pair F1 for ER,
composite for Pipeline and OCR Company). Entries are ranked by score, descending.

## Submitting a run

1. **Benchmark your tool** and capture the JSON output:

   ```bash
   dqbench run mytool --adapter path/to/my_adapter.py --json > run.json
   ```

   (Any built-in adapter works too, e.g. `dqbench run pandera-best --json > run.json`.)

2. **Add it to the published store.** From the repository root:

   ```bash
   dqbench submit run.json \
     --submitter "Your Name or Org" \
     --adapter-ref "mypackage.adapters:MyToolAdapter" \
     --result-source reproduced
   ```

   This validates the run, writes it into `leaderboard/results/<category>.json`
   (one entry per `tool@version`), and regenerates `LEADERBOARD.md`.

3. **Open a pull request** with the changed files in `leaderboard/results/` and
   `LEADERBOARD.md`. CI runs `dqbench publish --check` to validate every entry and
   confirm the Markdown board is in sync.

## Result sources

| `--result-source` | Meaning |
|-------------------|---------|
| `reproduced`      | Run on the standard DQBench datasets by the submitter (default). |
| `vendor-reported` | Numbers reported by the tool's vendor; not independently reproduced. |
| `third-party`     | Reproduced by someone other than the tool's authors. |

## Submission fields

Each entry in `leaderboard/results/<category>.json` looks like:

```json
{
  "category": "detect",
  "tool": "Pandera (best-effort)",
  "tool_version": "0.31.1",
  "score": 32.51,
  "tier_scores": { "1": 0.3636, "2": 0.381, "3": 0.25 },
  "submitter": "DQBench maintainers",
  "date": "2026-05-24",
  "adapter": "dqbench.adapters.pandera_adapter:PanderaBestEffortAdapter",
  "dqbench_version": "1.0.0",
  "source": "reproduced",
  "notes": ""
}
```

Validation rules (enforced by `dqbench publish --check`):

- `category` is one of `detect`, `transform`, `er`, `pipeline`, `ocr-company`.
- `tool` and `submitter` are non-empty.
- `score` is a number in `[0, 100]`.
- `tier_scores` is non-empty and every value is in `[0, 1]`.
- `source` is one of `reproduced`, `vendor-reported`, `third-party`.

## Regenerating the board locally

```bash
dqbench publish            # rewrite LEADERBOARD.md from the store
dqbench publish --check    # CI mode: validate + verify the board is current
dqbench leaderboard --source repo   # view the published board in the console
```
