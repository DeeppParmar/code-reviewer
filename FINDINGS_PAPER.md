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

> **This section is populated from real benchmark runs.**
> Execute `python benchmark_models.py` to generate `benchmark_results.csv` and `benchmark_results.json`, then update this section with actual data.

*(Results will be inserted here after live benchmark execution.)*

---

## 5. Discussion

### Expected Capability Gaps

Based on architectural analysis of the test environment:

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
