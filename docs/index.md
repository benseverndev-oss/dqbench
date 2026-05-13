---
layout: default
title: Home
nav_order: 1
---

# DQBench

The standard benchmark for data quality and validation tools.

The ImageNet of data quality — standardized benchmarks across five categories (Detect, Transform, ER, Pipeline, OCR Company), tiered by difficulty, with ground truth for every planted issue, fair scoring on recall and precision, and a single DQBench Score (0-100) for easy comparison.

## Install

```bash
pip install dqbench
```

## Quick Start

```bash
# Detect benchmark
dqbench run goldencheck

# ER benchmark (T1-T3 scored, T4 Mistyped reported as diagnostic)
dqbench run goldenmatch

# Pipeline benchmark
dqbench run goldenpipe

# Run with your own tool — implement one adapter class
dqbench run --adapter path/to/my_adapter.py
```

Integrate any tool in about 20 lines of code.

## Categories

| Category | Tiers | What it measures |
|----------|-------|------------------|
| Detect | 3 | Find data quality issues in a dataset |
| Transform | 3 | Clean, normalize, and repair data |
| ER | 3 scored + T4 diagnostic | Deduplicate and link records |
| Pipeline | 3 | End-to-end pipeline orchestration and quality gates |
| OCR Company | 3 | Post-OCR company-name confidence and correction quality |

**ER T4 — Mistyped** is a diagnostic tier (since DQBench v1.2) where four column names deliberately disagree with their content. It exposes dedupers that fire per-column refinements (name scorers, address normalisation) on noise when the column name doesn't match the data. Reported alongside T1-T3 but excluded from the composite ER score so it doesn't move headline numbers for tools that don't opt in.

## Links

- [GitHub Repository](https://github.com/benzsevern/dqbench)
- [PyPI Package](https://pypi.org/project/dqbench/)
- [Changelog](https://github.com/benzsevern/dqbench/blob/main/CHANGELOG.md)
- [Contributing](https://github.com/benzsevern/dqbench/blob/main/CONTRIBUTING.md)
