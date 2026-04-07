---
title: Code Review OpenEnv
emoji: "\U0001F50E"
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

## Environment Overview
This repository contains **Code Review OpenEnv**, a production-grade evaluation environment where an AI agent plays the role of a code reviewer. The agent receives buggy Python pull-request content, leaves line-specific review comments, and is scored on finding real bugs while avoiding false positives. This mirrors real-world engineering outcomes: missing critical issues is costly, but noisy reviews are also penalized.

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

## Task Descriptions
**Easy**: A small data-processing utility with 3 real bugs (indexing off-by-one, missing null check, and an error-prone conditional pattern). Expected baseline score: ~0.65–0.75.

**Medium**: A web handler with 4 security vulnerabilities (SQL injection, hardcoded secret, missing input validation leading to XSS risk, and an IDOR). Expected baseline score: ~0.40–0.55.

**Hard**: An async service function with 4 architectural issues (N+1 calls, async race condition on shared state, resource leak, and silent exception swallowing) plus 1 red herring trap. Expected baseline score: ~0.15–0.30.

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

## Grader Design
The grader computes **(weighted) F1** using severity-based weights (critical=3, major=2, minor=1, nit=0.5). Precision is influenced by total comments (false positives reduce score), while recall measures coverage of real bugs (excluding red herrings). Scoring is deterministic.

## Setup Instructions
```bash
python -m venv .venv
. .venv/bin/activate  # on Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest code-review-env/tests -v
uvicorn server:app --host 0.0.0.0 --port 7860
```

## Docker Instructions
```bash
docker build -t code-review-env .
docker run -p 7860:7860 code-review-env
```

## HF Space Deployment
Link: (add your deployed Space URL here)

## Baseline Scores
| Task | Model | Score |
|---|---|---:|
| easy | `Qwen/Qwen2.5-72B-Instruct` | TBD |
| medium | `Qwen/Qwen2.5-72B-Instruct` | TBD |
| hard | `Qwen/Qwen2.5-72B-Instruct` | TBD |

