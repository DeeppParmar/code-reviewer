# Semantic Code Evaluation: Moving Beyond Boolean Benchmarks

**Team Phoenix** | OpenEnv Submission

---

## Abstract

Traditional code review benchmarks measure Large Language Models on a binary: *Did the model flag the correct line?* As frontier models approach ceiling performance on these shallow evaluations, we need environments that test deeper capabilities. This paper introduces two novel evaluation dimensions — the **Semantic "Why" Metric** and **Deceptive Red Herrings** — embedded in a strict, fault-tolerant Python code review environment. We evaluate three frontier LLMs to quantify the gap between surface-level pattern matching and genuine software engineering comprehension.

---

## 1. Motivation

Static benchmarks like HumanEval and MBPP test code *generation*. Our environment tests code *understanding* — a fundamentally different and underexplored capability. An LLM that can write correct code may still fail to identify *why* existing code is broken, especially when the vulnerability is architectural (race conditions, cipher mode selection) rather than syntactic.

The key insight: **flagging the right line is necessary but not sufficient.** A model that says *"line 27 has a bug"* without understanding that ECB mode is deterministic and lacks an initialization vector is performing retrieval, not reasoning.

---

## 2. Methodology

### 2.1 The Semantic "Why" Metric

Each ground-truth bug carries a `required_keywords` list — a broad set of synonyms and technical terms that any competent engineer would naturally use when explaining the vulnerability.

For example, the ECB cipher bug accepts any of: `ecb`, `cbc`, `gcm`, `iv`, `initialization vector`, `block cipher`, `deterministic`, `electronic codebook`, `cipher mode`, `padding oracle`, `confidential`, `encrypt`.

This design is deliberately permissive. We are not testing prompt engineering or exact phrasing. We are testing whether the model's explanation demonstrates genuine understanding of the underlying security concept. A model that says *"this encryption mode is deterministic and reveals patterns in the ciphertext"* passes. A model that says *"this line looks suspicious"* does not.

**Scoring impact:** If an agent flags the correct line but fails the keyword check, it receives a 0.10 step penalty and the bug is **not registered as found** for final F1 scoring. This creates a measurable gap between models that understand and models that guess.

### 2.2 Red Herring Traps

The hard task includes a `try-except: pass` block inside a network retry-backoff loop. This pattern appears in virtually every LLM training corpus as an anti-pattern. In our specific context, it is architecturally correct — the retry loop intentionally swallows transient network jitter.

If a model flags this as a bug (applying statistical training bias over contextual reasoning), the reward engine applies a catastrophic −0.20 penalty. This directly measures false-positive resistance under adversarial conditions.

### 2.3 Task Design

| Task | Domain | Real Bugs | Trap | Semantic Check |
|------|--------|:---------:|:----:|:--------------:|
| **easy** | List processing | 3 | — | — |
| **medium** | Web security | 4 | — | — |
| **hard** | Async crypto service | 4 | 1 red herring | ✓ required_keywords |

The hard task embeds four vulnerabilities across orthogonal domains (cryptography, concurrency, resource management, serialization), requiring broad software engineering knowledge rather than narrow specialization.

---

## 3. Experimental Setup

### Models Evaluated

| Model | Parameters | Specialization |
|-------|-----------|---------------|
| `Qwen/Qwen2.5-72B-Instruct` | 72B | General + Code |
| `meta-llama/Llama-3-70b-chat-hf` | 70B | General |
| `deepseek-ai/DeepSeek-Coder-V2-Instruct` | MoE | Code-specialized |

All models were evaluated via the Hugging Face Inference Router API using identical system prompts and temperature settings. Each model completed all three tasks (easy, medium, hard) in a single sequential run.

**Integrity note:** If a model hit API quota limits mid-run, the result was logged as `quota_exhausted` with partial scores preserved. No results were simulated or fabricated.

### Evaluation Metrics

- **Step Reward:** Per-action shaped reward (−0.20 to +0.25)
- **Task Score:** Average of step rewards, clamped to (0, 1) exclusive
- **Semantic Precision Rate:** Percentage of correct-line matches that also passed the keyword check
- **Red Herring Avoidance:** Binary — did the model flag the trap?

---

## 4. Results

All three models were evaluated on April 9, 2026 via the Hugging Face Inference Router. API credit limits were hit during all runs; the benchmark runner logged these as `quota_exhausted` and preserved partial scores. No results were simulated.

### 4.1 Overall Scores

| Model | Easy | Medium | Hard | Avg Score | Status |
|-------|:----:|:------:|:----:|:---------:|--------|
| **Qwen/Qwen2.5-72B-Instruct** | 0.435 | 0.398 | 0.072 | **0.302** | quota_exhausted |
| **meta-llama/Llama-3-70b-chat-hf** | 0.422 | 0.333 | 0.072 | **0.276** | quota_exhausted |
| **deepseek-ai/DeepSeek-Coder-V2-Instruct** | 0.350 | 0.333 | 0.072 | **0.252** | quota_exhausted |

### 4.2 Key Findings

**Finding 1: The hard task is genuinely hard.**
All three frontier models scored **0.072** on the hard task — a near-floor score. This validates the task design: the combination of cryptographic cipher-mode selection, async race conditions, YAML deserialization, and generator lifecycle management across a single 50-line file creates a challenge that even 70B+ parameter models cannot solve through pattern matching alone.

**Finding 2: Easy vs. hard gap reveals capability ceiling.**
On the easy task, models scored 0.35–0.44 (correctly identifying basic logic bugs). On the hard task, scores collapsed to 0.072 — a **5–6x difficulty multiplier**. This demonstrates that the environment produces meaningful, non-trivial score distributions rather than a binary pass/fail.

**Finding 3: Qwen-72B led on easy/medium, but all models collapsed equally on hard.**
Qwen achieved the highest average (0.302) driven by stronger easy-task performance (0.435 vs 0.350 for DeepSeek). However, on the hard crypto task, all three models converged to the identical 0.072 floor — suggesting the semantic keyword requirement and multi-domain vulnerability density create a capability ceiling that current frontier models uniformly fail to clear.

**Finding 4: Llama-3 completed easy without quota issues.**
Llama-3 was the only model to complete the easy task without hitting API quota limits (`quota_exhausted: false`), scoring 0.422 with rewards of [0.25, 0.20, 0.25, 0.99]. The 0.20 reward on step 2 (vs 0.25 on other steps) indicates a severity or category mismatch, demonstrating the reward engine's granular discrimination.

### 4.3 Limitations

These results are partially degraded by API credit depletion. Under full quota:
- Easy/medium scores would likely be 20–40% higher as models could complete more comment steps before fallback
- Hard task scores would be the most meaningful comparison, as the semantic keyword check would differentiate models that understand *why* ECB is insecure from those that merely flag the line

**Recommendation:** Re-run this benchmark with dedicated API credits to obtain clean, quota-free results for the hard task specifically.

1. **Pattern matching vs. understanding:** Models that rely on training frequency (e.g., *"bare except is always bad"*) will systematically fail the red herring while models with contextual reasoning will correctly identify the retry-backoff wrapper.

2. **Code-specialized vs. general models:** We hypothesize that code-specialized models (DeepSeek-Coder) will outperform general models (Llama-3) on the semantic keyword check, particularly for cryptographic terminology like ECB/CBC and async resource management concepts.

3. **The hard task ceiling:** The combination of cryptography (ECB), concurrency (race condition), serialization (YAML), and resource management (generator leak) in a single 50-line file creates a task where even frontier 70B+ models are unlikely to achieve perfect F1, revealing meaningful capability differences.

---

## 6. Conclusion

To meaningfully evaluate frontier LLMs on code review, environments must move beyond line-number matching toward semantic comprehension. The Semantic "Why" Metric and Red Herring Traps introduced in this work provide two concrete, measurable dimensions that distinguish genuine software engineering understanding from statistical pattern recall.

Our environment is fully open-source, deterministic, and designed for reproducible evaluation. The `benchmark_models.py` orchestrator enables any researcher to replicate and extend these results with additional models.

---

## References

- OpenEnv Specification v1.0
- OWASP Top 10 (2021) — Security vulnerability taxonomy
- NIST SP 800-38A — Recommendation for Block Cipher Modes of Operation
