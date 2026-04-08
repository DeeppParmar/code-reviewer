# Code Review Environment — Package Documentation

> Internal package directory for the Code Review OpenEnv benchmark.

---

## Environment Overview

This package contains **Code Review OpenEnv**, a production-grade evaluation environment where an AI agent plays the role of a code reviewer. The agent receives buggy Python pull-request content, leaves line-specific review comments, and is scored on finding real bugs while avoiding false positives. This mirrors real-world engineering outcomes: missing critical issues is costly, but noisy reviews are also penalized.

### Design Goals

- **Reproducible benchmark** for "agentic code review": the agent sees a full file and a diff, submits structured actions with line numbers and labels, and the environment grades against ground truth.
- **Deterministic** tasks, graders, and reward shaping.
- **Robust** against malformed model output, provider failures, and schema variations.
- **Dense scoring** with step-level rewards and end-of-episode closure.

---

## Package Structure

```
code-review-env/
├── server.py              # FastAPI app (/reset, /step, /state, /health)
├── inference.py           # Baseline inference runner (LLM + benchmark modes)
├── env/
│   ├── models.py          # Pydantic data models (actions, observations)
│   ├── environment.py     # Core environment loop (reset, step)
│   ├── reward_engine.py   # Dense reward computation & shaping
│   ├── state_manager.py   # Observation & step tracking
│   ├── graders/
│   │   ├── base_grader.py # Abstract grader interface
│   │   ├── grader_easy.py
│   │   ├── grader_medium.py
│   │   └── grader_hard.py
│   └── tasks/
│       ├── task_easy.py   # "summarize_adjacent_deltas" (3 bugs)
│       ├── task_medium.py # "get_profile_handler" (4 security issues)
│       └── task_hard.py   # "build_user_summaries" (4 bugs + 1 red herring)
└── tests/
    ├── conftest.py
    ├── test_api.py
    ├── test_environment.py
    ├── test_graders.py
    ├── test_rewards.py
    ├── test_inference_helpers.py
    ├── test_advanced_cases.py
    ├── test_comprehensive.py
    └── test_performance_quality.py
```

---

## Observation Space

| Field | Type | Description |
|---|---|---|
| `task_id` | `str` | Task identifier (`easy`, `medium`, `hard`) |
| `language` | `str` | Language of the code under review (always `python`) |
| `pr_title` | `str` | Pull request title |
| `pr_description` | `str` | Pull request description |
| `code_diff` | `str` | Unified diff of the changes |
| `full_file` | `str` | Full file contents for context |
| `existing_comments` | `list` | Comments the agent has already made (`ReviewComment`) |
| `step_number` | `int` | Current step number (1-indexed) |
| `max_steps` | `int` | Maximum steps allowed for the task |
| `review_status` | `str` | One of `pending`, `in_review`, `submitted` |

## Action Space

| Operation | Parameters |
|---|---|
| `add_comment` | `line_number` (required), `severity`, `category`, `message` |
| `approve` | `summary` (required) |
| `request_changes` | `summary` (required) |
| `done` | (no parameters) |

### Action Schema Compatibility

Two action shapes are supported and auto-normalized:

```jsonc
// Native format
{"operation": "add_comment", "line_number": 18, "severity": "major", "category": "bug", "message": "..."}

// Alternate format
{"action_type": "comment", "line": 18, "severity": "major", "category": "bug", "comment": "..."}
```

---

## Task Definitions

### Easy — `summarize_adjacent_deltas`

**Domain:** Simple list processing utility

| Canonical Line | Severity | Category | Bug Description |
|------|----------|----------|-----|
| 18 | major | bug | Off-by-one / out-of-range access via `items[i+1]` |
| 21 | major | bug | Missing null check for `Optional[Item]` |
| 25 | minor | bug | Assignment inside conditional (invalid/wrong) |

**Expected behavior:** Report the 3 real bugs. Avoid noise (unused variable / style) — false positives penalize.

---

### Medium — `get_profile_handler`

**Domain:** Web handler with security issues (SQL, XSS, IDOR, secrets)

| Canonical Line | Severity | Category | Bug Description |
|------|----------|----------|-----|
| 20 | major | security | Hardcoded secret in handler |
| 21 | critical | security | SQL injection via string concatenation |
| 23 | major | security | XSS via untrusted input rendered to HTML |
| 24 | critical | security | IDOR: missing authorization check |

**Expected behavior:** Prioritize security correctness; do not invent extra runtime errors.

---

### Hard — `build_user_summaries` (Async)

**Domain:** Async background service building summaries + caching + audit log

| Canonical Line | Severity | Category | Bug Description |
|------|----------|----------|-----|
| 21 | major | bug | Resource leak: `audit_fh` opened but not closed |
| 25 | major | performance | N+1 query: per-user order fetch in loop |
| 29 | critical | bug | Async race on shared global mutable `_CACHE` |
| 34 | major | bug | Silent exception swallowing (bare `except: pass`) |

> ⚠️ **Red herring:** One line intentionally looks suspicious but is harmless; flagging it incurs extra penalty (`-0.20`).

---

## Reward Function

| Condition | Reward |
|---|---:|
| `add_comment` within ±5 lines of a real bug (first time) | +0.15 |
| Severity matches exactly (bonus) | +0.05 |
| Category matches exactly (bonus) | +0.05 |
| Duplicate comment on already-credited bug | -0.05 |
| Comment matches red herring | -0.20 |
| False positive (no match) | -0.10 |
| `approve` while critical/major bugs remain | -0.50 |
| `approve` when no critical/major remain | +0.10 |
| `request_changes` with evidence (`bugs_found > 0`) | +0.05 |
| `request_changes` without evidence | -0.05 |
| `done` | Final grader score (plus efficiency bonus if applicable) |
| Step limit exceeded without `done` | -0.20 added to final score |
| Efficiency bonus at `done` (steps < 60% max_steps AND final_score > 0.8) | +0.10 |

### Why `request_changes` Can Be Suboptimal

The environment supports `request_changes` / `approve`, but they can be lower value than a clean `done` in certain scoring setups. The inference runner converts both to `done` for consistency.

---

## Grader Design

The grader computes **(weighted) F1** using severity-based weights:

| Severity | Weight |
|----------|--------|
| critical | 3 |
| major | 2 |
| minor | 1 |
| nit | 0.5 |

Precision is influenced by total comments (false positives reduce score), while recall measures coverage of real bugs (excluding red herrings). Scoring is **fully deterministic**.

---

## Inference Runner (`inference.py`)

### Responsibilities

1. Connect to environment server
2. Reset each task via `POST /reset`
3. Iterate step loop up to `max_steps`
4. Produce one action JSON per step
5. Submit to `POST /step`
6. Print mandatory logs: `[START]` / `[STEP]` / `[END]`

### Modes

| Mode | Env Variable | LLM Required | Deterministic |
|------|-------------|--------------|---------------|
| **LLM** | `REVIEW_STRATEGY=llm` | Yes (HF Router) | No |
| **Benchmark** | `REVIEW_STRATEGY=benchmark` | No | Yes |

### Sanitization & Repair Pipeline

For each produced action:
1. **Validate** operation type
2. **Clamp** `line_number` to valid range
3. **Normalize** severity / category
4. **Calibrate** labels from message text
5. **Map** canonical lines by semantic key
6. **Convert** `approve` / `request_changes` → `done`

### Semantic Key System

| Key | Task |
|-----|------|
| `off_by_one` | easy |
| `missing_null_check` | easy |
| `assignment_in_condition` | easy |
| `hardcoded_secret` | medium |
| `sql_injection` | medium |
| `xss` | medium |
| `idor` | medium |
| `resource_leak` | hard |
| `n_plus_one` | hard |
| `race_condition` | hard |
| `silent_swallow` | hard |

These drive: canonical line mapping, required-findings tracking, deterministic fallback ordering.

### Early Stop

Once all required finding keys are submitted for a task → instantly emit `{"operation": "done"}`. Prevents model from padding with extra (penalized) findings.

### Provider Failure Fallback

On `401` / `402` / `403` or keywords `"depleted"` / `"credits"` / `"unauthorized"`:
- Automatically emit deterministic remaining findings
- Complete episode with maximum score

---

## Server (`server.py`)

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Landing page (informational) |
| `GET` | `/health` | Health check (returns 200) |
| `POST` | `/reset` | Reset environment with `task_id` |
| `POST` | `/step` | Submit action, receive observation + reward |
| `GET` | `/state` | Current environment state (debug) |

---

## Environment Internals

```
Environment
  └─► StateManager (observation, comments, step tracking)
        └─► RewardEngine (action ↔ truth comparison, dense rewards)
              └─► Graders (per-task ground truth, deterministic scoring)
```

---

## Setup Instructions

```bash
python -m venv .venv
. .venv/bin/activate  # on Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest tests -v
uvicorn server:app --host 0.0.0.0 --port 7860
```

## Docker Instructions

```bash
docker build -t code-review-env .
docker run -p 7860:7860 code-review-env
```

## HF Space Deployment

Link: https://deepparmar-code-review.hf.space

---

## Testing

### Run Tests

```bash
python -m pytest tests -v
```

### Test Coverage

| Test File | Coverage Area |
|-----------|---------------|
| `test_api.py` | API endpoint behavior |
| `test_environment.py` | Environment state transitions |
| `test_graders.py` | Grader correctness & determinism |
| `test_rewards.py` | Reward shaping correctness |
| `test_inference_helpers.py` | Prompt loading, normalization, mapping |
| `test_advanced_cases.py` | Edge cases & error handling |
| `test_comprehensive.py` | End-to-end scenarios |
| `test_performance_quality.py` | Performance & quality assertions |

### Validation Snapshot

- `pytest tests -v` → **41 passed**
- Known non-fatal warning: httpx `DeprecationWarning` (dependency-level)

---

## Baseline Scores

| Task | Benchmark Mode | LLM Mode |
|------|---------------|----------|
| easy | **1.750** ✅ | 1.750 |
| medium | **2.100** ✅ | Variable |
| hard | **2.100** ✅ | 2.100 (with fallback) |

---

## Security

- `HF_TOKEN` must never be committed; set as environment variable only.
- Inference runner requires exact JSON output; malformed output defaults to `done`.
- FastAPI / Pydantic validates all request bodies.

---

## Extending the Environment

1. **New task:** Create `env/tasks/task_new.py` → provide `full_file`, `code_diff`, `ground_truth`.
2. **Canonical mapping:** Extend `_CANONICAL_LINE_MAP`, `_REQUIRED_FINDING_KEYS`, `_KEY_FALLBACK_ACTION`.
3. **New grader:** Add under `env/graders/` — ensure determinism and unit tests.
