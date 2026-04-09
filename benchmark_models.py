import json
import os
import subprocess
import time
from typing import Dict, Any

MODELS_TO_BENCHMARK = [
    "Qwen/Qwen2.5-72B-Instruct",
    "meta-llama/Llama-3-70b-chat-hf",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "google/gemma-2-27b-it",
    "deepseek-ai/DeepSeek-Coder-V2-Instruct"
]

RESULTS_FILE = "benchmark_results.json"

def run_benchmark(model: str) -> Dict[str, Any]:
    print(f"\n[{model}] Starting benchmark...")
    
    # We orchestrate inference.py securely in a subprocess so failures
    # don't panic the main orchestrator script.
    env = os.environ.copy()
    env["HF_MODEL"] = model
    env["REVIEW_STRATEGY"] = "llm"
    env["TASK_IDS"] = "easy,medium,hard"

    try:
        # Run inference and capture stdout to evaluate scores
        result = subprocess.run(
            ["python", "code-review-env/inference.py"], 
            env=env, 
            capture_output=True, 
            text=True, 
            timeout=300
        )
        stdout = result.stdout
        
        # Parse final scores from stdout [END] logs
        scores = {}
        for line in stdout.splitlines():
            if line.startswith("[END]"):
                parts = line.split()
                task_id = "unknown"
                score = 0.0
                # We need to figure out which task this is, inference logs print [START] with task=easy
                # Let's extract the score.
                for part in parts:
                    if part.startswith("score="):
                        score = float(part.split("=")[1])
                scores["last_task_score"] = score # simplified extraction for benchmark runner
                
        # If API depletion occurred, we save the resilient score to CSV
        if "402" in stdout or "Depleted" in stdout:
            print(f"[{model}] API Depletion detected. Saving partial fallback score.")
            scores["error"] = "API Credit Depletion"
            
        print(f"[{model}] Benchmark complete. Score: {scores.get('last_task_score', 0.0)}")
        return {"scores": scores, "raw_output": stdout, "success": True}

    except subprocess.TimeoutExpired:
        print(f"[{model}] Benchmark timed out.")
        return {"error": "timeout", "success": False}
    except Exception as e:
        print(f"[{model}] Benchmark crashed: {e}")
        return {"error": str(e), "success": False}

def main():
    print("=== OpenEnv Code Review Model Benchmarker ===")
    
    results = {}
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r") as f:
            results = json.load(f)

    for i, model in enumerate(MODELS_TO_BENCHMARK):
        if model in results and results[model].get("success") == True:
            print(f"Skipping {model}, already benchmarked.")
            continue
            
        res = run_benchmark(model)
        results[model] = res
        
        # Save progressively
        with open(RESULTS_FILE, "w") as f:
            json.dump(results, f, indent=2)
            
        # Give API a break
        if i < len(MODELS_TO_BENCHMARK) - 1:
            print(f"Cooling down HF router before next model (10 seconds)...")
            time.sleep(10)

    print("\n=== Benchmarking Cycle Complete ===")
    print(f"Results saved to {RESULTS_FILE}")

if __name__ == "__main__":
    main()
