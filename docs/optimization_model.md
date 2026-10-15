# Optimization model

The model is written as a standard formulation: sets, parameters, decision variables, then objective and constraints. Later Parts extend it here.

## Findings so far (Parts 1–8, updated 2026-10-15)

The same model and rules behave very differently on the two datasets: on the full data most rules never bind and must-include is infeasible; on the brief's example must-include is affordable and priority visibly reshapes the load.

| Experiment | Full dataset (1,000 packages) | Example (10 packages) |
| --- | --- | --- |
| Part 1 (value only) | OPTIMAL, 19,270; 34 packages, all Medical | OPTIMAL, 3,750 |
| Greedy, Part 1 | 19,257 (0.07% below optimum) | 3,650 (2.7% below optimum) |
| Part 2 (must-include hard) | INFEASIBLE: 19,332 kg forced vs 1,000 kg | OPTIMAL, 3,650: must-include costs 100 (2.7%) |
| Part 3 (priority, w = 0→2,000) | Critical 4→18, value lost up to 44%; diminishing beyond w = 500 | w = 50 keeps 3,750 with more priority points; w ≥ 150 gives 3,500 (−6.7%) and stops changing |
| Part 2 + 3 | INFEASIBLE at every weight | w ≥ 150: identical to Part 3 — priority already loads every must-include package |
| Part 4 hard rules | Never bind (19,270) | Never bind (3,750) |
| Part 4 soft Medical ≥ 2 | Already met (shortfall 0 at every penalty) | Already met (P03, P09) |

Conclusions:

1. Feasibility comes only from constraints; weights and penalties only choose among feasible solutions.
2. A rule matters only if it binds. Most Part 4 rules are already satisfied by the value-optimal load, so they change nothing alone; their effect appears in combination (Part 5).
3. Hard rules have a price: the value given up to satisfy them (example must-include: 100) — or no solution at all (full data).
4. Priority weights are a business trade-off with diminishing returns; each weight has a plain meaning in value terms.
5. Different selections can have equal value (several optima), so compare objective values, not package lists.
6. Greedy is a strong baseline on the full data (≤ 0.3% gap) but weaker on small instances (2.7% on the example); CP-SAT also proves optimality.
7. Every model here solves in milliseconds; size and solver settings are left for Part 8.

Parts 5 and 6 add:

| Experiment | Full dataset | Example |
| --- | --- | --- |
| Part 5 infeasibility | A: capacity + must\_include; B: must\_include + Furniture at\_most 3 — found automatically; fixed by a bigger truck, 20 trucks, a raised limit or soft rules | C: capacity + must\_include; D: Medical at\_least 3 impossible on its own (only 2 Medical exist) |
| Part 6 weights | Should-include weight raises coverage 11 → 41 (the most that fit) at up to 42% of value; weights ×10 change nothing | Coverage 5 / 5 once the weight beats the 100 it costs |
| Part 6 soft category | Furniture penalty vs should-include weight decides whether required Furniture rides (25,000 kg) | Medical preference flips at its break-even penalty: 150 (200 kg), 300 (250 kg) |

8. Every infeasibility has a business fix with a different cost: more capacity (trucks), a changed limit, or a requirement turned into a priced preference — the owner chooses.
9. A soft rule only matters under pressure; its break-even penalty equals the value given up to satisfy it.
10. Weights express business value, not truth: only their ratios matter, and an objective that values nothing returns an empty truck.
11. Identical trucks create symmetry: 20 trucks solve in 38 s, 21 do not finish in 60 s — a performance issue for Part 8.

Part 8 adds (random datasets 1k–100k, trucks on the full data):

12. Difficulty depends on the capacity, not just the number of variables: 100,000 packages solve in 2.8 s with a 1,000 kg truck but not in 60 s with a scaled truck.
13. On large single-truck models the time is single-threaded presolve, so workers do not help; presolve off solved every large case in under 4 s.
14. With many identical trucks, symmetry breaking helped at 20–21 trucks and hurt at 25: measure, do not assume.
15. Status must be read with the gap: a 1% gap limit gives "OPTIMAL within 1%" in 1 s instead of FEASIBLE after 60 s.

### All-combinations sweep (2026-10-14)

100 runs per dataset (5 bases × should\_include 2 × priority\_weight 5 × method 2): only should\_include and priority\_weight change the outcome; the Part 4 rules and the Medical penalty never change any result.

- Bases: part1 and part4\_all\_rules with Medical penalty 0 / 50 / 150 / 500; summaries in results/summary\_\<time>\_\<dataset>.csv.

| Dataset | OPTIMAL | FEASIBLE (greedy) | INFEASIBLE | SKIPPED (greedy) |
| --- | --- | --- | --- | --- |
| full | 25 | 5 | 25 (every must-include hard run) | 45 |
| example | 50 | 5 | 0 | 45 |

Total value with CP-SAT, identical for all 5 bases:

| Dataset, should\_include | w = 0 | 50 | 150 | 500 | 2,000 |
| --- | --- | --- | --- | --- | --- |
| full, ignore | 19,270 | 18,946 | 15,784 | 12,517 | 10,787 |
| full, hard | INFEASIBLE | INFEASIBLE | INFEASIBLE | INFEASIBLE | INFEASIBLE |
| example, ignore | 3,750 | 3,750 | 3,500 | 3,500 | 3,500 |
| example, hard | 3,650 | 3,650 | 3,500 | 3,500 | 3,500 |

- On the full data, capacity alone already makes must-include infeasible, so the Furniture conflict (28 must-include vs at most 3) is hidden behind it; Part 5 isolates it.
- On the example, must-include costs 100 at w ≤ 50 and nothing at w ≥ 150, where priority already loads every must-include package.
- Greedy runs only without Part 2 / Part 4 rules (5 runs per dataset); every run solves in under 0.11 s.

## Part 1 — basic model

Part 1 is a binary integer linear program: the 0/1 knapsack problem. Agreed on 2026-10-13.

### Sets

- *I* = the set of packages, indexed by *i* (1,000 packages)

### Parameters (known data)

- *wᵢ* = weight of package *i* (kg)
- *vᵢ* = value of package *i*
- *C* = truck capacity = 1,000 kg

### Decision variables

```latex
x_i \in \{0, 1\} \quad \forall i \in I
```

*xᵢ* = 1 if package *i* is loaded, 0 otherwise.

### Constraints

Capacity: total loaded weight must not exceed the truck capacity.

```latex
\sum_{i \in I} w_i x_i \le C
```

### Objective

Maximize the total value of the loaded packages.

```latex
\max \sum_{i \in I} v_i x_i
```

### Model type

Binary integer linear program (0/1 knapsack).

## Part 2 — should\_included as a hard constraint

Adds to Part 1 (config: should\_include: hard):

- *S* = packages with should\_included = True (184 packages, 19,332 kg)

```latex
x_i = 1 \quad \forall i \in S
```

### Result (2026-10-13)

Solver status: INFEASIBLE; no solution exists.

- Conflict: capacity (total weight ≤ 1,000 kg) against must-include (184 packages weighing 19,332 kg).
- Each requirement is satisfiable on its own (capacity alone: Part 1 is OPTIMAL; must-include alone, with unlimited capacity: OPTIMAL), but they are mutually incompatible with the current dataset.
- Why: the must-include packages alone weigh 19.3 times the capacity, so no selection can satisfy both.
- Greedy: skipped (does not support should\_include = hard).

Ways to restore feasibility, each a different business decision:

| Option | What changes | Trade-off |
| --- | --- | --- |
| Larger capacity | Capacity ≥ 19,332 kg (verified: 19,331 INFEASIBLE, 19,332 OPTIMAL, loading exactly the 184 must-include packages) | A bigger truck |
| Several trucks | The model: one set of variables and a capacity per truck | More vehicles to model and pay for |
| Several trips | The model: trips and their cost | Time and cost per trip |
| Shorter must-include list | should\_included data: at most 41 of the 184 fit (lightest 41 = 989 kg; lightest 42 = 1,025 kg) | Someone must decide which packages are truly mandatory |
| Must-include as a soft preference | Hard constraint → penalty in the objective (Part 6) | The solver may leave required packages behind |

Relaxing the rule changes the business requirement, not just the model: if all 184 packages truly must travel, the model must not drop some just to find a solution. Any change needs the requirement owner's approval. Finding and explaining the infeasibility is the expected outcome of Part 2.

## Part 3 — package priority

Agreed on 2026-10-14: an additive priority term in the objective, in the same unit as value, with fixed points and a varied priority\_weight.

### Data (packages.csv)

| Priority | Packages | Median value | Max value | Median value per kg | Loaded in Part 1 |
| --- | --- | --- | --- | --- | --- |
| Critical | 70 | 518 | 1,998 | 5.83 | 4 |
| High | 217 | 463 | 1,801 | 5.31 | 12 |
| Normal | 437 | 479 | 2,158 | 4.50 | 15 |
| Low | 276 | 405 | 1,703 | 4.72 | 3 |

- Median values are similar across levels (405–518), so priority is new information, not hidden in value.
- Capacity binds on weight, so packages compete on value per kg; a fixed per-package bonus favours light packages.

### Approach

- **Priority points (*pᵢ*):** numeric scores for the priority levels that represent their order of importance: Critical = 3, High = 2, Normal = 1, Low = 0. They stay fixed across experiments.
- **Priority weight (*w*):** a configurable value that controls how much priority influences the objective compared with package value. It is multiplied by the priority points to give the priority bonus.

```latex
\max \sum_{i \in I} \left( v_i + w \, p_i \right) x_i
```

Example: a package with value 500 and Critical priority (3 points), with *w* = 10, has an adjusted score of 500 + 10 × 3 = 530.

The weight is the same for all packages in an experiment; the bonus differs by each package's points. Keeping the points fixed while varying the weight measures how strongly priority affects selection. The points and weights are modelling assumptions, not values from the dataset, so they are documented and justified.

| w | Meaning (median value = 455) |
| --- | --- |
| 0 | Priority ignored (Part 1 result) |
| 50 | One step ≈ 10% of a typical value |
| 150 | One step ≈ ⅓ of a typical value |
| 500 | One step ≈ one typical package |
| 2,000 | One step ≈ the most valuable package |

### Additional modelling decisions

**1. Package divisibility.** Packages are indivisible: each is loaded entirely or not at all; partial loading is not allowed. This is the binary variable *xᵢ* ∈ {0, 1}: 1 = the entire package is selected, 0 = not selected. It suits this problem, where each package is a single unit.

**2. Priority bonus parameter.** The bonus uses fixed points per level and a configurable priority\_weight.

| Priority | Points |
| --- | --- |
| Critical | 3 |
| High | 2 |
| Normal | 1 |
| Low | 0 |

- The points stay fixed in the initial experiments; priority\_weight varies to measure how strongly priority influences selection.
- The weights 0, 50, 150, 500 and 2,000 are experimental scenarios, not values supplied by the dataset; their effects must be evaluated on the actual results.
- priority\_weight = 0 gives priority no effect, reproducing the Part 1 objective.
- The bonus is applied per package, independently of its weight. Weight affects feasibility through the capacity constraint: lighter packages leave more room for others, but get no explicit bonus in the objective.

**Optional follow-up experiment: weight tie-breaking.** Separately, minimize total loaded weight among solutions with the same optimal value-plus-priority objective. Not part of the initial Part 3 model; document its assumptions and compare results before deciding whether the rule is useful.

### Results (2026-10-14)

As priority\_weight grows, the solver trades monetary value for higher-priority packages: at w = 150 it gives up 18% of value to load 14 Critical instead of 4.

| w | Status | Packages | Critical | High | Normal | Low | Total value | Value lost vs w = 0 | Objective |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | OPTIMAL | 34 | 4 | 12 | 15 | 3 | 19,270 | — | 19,270 |
| 50 | OPTIMAL | 38 | 7 | 14 | 16 | 1 | 18,946 | 324 (1.7%) | 22,196 |
| 150 | OPTIMAL | 47 | 14 | 24 | 9 | 0 | 15,784 | 3,486 (18%) | 30,634 |
| 500 | OPTIMAL | 52 | 16 | 28 | 8 | 0 | 12,517 | 6,753 (35%) | 68,517 |
| 2,000 | OPTIMAL | 51 | 18 | 27 | 6 | 0 | 10,787 | 8,483 (44%) | 238,787 |

- w = 0 reproduces Part 1 exactly (19,270).
- w = 50 only tips close cases: 3 more Critical, 2 more High, for 1.7% of value.
- From w = 150, Low packages disappear and Critical + High dominate; beyond w = 500 the selection barely changes (diminishing returns).
- Even at w = 2,000 only 18 of 70 Critical packages load. Loaded Critical packages average 20–25 kg against 98 kg for all Critical packages: the per-package bonus favours light packages, as expected, so heavy Critical packages still lose on bonus per kg.
- More packages load as w grows (34 → 52), because light priority packages replace heavier, valuable ones.
- Objective values are not comparable across weights (each includes its own bonus); compare total value and the priority counts.

Example swap, w = 0 → w = 50: the same 115 kg is reassigned. Value drops by 324, but 3 Critical and 2 High packages come in.

| Change | Packages | Weight (kg) | Value |
| --- | --- | --- | --- |
| Out | P1000 (Low), P0881 (Low), P0101 (Normal) | 115 | 2,114 |
| In | P0017, P0545, P0338 (Critical); P0773, P0337 (High); P0419, P0830 (Normal) | 115 | 1,790 |

Why: P0545 (Critical, 25 kg, value 336) earns 13.4 value per kg, less than any package it replaced (17.9–18.8). With the bonus of 3 × 50 = 150 its score per kg rises to 19.4, overtaking P1000 (Low, 18.3 per kg, no bonus).

Greedy with the same score (sorted by score per kg) stays within 0.3% of the CP-SAT objective at every weight.

| w | CP-SAT objective | Greedy objective | Gap | Greedy total value | Greedy Critical / High / Low |
| --- | --- | --- | --- | --- | --- |
| 0 | 19,270 | 19,257 | 0.07% | 19,257 | 4 / 13 / 4 |
| 50 | 22,196 | 22,181 | 0.07% | 18,881 | 7 / 14 / 0 |
| 150 | 30,634 | 30,594 | 0.13% | 15,744 | 14 / 24 / 0 |
| 500 | 68,517 | 68,340 | 0.26% | 12,340 | 17 / 27 / 1 |
| 2,000 | 238,787 | 238,787 | 0.00% | 10,787 | 18 / 27 / 0 |

At w = 2,000 greedy finds the optimum: the bonus dominates the score, so ordering by score per kg is nearly the optimal order. Compare objectives, not total value: greedy optimises the same weighted score.

## Part 2 + Part 3 — must-include hard with the priority bonus

At capacity 1,000 kg the model is INFEASIBLE at every priority weight: the objective cannot fix feasibility.

| w | Status |
| --- | --- |
| 0 | INFEASIBLE |
| 50 | INFEASIBLE |
| 150 | INFEASIBLE |
| 500 | INFEASIBLE |
| 2,000 | INFEASIBLE |

The priority weight only changes which feasible solution is best (the objective). Feasibility depends only on the constraints, and capacity plus must-include already conflict (19,332 kg forced vs 1,000 kg), so no weight can produce a solution.

## Part 4 — business rules (implemented)

Agreed 2026-10-14: incompatible, dependency and Furniture ≤ 3 are hard; Medical ≥ 2 is soft. Every experiment can run on two datasets: full (packages.csv) or example (the brief's 10 packages); rule package IDs are set per dataset.

| Dataset | File | Incompatible pair | Note |
| --- | --- | --- | --- |
| full | data/packages.csv | P0002, P0006 | Assumption: the brief's P02/P06, zero-padded |
| example | data/example\_packages.csv | P02, P06 | As written in the brief; capacity 1,000 kg |

### Incompatible packages (implemented)

- *P* = set of incompatible pairs (*a*, *b*) of the chosen dataset

```latex
x_a + x_b \le 1 \quad \forall (a, b) \in P
```

| Dataset | Experiment | Status | Total value | Selected |
| --- | --- | --- | --- | --- |
| example | part1 | OPTIMAL | 3,750 | P01, P02, P03, P05, P09, P10 |
| example | part4\_incompatible | OPTIMAL | 3,750 | P01, P03, P05, P06, P08, P09, P10 |
| full | part1 / part4\_incompatible | OPTIMAL | 19,270 | identical (34 packages) |

- The rule does not bind on either dataset: the Part 1 optimum never loads both packages of the pair.
- On the example the selection changes but the value does not: the problem has more than one optimal solution (P02 alone, or P06 + P08, both worth 850 with the rest equal), and the extra constraint led the solver to a different one.
- Greedy skips configs with incompatible pairs.

### Dependency (implemented)

- *D* = set of (dependent *a*, required *b*) pairs: full P0007 → P0003; example P07 → P03. In CP-SAT: model.add(x\_a <= x\_b), equivalent to add\_implication for 0/1 variables.

```latex
x_a \le x_b \quad \forall (a, b) \in D
```

### Category limit (implemented)

- *F* = packages in the limited category (Furniture), limit 3; set per experiment as a category rule {category: Furniture, at\_most: 3}

```latex
\sum_{i \in F} x_i \le 3
```

### Results: all three hard rules (2026-10-14)

No hard rule binds on its own with should\_include ignored, on either dataset: every Part 4 run keeps the Part 1 value.

| Dataset | Experiments | Status | Weight (kg) | Total value | Selected |
| --- | --- | --- | --- | --- | --- |
| example | part1, part4\_dependency, part4\_furniture\_max, part4\_medical\_\*, part4\_all\_rules\_p500 | OPTIMAL | 960 | 3,750 | P01, P02, P03, P05, P09, P10 |
| example | part4\_incompatible, part4\_hard\_rules, part4\_all\_rules\_p0 / p50 / p150 | OPTIMAL | 990 | 3,750 | P01, P03, P05, P06, P08, P09, P10 |
| full | part1 and every part4 run | OPTIMAL | 1,000 | 19,270 | same 34 packages, all Medical |

- Example: P07 is never loaded, so the dependency never triggers; the example has only 2 Furniture packages, so the limit of 3 cannot bind. Selections differ only between the two equal-value optima.
- Full: the optimum is 34 Medical packages; P0002, P0003, P0006, P0007 and any Furniture are never loaded.
- The rules start to bind when combined with must-include hard: on the full data, 28 must-include Furniture packages against a limit of 3 make the model infeasible at any capacity (the Part 5 scenario).
- Greedy skips every Part 4 rule.

Equal-value optima on the example (re-run 2026-10-14): which of the two 3,750 selections CP-SAT returns depends on the exact model, not on the rules' effect. Rewriting the dependency from add\_implication to x\_a ≤ x\_b moved part4\_dependency from the P06 + P08 selection to the P02 selection, with the same value. When the value is tied, the package list is arbitrary; compare objective values.

### Category minimum — soft (implemented)

"Prefer" makes it a soft constraint: the solver may load fewer than two Medical packages, but pays a penalty per missing package. The penalty is not in the dataset; it is an experimental parameter that expresses how much the preference is worth in value.

- *M* = Medical packages, target *T* = 2, λ = category\_min\_penalty
- *s* = shortfall, an integer variable with 0 ≤ *s* ≤ *T*: the number of Medical packages missing from the target

```latex
\sum_{i \in M} x_i + s \ge T, \qquad \max \sum_{i \in I} (v_i + w \, p_i) \, x_i - \lambda s
```

The penalty lowers the objective of solutions that miss the target; it does not make them invalid. A small λ lets the solver give up the preference for value; a large λ makes it give up value for the preference.

| Dataset | λ = 0 | λ = 50 | λ = 150 | λ = 500 | All four rules (λ = 150) |
| --- | --- | --- | --- | --- | --- |
| example | 3,750, shortfall 0 | 3,750, shortfall 0 | 3,750, shortfall 0 | 3,750, shortfall 0 | 3,750, shortfall 0 |
| full | 19,270, shortfall 0 | 19,270, shortfall 0 | 19,270, shortfall 0 | 19,270, shortfall 0 | 19,270, shortfall 0 |

- The preference is already met without any penalty (example: P03 and P09; full: 34 Medical packages), so the penalty has no effect at any value.
- Its effect is shown in Part 6.2 on the example with smaller trucks (decision flips at λ = 150 for 200 kg, λ = 300 for 250 kg) and in tests/test\_part4.py.
- Greedy skips category targets.

### Category rules: direction and strictness are separate

Decided 2026-10-14: at least / at most (direction) and hard / soft (strictness) are independent choices. Every category rule states both; a rule with a penalty is soft, without one it is hard.

```yaml
category_rules:
  - {category: Furniture, at_most: 3}                # hard maximum
  - {category: Medical, at_least: 2, penalty: 150}   # soft minimum
```

| Rule | Hard | Soft (v = violation variable, penalised by λ · v) |
| --- | --- | --- |
| at\_least n | Σ xᵢ ≥ n | Σ xᵢ + v ≥ n |
| at\_most n | Σ xᵢ ≤ n | Σ xᵢ − v ≤ n |

All four combinations are tested (tests/test\_part4.py). Experiments part4\_all\_rules\_p0 / p50 / p150 / p500 run every Part 4 rule together, one per Medical penalty; results are unchanged (example 3,750, full 19,270, no violations).

## Part 5 — infeasibility experiments (2026-10-15)

Four infeasible scenarios, each run, diagnosed automatically, explained, then relaxed in more than one way and re-run. Every relaxation restores a solution, but each is a different business decision.

### How conflicts are found

Each hard rule group (capacity, must-include, incompatible, dependency, each hard category rule) gets an on/off switch; its constraints apply only while the switch is on (only\_enforce\_if). On INFEASIBLE, CP-SAT reports the switches that explain it (sufficient\_assumptions\_for\_infeasibility); removing one group at a time then keeps a minimal conflict set. The runner does this automatically for every infeasible run and prints it, e.g. "Conflict: capacity + must\_include".

### Scenarios

| Scenario | Dataset | Conflict found | Why no solution exists |
| --- | --- | --- | --- |
| A | full | capacity + must\_include | 184 must-include packages weigh 19,332 kg; one truck carries 1,000 kg |
| B | full, capacity 25,000 kg | must\_include + Furniture at\_most 3 | Weight fits, but 28 must-include packages are Furniture and at most 3 are allowed |
| C | example, capacity 600 kg | capacity + must\_include | The 5 must-include packages need 660 kg |
| D | example | Medical at\_least 3 (alone) | Only 2 Medical packages exist: the rule is impossible on this data by itself |

### Relaxations and results

| Scenario | Relaxation (business decision) | Status | Must-include loaded | Total value | Objective | Comment |
| --- | --- | --- | --- | --- | --- | --- |
| A | Bigger truck: capacity 19,332 kg | OPTIMAL | 184 / 184 | 107,742 | 107,742 | Exactly the must-include packages; nothing else fits |
| A | Fleet: 20 trucks of 1,000 kg (19 proven infeasible) | OPTIMAL | 184 / 184 | 120,592 | 120,592 | Every truck exactly full; the spare 668 kg carries extra value; solve 38 s |
| A | Must-include as a preference, 500 per package left behind | OPTIMAL | 38 / 184 | 13,593 | −59,407 | One 1,000 kg truck: keeps 38 required packages (Part 1 kept 11 by chance), mostly light Critical / High ones; value −29% vs Part 1; pays for the 146 left behind |
| B | Raise the Furniture limit to 28 | OPTIMAL | 184 / 184 | 183,148 | 183,148 | Requirement owner accepts more Furniture |
| B | Furniture limit as a preference, 500 per extra package | OPTIMAL | 184 / 184 | 183,148 | 170,648 | Same load; pays for 25 extra Furniture packages |
| B | Must-include as a preference, Furniture limit kept | OPTIMAL | 139 / 184 | 231,194 | 208,694 | Leaves 45 required packages (25 Furniture forced out); freed space carries more valuable packages |
| C | Bigger truck: 660 kg | OPTIMAL | 5 / 5 | 2,650 | 2,650 | Only the must-include packages |
| C | Fleet: 2 trucks of 600 kg | OPTIMAL | 5 / 5 | 4,500 | 4,500 | Adds P02 and P10; trucks 580 / 600 kg |
| C | Must-include as a preference, 500 each | OPTIMAL | 4 / 5 | 2,300 | 1,800 | Leaves P09 behind |
| D | Medical minimum as a preference, 500 per missing package | OPTIMAL | — | 3,750 | 3,250 | Loads both Medical packages; pays for the missing third |

### What the business can relax

- **More capacity:** a bigger truck, more trucks or more trips (A, C). Keeps every requirement but costs vehicles; the fleet also carries extra value.
- **Change a limit:** raise the Furniture maximum (B). Valid only if the limit is a policy, not a physical or safety rule.
- **Turn a requirement into a preference with a price** (A, B, C, D). Always feasible, but some required packages stay behind; the penalty states how much each is worth.
- **Fix the requirement or the data** (D). A rule that is impossible on the data alone points to a wrong requirement or missing packages, not to the optimizer.

Any relaxation changes the business requirement, so it needs the requirement owner's approval. Penalties of 500 are experimental (about one typical package's value); Part 6 varies them.

### Agentic AI for diagnostics

Used in this project with Claude Code: after an INFEASIBLE run the agent read the conflict, inspected the data (must-include weight, Furniture counts), ran boundary checks (19,331 vs 19,332 kg; 19 vs 20 trucks), proposed relaxations, ran them as experiments, compared the results and updated this document — a diagnose → fix → verify loop of minutes instead of hours.

- Strengths: fast what-if runs, structured comparison, consistent documentation.
- Guardrail: the agent proposes; a person approves any change to a business rule.
- Limit: its explanations must be checked against the actual results.

## Part 6 — objective and penalty experiments (2026-10-15)

Weights decide what "best" means: raising the should-include weight trades value for required packages until no more fit (41 on one truck), raising the priority weight trades value for Critical/High packages, and only the ratios between weights matter.

```latex
\max \; \sum_i \left( w_{value} v_i + w_{priority} p_i \right) x_i \; - \; w_{should} \cdot (\text{required packages left behind}) \; - \; \sum_{\text{soft rules}} \lambda \cdot \text{violation}
```

- Value weight = value\_weight; should-include weight = should\_include\_penalty (must-include soft); priority weight = priority\_weight; λ = a soft category rule's penalty.
- 104 runs in three sweeps (part6\_weights, part6\_medical, part6\_furniture); every run OPTIMAL in under 1 s. Full rows: results/summary\_\*.csv.

### 6.1 Value vs should-include vs priority (full dataset, one 1,000 kg truck)

| Experiment | Value weight | Should-include weight | Priority weight | Selected packages | Total value | Preferred included (of 184) | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 0 | 0 | 34 | 19,270 | 11 | OPTIMAL |
| 2 | 1 | 100 | 0 | 37 | 18,939 | 17 | OPTIMAL |
| 3 | 1 | 500 | 0 | 39 | 13,593 | 38 | OPTIMAL |
| 4 | 1 | 2,000 | 0 | 41 | 11,180 | 41 | OPTIMAL |
| 5 | 1 | 0 | 50 | 38 | 18,946 | 14 | OPTIMAL |
| 6 | 1 | 0 | 500 | 52 | 12,517 | 25 | OPTIMAL |
| 7 | 1 | 500 | 500 | 49 | 11,429 | 34 | OPTIMAL |
| 8 | 10 | 0 | 500 | 38 | 18,946 | 14 | OPTIMAL |
| 9 | 10 | 2,000 | 0 | 37 | 17,908 | 24 | OPTIMAL |
| 10 | 0 | 2,000 | 0 | 41 | 10,498 | 41 | OPTIMAL |
| 11 | 0 | 0 | 0 | 0 | 0 | 0 | OPTIMAL |

Why the decisions changed:

- 1 → 4: each required package left behind costs the should-include weight, so as it rises the solver swaps valuable optional packages for light required ones. Coverage rises 11 → 17 → 38 → 41 and stops at 41: the lightest 41 required packages weigh 989 kg, the most that fit (the same limit found in Part 2). Value falls 42%.
- 1 → 5 → 6: the priority bonus pulls in Critical/High packages (Part 3); they are often required too, so coverage also rises (11 → 25) without any should-include weight.
- 7: both preferences together compete for the same 1,000 kg; the load is a compromise (34 required, 18 Critical).
- 8 = 5 exactly: multiplying all weights by 10 changes nothing — only ratios matter. 9: value ×10 dilutes the should-include weight, so it acts like 200 instead of 2,000 (24 required instead of 41).
- 10: with value ignored, the solver simply maximises coverage (41) with whatever value results.
- 11: with every weight 0, all loads score 0, so an empty truck is "optimal" — the objective must value something.

On the example the same sweep shows the small-scale version: all 5 required packages fit, so coverage reaches 5 / 5 once the should-include weight exceeds the 100 of value it costs (at value weight 10 it needs 2,000).

### 6.2 Soft category requirement vs value (example, soft Medical ≥ 2)

The Medical preference is non-binding on the full data (Part 4); here smaller trucks make it compete.

| Capacity | λ = 0–100 | λ = 150–200 | λ = 500 | Break-even |
| --- | --- | --- | --- | --- |
| 200 kg | P01 + P03, value 900, 1 Medical | P03 + P09, value 750, 2 Medical | P03 + P09 | 150 (900 − 750) |
| 250 kg | P03 + P05, value 1,050, 1 Medical | same (1,050) | P03 + P09, value 750 | 300 (1,050 − 750) |
| 300 kg | P01 + P03 + P09, value 1,250, 2 Medical | same | same | none: room for both |

The decision flips exactly when the penalty passes the value that meeting the preference costs; with enough capacity the rule costs nothing and the penalty is irrelevant.

### 6.3 Two soft requirements competing (full dataset, 25,000 kg)

Must-include (weight w\_should) against Furniture at most 3 (penalty λ); 28 required packages are Furniture.

| w\_should | λ Furniture | Required loaded | Extra Furniture | Total value |
| --- | --- | --- | --- | --- |
| 100 | 0–2,000 | 97 | 0 | 241,301 |
| 500 | 0 | 142 | 3 | 230,036 |
| 500 | 500–2,000 | 139 | 0 | 231,194 |
| 2,000 | 0–100 | 179 | 20 | 194,530 |
| 2,000 | 500 | 174 | 15 | 203,062 |
| 2,000 | 2,000 | 159 | 0 | 217,380 |

- A cheap should-include weight (100) drops required packages freely, so the Furniture limit never matters.
- With an expensive should-include weight (2,000), the Furniture penalty decides: cheap → load the required Furniture and pay for 20 extra; equal (2,000) → leave required Furniture behind instead.
- Each required Furniture package is kept only while its should-include weight beats the Furniture penalty it triggers: the weights encode which preference the business values more.

### 6.4 The same rule as soft vs hard (Medical ≥ 2)

Soft lets the solver trade the rule for value at a price; hard never trades it — and fails when it cannot be met.

| Dataset, capacity | Soft, λ = 50 | Soft, λ = 150 | Hard |
| --- | --- | --- | --- |
| example, 150 kg | P05: value 650, 0 Medical (pays 2 × 50) | P05: value 650, 0 Medical (pays 2 × 150) | INFEASIBLE — conflict: capacity + Medical at\_least 2 (P03 + P09 weigh 170 kg) |
| example, 200 kg | P01 + P03: value 900, 1 Medical | P03 + P09: value 750, 2 Medical | P03 + P09: value 750 |
| example, 250 kg | P03 + P05: value 1,050, 1 Medical | P03 + P05: value 1,050, 1 Medical | P03 + P09: value 750 |
| example, 1,000 kg | value 3,750, rule met | same | same |
| full, 1,000 kg | value 19,270, rule met | same | same |

- When the rule is met for free (1,000 kg), soft and hard give the same load: the difference only shows under pressure.
- Hard is the limit of soft with an infinite penalty: at 200 kg a penalty of 150 already matches hard; at 250 kg it does not (break-even 300), so soft keeps 300 more value.
- Where the rule is impossible (150 kg), hard returns no plan at all, while soft still loads the truck and reports exactly what is missing.
- Choose hard only for rules that must never be broken (safety, law); otherwise soft with a justified penalty gives a plan plus a visible cost.

## Part 8 — scaling experiments (2026-10-15)

Model size alone did not predict solve time: on large single-truck models CP-SAT spent almost all its time in single-threaded presolve, so extra workers did nothing and switching presolve off made the 100,000-package case solvable in 3.3 s; with many trucks, symmetry and the gap limit decide the time.

### Machine and settings

| Item | Value |
| --- | --- |
| Machine | Apple M4 Pro, 14 cores (10 performance + 4 efficiency), 24 GB memory |
| Software | macOS 26.4, Python 3.12.8, OR-Tools CP-SAT 9.15 |
| Defaults | 8 workers, 60 s time limit, seed 0, relative gap limit 0, presolve on |
| Data | Random datasets (scripts/generate\_dataset.py, seed 42): weight 5–400 kg, value = weight × 1–10 per kg, real priority / category / should\_included shares |

### The solver gap

- CP-SAT tracks the best solution found (objective) and a proven upper bound: no solution can score more. Gap = (bound − objective) / bound.
- Gap 0 = proven optimal. A gap of 0.08% at the time limit (FEASIBLE) means the plan is at most 0.08% below the best possible.
- Every run records best\_bound and gap (result.json, summary CSV). When a relative\_gap\_limit stops the search, CP-SAT reports OPTIMAL meaning "optimal within the limit" — only the gap shows the difference.
- SmartSchedulingOptimizerCore uses relative\_gap\_limit = 0 plus a GapStallCallback that stops when the gap improves by less than 0.5 percentage points in 90 s; it measures the gap relative to the objective, we relative to the bound (nearly equal for small gaps).

### Size × capacity (8 workers, 60 s, presolve on)

| Packages (variables) | Fixed 1,000 kg | Scaled (0.5% of weight) | Generous (25%) |
| --- | --- | --- | --- |
| 1,000 | 0.01 s | 0.006 s | 0.38 s |
| 5,000 | 0.03 s | 0.17 s | 3.8 s |
| 10,000 | 0.04 s | 2.1 s | 5.9 s |
| 50,000 | 1.4 s | 34.5 s | 27.5 s |
| 100,000 | 2.8 s | UNKNOWN (no solution in 60 s) | 55.6 s |

One capacity constraint throughout; every solved run OPTIMAL with gap 0. A fixed truck stays easy at any size (only a few top packages matter); the scaled truck is hardest.

### Results in the brief's format

| # | Case | Variables | Constraints | Solve time | Status | Objective (gap) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1,000 packages, scaled truck | 1,000 | 1 | 0.006 s | OPTIMAL | 10,047 (0%) |
| 2 | 10,000, scaled | 10,000 | 1 | 2.1 s | OPTIMAL | 100,544 (0%) |
| 3 | 50,000, scaled | 50,000 | 1 | 34.5 s | OPTIMAL | 503,917 (0%) |
| 4 | 50,000, scaled, 5 s limit | 50,000 | 1 | 4.8 s | UNKNOWN | — |
| 5 | 100,000, scaled | 100,000 | 1 | 60 s | UNKNOWN | — |
| 6 | 100,000, fixed 1,000 kg | 100,000 | 1 | 2.8 s | OPTIMAL | 10,000 (0%) |
| 7 | 100,000, generous 25% | 100,000 | 1 | 55.6 s | OPTIMAL | 45,038,593 (0%) |
| 8 | 100,000, scaled, presolve off | 100,000 | 1 | 3.3 s | OPTIMAL | 1,011,780 (0%) |
| 9 | Full data, 20 trucks | 21,000 | 1,204 | 48.4 s | OPTIMAL | 120,592 (0%) |
| 10 | Full data, 25 trucks | 26,000 | 1,209 | 60 s | FEASIBLE | 182,943 (0.11%) |

Rows 5 and 6 have identical size, yet one finds nothing in 60 s and the other solves in 2.8 s: the capacity, not the number of variables, drives difficulty. Full rows for every run: results/summary\_\*.csv (re-run the part8 sweeps).

### Workers and time limit (50,000 packages, scaled)

| Workers | 1 | 2 | 4 | 8 | 10 | 14 |
| --- | --- | --- | --- | --- | --- | --- |
| Solve time (s) | 31.5 | 31.6 | 29.2 | 32.0 | 34.7 | 34.4 |

| Time limit | 1 s | 5 s | 30 s |
| --- | --- | --- | --- |
| Status | UNKNOWN | UNKNOWN | OPTIMAL (30.1 s) |

CP-SAT's log explains both: presolve ran from 0 to 27.5 s on one thread (it generated about 1.9 million clauses from the capacity constraint); the search then found the first solution at 29.2 s and the optimum about a second later. Workers only speed up the search, and any limit below about 28 s ends before the search starts.

### Presolve on vs off

| Case | Presolve on | Presolve off |
| --- | --- | --- |
| 10,000 scaled / generous | 2.0 s / 5.2 s | 0.26 s / 0.39 s |
| 50,000 scaled / generous | 30.3 s / 24.4 s | 1.3 s / 1.2 s |
| 100,000 scaled / generous | UNKNOWN / 50.4 s | 3.3 s / 2.6 s |

Same optimal values everywhere: for this one-constraint model presolve costs far more than it saves. It is a tuning choice per model, not a rule — presolve often helps on richer models.

### Trucks and symmetry breaking (full dataset, all 184 must-include packages)

| Trucks (variables) | No symmetry breaking | Symmetry breaking (truck loads ordered) |
| --- | --- | --- |
| 20 (21,000) | OPTIMAL, 48.4 s | OPTIMAL, 17.8 s |
| 21 (22,000) | FEASIBLE at 60 s, gap 0.047% | FEASIBLE at 60 s, gap 0.003% |
| 25 (26,000) | FEASIBLE at 60 s, gap 0.11% | FEASIBLE at 60 s, gap 1.45% |

Identical trucks make every load appear in many swapped versions. Ordering trucks by load removed them: 2.7× faster at 20 trucks and a 15× smaller gap at 21 — but worse at 25, where the extra constraints made good solutions harder to find within 60 s. Symmetry breaking is worth testing, not assuming.

### Limiting the gap (25 trucks)

| Relative gap limit | Status | Objective | Gap | Time |
| --- | --- | --- | --- | --- |
| 0 (default) | FEASIBLE (time limit) | 183,008 | 0.079% | 60.0 s |
| 0.1% | OPTIMAL within limit | 182,972 | 0.099% | 45.9 s |
| 1% | OPTIMAL within limit | 181,491 | 0.91% | 1.0 s |
| 5% | OPTIMAL within limit | 181,491 | 0.91% | 1.0 s |

Accepting 1% returns a plan in 1 s instead of 60 s, giving up 0.8% of value. Repeated runs under a time limit vary slightly (the earlier 25-truck run ended at 182,943): with several workers, timing makes the search non-deterministic even with a fixed seed.

### Observations

1. Variables alone do not predict difficulty: 100,000 packages with a 1,000 kg truck solve in 2.8 s, the same packages with a \~100,000 kg truck did not solve in 60 s.
2. Look at the solver log before adding workers: here the bottleneck was single-threaded presolve, and workers did nothing.
3. Presolve off solved every large case in under 4 s — the largest single improvement in the project.
4. Many trucks create symmetry; ordering trucks can help a lot or hurt, so measure it.
5. Always record status and gap together: a gap limit turns "FEASIBLE after 60 s" into "OPTIMAL within 1% after 1 s".

## Explanations

### Why the model is not an LP

An LP (linear program) lets variables take any value, including fractions: xᵢ = 0.6 would mean loading 60% of a package. Packages are indivisible, so each xᵢ must be exactly 0 or 1 — a binary integer program, solved with CP-SAT.

| Model (capacity 10 kg; A 6 kg / 30, B 5 kg / 20, D 5 kg / 20) | Answer | Value |
| --- | --- | --- |
| LP, fractions allowed | All of A + 80% of B | 30 + 16 = 46 |
| Our model, xᵢ ∈ {0, 1} | B + D | 40 |

The LP answer is impossible in reality, but it is a valid ceiling: no real load can beat 46. Solvers use such relaxed calculations for the best bound behind the solver gap (Part 8).

### Why the Part 1 load is all Medical

With value as the only objective and a 1,000 kg truck, packages compete on value per kg, and Medical packages earn far more per kg than any other category.

| Category | Median value per kg | Best 34 packages, average value per kg |
| --- | --- | --- |
| Medical | 13.6 | 19.3 |
| Electronics | 9.1 | 12.2 |
| Equipment | 4.9 | 7.1 |
| Furniture | 3.5 | 4.9 |
| Food | 2.5 | 4.1 |

So the optimal load is 34 packages, all Medical. This explains later results: "prefer at least 2 Medical" and "at most 3 Furniture" never bind (Part 4), and a priority weight is needed to bring Critical and High packages in from other categories (Part 3). A value-only objective concentrates the load in one category; business rules correct that imbalance.

## Extra — greedy baseline (own addition, not in the brief)

A greedy heuristic runs next to CP-SAT on the Part 1 model, to compare total value and solve time.

Algorithm:

1. Sort packages by value per kg, *vᵢ* / *wᵢ*, highest first.
2. Load each package in that order if it still fits within *C*; skip it otherwise.

Compare: total value, total weight, selected packages and run time against the CP-SAT result.

Expected: greedy is fast but not guaranteed optimal for 0/1 knapsack (for example, *C* = 10 with A (6 kg, 30), B (5 kg, 20), D (5 kg, 20): greedy gets 30, optimal is 40).

Code: src/cargo\_optimizer/greedy.py. It reads the same config as the CP-SAT model; the config chooses the method (CP-SAT or greedy), and run\_experiment.py runs whichever is chosen and records results in the same format.

Unsupported rules (agreed 2026-10-13): if a config uses a rule greedy cannot honour (soft penalties, dependencies, etc.), greedy skips that config and the results record it as skipped, with the reason.

## Part 1 results (2026-10-13)

CP-SAT is optimal at 19,270; greedy reaches 19,257 (13 less) on the same 1,000 kg.

| Method | Status | Packages | Weight (kg) | Value | Time (s) |
| --- | --- | --- | --- | --- | --- |
| CP-SAT | OPTIMAL | 34 | 1,000 | 19,270 | 0.024 |
| Greedy | FEASIBLE | 35 | 1,000 | 19,257 | 0.0001 |

The selections differ in 32 kg: CP-SAT loads P0574 + P0637 (value 566); greedy loads P0337 + P0419 + P0724 (value 553). Greedy reached P0637 (25 kg) when it no longer fitted, then filled the gap with smaller packages.
