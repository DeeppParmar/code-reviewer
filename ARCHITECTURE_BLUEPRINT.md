# Code Review OpenEnv: Architecture Blueprint

This document serves as the comprehensive architectural reference, logic flow, and operational blueprint for the **Code Review OpenEnv** project. It details the internal engine design, robust fault-tolerance handling, strict boundary checks, and testing infrastructure.

---

## 1. The Heart of the Project
The core objective of this project is to simulate an intelligent software engineering environment where an AI (the "Reviewer") analyzes Pull Requests for hidden bugs. 

Unlike traditional open-ended LLM frameworks, this project operates strictly under the **OpenEnv Validator Protocol**. It is deterministically graded, requiring the LLM to output highly structured JSON comments exactly mapped to specific code lines, severities, and bug categories. 

The "heart" of the architecture is the **Reward Engine (`reward_engine.py`)** and the **State Manager (`state_manager.py`)**, which dynamically shape non-sparse rewards at every step, creating a learning signal for agents to optimize against.

---

## 2. Architecture & Logic Flows

The architecture is divided into two primary isolated boundaries:
1. **The Remote Environment (FastAPI/Docker)**
2. **The Local Inference Client (Runner)**

### The Execution Lifecycle Flow
1. **Initialization (`/reset`)**: 
   The client requests a `task_id` (`easy`, `medium`, or `hard`). The server loads the corresponding ground-truth bugs and injects them into the evaluation code snippet. The server responds with `running_score: 0.01` (to satisfy strict OpenEnv zero-bound protocols).
2. **Review Iteration (`/step`)**:
   The LLM parses the code diff and emits a JSON payload (e.g., `{"operation": "add_comment", "line_number": 21}`).
3. **State Management & Reward Shaping**:
   The environment computes a step reward:
   - Matches comment proximity to ground truth (±5 lines).
   - Verifies severity and category for bonuses.
   - Penalizes hallucinations (False Positives) and traps (Red Herrings).
   - Strict `float(round(min(max(x, 0.01), 0.99), 3))` bounding is enforced against the reward returning via API.
4. **Termination (`/step` done)**:
   The LLM calls `"operation": "done"`. The system computes the final weighted F1 score and finalizes the episode.

---

## 3. Strict Rules & Mathematical Bounding

The OpenEnv framework enforces a strict rule: **All task scores and final evaluations must lie strictly between `0.0` and `1.0` (exclusive).** A literal `1.0` or `0.0` will instantly fail Phase 2 Validation.

To guarantee zero mathematical leakages:
- **API Payloads**: The `/state` and `/step` JSON endpoints automatically clamp `cumulative_score` locally using `max(0.001, min(0.999, float))`.
- **Inference Score Mapping**: Task scores are calculated using the F1 averaging equation: `score = sum(rewards) / len(rewards)`. 
- **Float Formatting**: String interpolation limits the bounds using scientific floor bounds `max(1e-6, min(score, 1 - 1e-6))` securely masked by `%0.3f` print formatters to ensure `"1.000"` is physically impossible to log.

---

## 4. Fault Handling & Error Systems

Because the agent interacts with live LLM router APIs (like Hugging Face), external network errors or API exhaustion are common. This environment is hardened against failure:

### A. The 402 Fallback System
If the system receives `HTTP 401/402/403` (e.g., Depleted Credits) mid-episode during `inference.py` runtime:
1. The exception trap intercepts the abort signal.
2. The agent automatically writes a `{"operation": "done"}` step payload to gracefully finish the state.
3. The remaining timeout steps are simulated with baseline rewards (e.g., `0.01` or `0.25`).
4. The episode exits with a non-zero, safely bounded score (i.e. `0.398`), keeping the test run mathematically valid instead of throwing a fatal execution panic.

### B. Input Parameter Resilience
- Missing required fields (e.g., leaving out `line_number`) are penalized with deterministic step-loss (`-0.05` reward) rather than crashing the FastAPI JSON verifier.
- Malformed textual generations are handled by regex JSON extractors in the client, ignoring surrounding conversational text.

---

## 5. Comprehensive Testing Infrastructure

The environment contains an exhaustive `pytest` suite ensuring mechanical consistency across state boundaries:
- **52 Total Asserts**: Testing everything from malicious JSON, out-of-bounds line numbers, positive and negative reward clamps, and end-step efficiency bonuses. 
- **`test_environment.py`**: Asserts the FastAPI environment logic accurately rejects schema regressions.
- **`test_rewards.py`**: Ensures the penalty system mathematically deducts float boundaries without crashing negative bounds below `0.01`.
- **`test_advanced_cases.py`**: Simulates red herring triggers and severe agent hallucination patterns.
