# Cargo Loading Optimizer

Decides which packages to load onto a truck (or a fleet of trucks) with Google OR-Tools CP-SAT: maximise value
within capacity, while respecting business rules such as must-include packages, priorities, incompatible pairs,
dependencies and category limits. Every Part of the practice brief is an experiment defined in one YAML file.

## The model

| | |
|---|---|
| Decision variables | `x_i ∈ {0, 1}`: package *i* is loaded; with several trucks also `y_it`: package *i* rides on truck *t* |
| Capacity (hard) | `Σ w_i · x_i ≤ C` per truck |
| Must-include | hard: `x_i = 1` for every `should_included` package; soft: penalty per package left behind |
| Incompatible pair (hard) | `x_a + x_b ≤ 1` |
| Dependency (hard) | `x_a ≤ x_b` (loading *a* requires *b*) |
| Category rules | at least / at most *n* packages of a category; hard, or soft with a penalty per violating package |
| Objective | `max Σ (value_weight · v_i + priority_weight · p_i) · x_i − Σ penalties`, priority points Critical 3, High 2, Normal 1, Low 0 |

A greedy baseline (best score per kg first) runs on the same configs where it can; it skips configs with rules it
cannot honour and records why. For an infeasible model the runner reports a minimal set of conflicting hard rules.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync                      # creates .venv and installs ortools, pyyaml and pytest from uv.lock
```

In PyCharm: set the interpreter to `.venv/bin/python` and mark `src` as Sources Root.

## Running experiments

```bash
uv run python -m cargo_optimizer.run_experiment part1                     # one experiment
uv run python -m cargo_optimizer.run_experiment "part3_*"                 # a group, by pattern
uv run python -m cargo_optimizer.run_experiment "part4_*" --dataset example
uv run python -m cargo_optimizer.run_experiment "part6_weights*" --quiet  # summary table only
uv run python -m cargo_optimizer.run_experiment --quiet                   # everything (256 runs, several minutes)
```

| Experiments | Brief |
|---|---|
| `part1`, `part1_greedy` | Part 1: maximise value within capacity |
| `part2`, `part2_greedy`, `part2_3_*` | Part 2: must-include as a hard rule (infeasible on the full data) |
| `part3_w*` | Part 3: priority weight 0 / 50 / 150 / 500 / 2000 |
| `part4_*` | Part 4: incompatible pair, dependency, Furniture ≤ 3 (hard), Medical ≥ 2 (soft) |
| `part5_A_*` … `part5_D_*` | Part 5: infeasible scenarios and their relaxations (C and D: `--dataset example`) |
| `part6_*` | Part 6: objective weights and penalties (sweeps) |
| `part8_*` | Part 8: scaling (`--dataset random_<size>`), workers, time limit, presolve, trucks, gap limit |
| `all_cases*` | Every combination of Parts 2–4 settings |

Each run prints its rules, status, totals and model size, and writes:

- `results/<time>_<dataset>_<experiment>/config.yaml`: the exact settings used
- `results/<time>_<dataset>_<experiment>/result.json`: status, selected packages, totals, gap, conflicts
- `results/summary_<time>_<dataset>.csv`: one row per run of that invocation

`results/` is not committed: the important results are kept as tables in the project's design log, and re-running
an experiment recreates its raw results exactly (fixed seeds; runs that hit a time limit can vary slightly).

## Datasets

| Name | File | Notes |
|---|---|---|
| `full` (default) | `data/packages.csv` | the 1,000-package dataset |
| `example` | `data/example_packages.csv` | the brief's 10 packages |
| `random_1000` … `random_100000` | `data/random_<size>.csv` | generated, not committed: `uv run python scripts/generate_dataset.py --size 10000` |

Rule package IDs (incompatible pairs, dependencies) are set per dataset in `configs/experiments.yaml`.

## Configuring experiments

`configs/experiments.yaml` has four sections:

```yaml
datasets:                    # file + the package IDs its rules refer to
  example:
    path: data/example_packages.csv
    incompatible_pairs: [[P02, P06]]
    dependencies: [[P07, P03]]

defaults:                    # every setting, once
  method: cpsat              # cpsat | greedy
  capacity: 1000             # kg per truck, or a share of total weight such as "25%"
  should_include: ignore     # ignore | hard | soft
  category_rules: []
  # ... see the file for all settings

experiments:                 # each overrides only what differs from the defaults
  part4_all_rules_p150:
    incompatible: true
    dependency: true
    category_rules:
      - {category: Furniture, at_most: 3}                # hard: no penalty
      - {category: Medical, at_least: 2, penalty: 150}   # soft: penalty per missing package

sweeps:                      # every combination of the listed values, for each base experiment
  part6_weights:
    base: [part6_base]
    value_weight: [0, 1, 10]
    should_include_penalty: [0, 100, 500, 2000]
```

| Setting | Meaning | Default |
|---|---|---|
| `method` | `cpsat` or `greedy` | `cpsat` |
| `capacity` | kg per truck, or `"N%"` of the dataset's total weight | `1000` |
| `trucks` | number of trucks; each package rides on at most one | `1` |
| `should_include` / `should_include_penalty` | ignore, hard, or soft with this cost per required package left behind | `ignore` / `0` |
| `value_weight` / `priority_weight` | objective weights of value and priority points | `1` / `0` |
| `incompatible` / `dependency` | apply the dataset's incompatible pairs / dependencies | `false` |
| `category_rules` | list of `{category, at_least \| at_most, penalty?}` | `[]` |
| `num_workers`, `time_limit_seconds`, `random_seed` | CP-SAT search settings | `8`, `60`, `0` |
| `relative_gap_limit` | stop once proven within this share of the best (0.01 = 1%) | `0` |
| `presolve` | CP-SAT preprocessing; switching it off was much faster on large models | `true` |
| `symmetry_breaking` | with several trucks, order trucks by load | `false` |

Unknown or missing settings, unknown categories and invalid values are rejected with a clear message.

## Tests

```bash
uv run pytest
```

Each Part has checks on small hand-computed examples (e.g. the optimum is B + D = 40 where greedy gets 30).

## Project structure

```text
configs/experiments.yaml     datasets, defaults, experiments, sweeps
data/                        package datasets
scripts/generate_dataset.py  random datasets for scaling
src/cargo_optimizer/
    data.py                  load and validate package CSVs
    config.py                load experiments.yaml into validated dataclasses
    model.py                 CP-SAT model: variables, constraints, objective
    diagnose.py              conflicting hard rules of an infeasible model
    greedy.py                greedy baseline
    run_experiment.py        run experiments, print and save results
tests/                       pytest checks per Part
```
