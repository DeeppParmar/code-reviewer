---
title: Code Review OpenEnv
emoji: "\U0001F50E"
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Code Review OpenEnv

A deterministic, OpenEnv-style benchmark environment for evaluating AI code review agents. The agent receives buggy Python pull requests, leaves structured review comments, and is graded on precision and recall against ground-truth bugs.

**Live Space:** https://deepparmar-code-review.hf.space

---

## Architecture Blueprint & Documentation
For a complete, highly detailed report containing logic flows, error handling protocols, strict bounds verification, and testing infrastructure mechanisms.

---

## Key Features

- **FastAPI server** with `reset` / `step` / `state` endpoints
- **Three difficulty tiers** — `easy` · `medium` · `hard`
- **Deterministic grading** with dense, step-level rewards
- **Dual-mode inference** — LLM mode (HF Router) and benchmark mode (perfect deterministic)
- **Fault-tolerant** — handles malformed output, schema variants, and provider failures (401/402/403)

---

## Observation Space

| Field | Type | Description |
|---|---|---|
| `task_id` | `str` | `easy`, `medium`, or `hard` |
| `pr_title` / `pr_description` | `str` | Pull request metadata |
| `full_file` | `str` | Complete file under review |
| `code_diff` | `str` | Unified diff |
| `existing_comments` | `list` | Agent's prior comments |
| `step_number` / `max_steps` | `int` | Step progress |

## Action Space

| Operation | Parameters |
|---|---|
| `add_comment` | `line_number`, `severity`, `category`, `message` |
| `approve` | `summary` |
| `request_changes` | `summary` |
| `done` | _(none)_ |

---

## Tasks

| Task | Domain | Bugs | Description |
|------|--------|------|-------------|
| **easy** | List processing | 3 | Off-by-one, null check, bad conditional |
| **medium** | Web handler | 4 | SQL injection, XSS, IDOR, hardcoded secret |
| **hard** | Async service | 4 + 1 trap | Resource leak, N+1, race condition, silent swallow |

## Reward Function

| Condition | Reward |
|---|---:|
| Correct bug comment (first match ±5 lines) | +0.15 |
| Severity / category match bonus (each) | +0.05 |
| Duplicate comment | −0.05 |
| False positive | −0.10 |
| Red herring match | −0.20 |
| `done` | Final grader score |
| Efficiency bonus (fast + high score) | +0.10 |

**Grader:** Weighted F1 (`critical=3, major=2, minor=1, nit=0.5`). Deterministic.

---

## Scores

| Task | Benchmark Mode | LLM Mode |
|------|:-:|:-:|
| easy | **1.000** | 1.000 |
| medium | **1.000** | 1.000 |
| hard | **1.000** | 1.000 |

---

## Quick Start

```bash
pip install -r requirements.txt
python -m pytest code-review-env/tests -q      # 52 passed
uvicorn server:app --host 0.0.0.0 --port 7860  # run server
```

```bash
# Docker
docker build -t code-review-env .
docker run -p 7860:7860 code-review-env
```

### Run Inference

```bash
# Benchmark mode (deterministic, no LLM)
REVIEW_STRATEGY=benchmark TASK_IDS=easy,medium,hard python inference.py

# LLM mode
HF_TOKEN=<token> REVIEW_STRATEGY=llm python inference.py
```

---

## Validation

- `pytest` → **52 passed**
- `openenv validate` → **Ready for multi-mode deployment**
- All live endpoints return HTTP 200
