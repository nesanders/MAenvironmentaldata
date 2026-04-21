---
layout: default
title: Testing Plan
permalink: /testing-plan/
---

# AMEND Testing Plan

## Goals

- Catch regressions in the data → DB → charts CI pipeline before they hit `main`
- Verify the semantic context supports accurate AI-generated SQL as it evolves
- All tests run locally without network access where possible; total runtime under ~5 minutes
- Runnable on GitHub Actions free tier

---

## Test Categories

### 1. Syntax Checks (~2s)

`py_compile` every script in `get_data/` and `analysis/`. Catches broken imports and syntax errors before any execution. No linting — the codebase is old and broad linting would generate noise without real value.

```python
# tests/test_syntax.py
import py_compile, glob, pytest

@pytest.mark.parametrize("path", glob.glob("get_data/*.py") + glob.glob("analysis/*.py"))
def test_compiles(path):
    py_compile.compile(path, doraise=True)
```

### 2. Data Integrity (~5s)

Run against the committed CSVs in `docs/data/` — no network, no execution. Guards against:

- Required files missing or empty
- Required columns absent from key CSVs (schema regression)
- Row counts below known minimums (data truncation / source change)
- `docs/data/data_stats.yml` parseable and consistent with files on disk

```python
# tests/test_data_integrity.py
REQUIRED_FILES = {
    "docs/data/MAEEADP_CSO.csv": {"min_rows": 50000, "required_cols": ["incidentDate", "volumnOfEvent", "waterBody", "municipality", "eventType"]},
    "docs/data/MAEEADP_Enforcement.csv": {"min_rows": 10000, "required_cols": ["EnforcementDate", "Town", "FacilityId", "ActionType"]},
    "docs/data/MADEP_staff_Comptroller.csv": {"min_rows": 500, "required_cols": ["year", "name", "title", "dept"]},
    "docs/data/MassBudget_summary.csv": {"min_rows": 20, "required_cols": ["Year", "DEP_budget"]},
    "docs/data/EPA_303d_Impairments.csv": {"min_rows": 1000, "required_cols": ["waterbody", "reportingCycle", "hasTmdl", "category"]},
}
```

### 3. DB Assembly (~30s)

Runs `assemble_db.py` against the committed CSVs in a temp directory. Requires a `--no-upload` flag to skip the GCS push. Asserts:

- `AMEND.db` is created and non-empty
- All expected tables exist with correct column names
- Row counts match `data_stats.yml` within a tolerance (±5%)
- `docs/assets/db_semantic_context.txt` is regenerated without error

This is the closest possible proxy for the Monday `update-data.yml` workflow. If this passes locally, the CI run will pass.

### 4. Semantic Context Evals (~60–90s)

See detailed section below.

---

## Semantic Context Evals — Detailed Design

### What we're testing

When `generate_semantic_context.py` changes, or when table schemas / data change, the semantic context in `docs/assets/db_semantic_context.txt` may regress: the LLM generates invalid SQL, misuses a join, applies a filter to the wrong table, or returns empty results for a valid question.

The eval suite catches these regressions by running a fixed set of natural-language questions through the full pipeline (semantic context → LLM → SQL → execution against `AMEND.db`) and judging the outputs.

### Infrastructure: GitHub Models

We use the **GitHub Models API** for CI evals:

- Uses `GITHUB_TOKEN`, which is automatically injected in every GHA run — no secret management, works on fork PRs
- OpenAI-compatible endpoint, so the client code is trivial
- Model: `gpt-4o-mini` for both generation and judging — 10 evals × 2 calls = 20 total requests per run

**Context window caveat:** GitHub Models free tier has a hard 8000-token limit across all models (confirmed across `gpt-4o-mini`, `gpt-4o`, `Meta-Llama-3.1-8B-Instruct`, `Meta-Llama-3.1-405B-Instruct`). The full semantic context is ~20k tokens. The evals therefore send only the **"Global Data Notes" and "Key Join Relationships" sections** (~1200 tokens) — the portion of the context that governs SQL correctness for our eval cases (join patterns, preferred tables, ALL CAPS warnings, date format notes). The table schemas and 5-row sample data blocks are excluded. This is a principled extraction, not arbitrary truncation: if someone changes the join examples or global notes in `generate_semantic_context.py`, the evals will catch it.

Using the same model for generation and judging is a known limitation — a stronger judge would catch more subtle errors. This is acceptable given the free-tier constraint.

```python
from openai import OpenAI
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.environ["GITHUB_TOKEN"],
)
```

For local runs, set `GITHUB_TOKEN` to a personal access token with `models: read` scope, or set `OPENAI_API_KEY` to use OpenAI directly as a fallback.

### Fixture file

Evals are defined in `tests/eval_fixtures.yaml`. Each entry is a natural-language question plus a set of assertions. The fixture format:

```yaml
- id: cso_top_operator_2022
  question: "Which CSO operator discharged the most volume in 2022?"
  tags: [cso, aggregation]
  assert_sql_runs: true
  assert_nonempty: true
  assert_min_rows: 1
  assert_columns_include: []          # exact column name checks (optional)
  assert_sql_contains: []             # regex patterns the SQL must match (optional)
  assert_sql_not_contains:            # anti-patterns that indicate a known failure mode
    - "CSO_303d_Mapping"              # wrong table for this query
  judge_rubric: |
    The query should return a ranked list of operators with their total discharge volume for 2022.
    It should use MAEEADP_CSO, filter eventType LIKE 'CSO%', filter by year 2022, and GROUP BY operator.
    Penalise if: wrong table used, no year filter, no GROUP BY, empty result.
```

### Planned eval cases (v1, 10 cases)

Selected to cover the most important join patterns and the failure modes most likely to be introduced by semantic context changes. Each case was chosen to exercise a distinct pattern — no redundant cases.

| id | Question | What it tests |
|----|----------|---------------|
| `cso_top_operator` | Which CSO operator discharged the most volume in 2022? | Basic `MAEEADP_CSO` aggregation, year filter |
| `cso_monthly_rainfall` | Show monthly CSO discharge volume vs rainfall over the past 5 years | Month-aggregation join pattern; must NOT join raw dates directly |
| `cso_by_watershed` | What's the total CSO volume by watershed? | `CSO_WatershedMapping` join |
| `enforcement_vs_budget` | Compare DEP enforcement actions to DEP budget by year | Cross-table join: `MAEEADP_Enforcement` + `MassBudget_summary` |
| `staffing_trend` | Show DEP staffing levels from 2005 to present | `MADEP_staff_Comptroller`; basic time series |
| `303d_impaired_trend` | How has the number of impaired waters changed across reporting cycles? | `reportingCycle` grouping in `EPA_303d_Impairments` |
| `303d_named_waterbody` | Is the Mystic River listed as impaired? | Direct lookup in `EPA_303d_Impairments`; must NOT misuse `CSO_303d_Mapping` |
| `cso_to_impaired` | Which CSO discharges go into 303(d) impaired waters? | Two-step join via `CSO_303d_Mapping`; `reportingCycle` filter must land on `EPA_303d_Impairments` not `CSO_303d_Mapping` |
| `all_caps_boston` | Show CSO events in Boston | ALL CAPS handling: `UPPER(municipality) = 'BOSTON'` |
| `ecos_per_capita` | How does Massachusetts per-capita environmental spending compare to other states? | `ECOS_budgets` table; different data asset from the rest |

### Evaluation: two-pass judging

Each eval runs two independent checks:

**Pass 1 — Hard assertions (deterministic):**
- SQL parses and executes without error against `AMEND.db`
- Result is non-empty (or empty when expected)
- SQL contains / does not contain required patterns (from `assert_sql_not_contains`)
- Column names match expectations

**Pass 2 — LLM-as-judge (rubric scoring):**

A second `gpt-4o-mini` call evaluates the generated SQL against the rubric. The judge receives:

```
SYSTEM: You are evaluating SQL generated by an AI assistant for correctness and quality.
        Score the SQL on a scale of 1–5 using the rubric provided.
        Respond with JSON only: {"score": <1-5>, "reason": "<one sentence>", "fatal": <true|false>}
        fatal=true means the query would return wrong or misleading results
        (wrong table, missing required filter, wrong join, etc.)

USER:
Question: {question}
Generated SQL: {sql}
Rubric: {judge_rubric}
Schema excerpt: {relevant_schema_excerpt}
```

### Metrics and persistence

Eval results are posted as a **PR comment** after each run (or as a commit status annotation on push to `main`). The comment shows the full per-case breakdown and summary metrics.

A `tests/eval_results/summary.json` is also kept in the repo, updated each CI run, so the quality trend is visible in git history without needing an external metrics store.

**Per-run JSON schema:**
```json
{
  "run_at": "2026-04-20T06:00:00Z",
  "model": "gpt-4o-mini",
  "judge_model": "gpt-4o-mini",
  "semantic_context_hash": "abc123",
  "results": [
    {
      "id": "cso_top_operator",
      "tags": ["cso", "aggregation"],
      "passed_hard": true,
      "judge_score": 4,
      "judge_reason": "Correct table and grouping; year filter present.",
      "judge_fatal": false,
      "sql_generated": "SELECT operator, SUM(volumnOfEvent) ...",
      "error": null,
      "duration_ms": 1240
    }
  ],
  "summary": {
    "total": 10,
    "hard_pass": 9,
    "fatal_failures": 0,
    "mean_judge_score": 3.8,
    "p50_judge_score": 4.0
  }
}
```

**CI pass/fail thresholds (configurable in `tests/eval_config.yaml`):**
```yaml
fail_on_hard_pass_below: 0.80      # <80% hard-pass rate fails CI
fail_on_fatal_above: 0             # any fatal failure fails CI
warn_on_mean_judge_score_below: 3.0  # mean judge score < 3 posts a warning annotation
```

A "fatal" failure (wrong table, missing required filter, empty result for a non-empty question) always fails CI. A low judge score only warns, because style/verbosity differences shouldn't break the build.

### Trigger strategy

Evals run only on `pull_request` events, and only when one of these files changed:
- `docs/assets/db_semantic_context.txt`
- `tests/eval_fixtures.yaml`
- `get_data/generate_semantic_context.py`
- `tests/test_semantic_evals.py`

This prevents quota burn on every push. Pushes to a branch without a PR, or PRs that touch only non-semantic files, don't trigger evals.

### GitHub Actions job

```yaml
# in .github/workflows/tests.yml
evals:
  name: Semantic evals
  if: github.event_name == 'pull_request'
  runs-on: ubuntu-latest
  permissions:
    models: read           # required for GitHub Models
    pull-requests: write   # to post PR comment
    contents: write        # to commit summary.json
  steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with: { python-version: "3.11" }
    - run: pip install openai pytest pyyaml
    - name: Run evals
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      run: pytest tests/test_semantic_evals.py -v --tb=short
    - name: Post eval summary as PR comment
      if: github.event_name == 'pull_request'
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      run: python tests/post_eval_comment.py   # reads summary.json, posts via gh API
    - name: Commit eval summary to main
      if: github.ref == 'refs/heads/main'
      run: |
        git config user.name "github-actions[bot]"
        git config user.email "github-actions[bot]@users.noreply.github.com"
        git add tests/eval_results/summary.json
        git diff --staged --quiet || git commit -m "Update eval summary [skip ci]" && git push
```

---

## Proposed Workflow Structure

```yaml
# .github/workflows/tests.yml
on:
  push:
  pull_request:

jobs:
  fast:
    # Syntax + data integrity: ~15s
    # No secrets, no network — runs on every push
    steps:
      - pytest tests/test_syntax.py tests/test_data_integrity.py

  db-assembly:
    needs: fast
    # Builds AMEND.db from committed CSVs, checks tables/rows: ~30s
    # Requires adding --no-upload flag to assemble_db.py
    steps:
      - conda run -n amend_python python get_data/assemble_db.py --no-upload
      - pytest tests/test_db_assembly.py

  evals:
    needs: fast
    # Semantic context evals via GitHub Models: ~60-90s
    # Uses GITHUB_TOKEN, no extra secrets needed
    # continue-on-error: true initially while tuning fixtures
    steps:
      - pytest tests/test_semantic_evals.py
```

---

## Build Order

1. `tests/test_syntax.py` + `tests/test_data_integrity.py` — zero dependencies, immediate value
2. `--no-upload` flag in `assemble_db.py` + `tests/test_db_assembly.py`
3. `tests/eval_fixtures.yaml` + `tests/test_semantic_evals.py` — highest unique value
