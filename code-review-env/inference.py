"""Baseline inference script that runs an LLM against the environment server.

Outputs mandatory stdout logs:
  [START] ...
  [STEP] ...
  [END] ...
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from openai import OpenAI


def _fmt_bool(v: bool) -> str:
    """Format booleans as lowercase strings."""

    return "true" if v else "false"


def _safe_json_loads(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Parse a JSON object from model text.

    Args:
        text: Raw model output.

    Returns:
        Tuple of (parsed_object_or_none, error_or_none).
    """

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj, None
        return None, "Model output was not a JSON object"
    except Exception as e:
        return None, str(e)


def _print_start(task_name: str, env_name: str, model_name: str) -> None:
    """Print the mandatory START line."""

    print(f"[START] task={task_name} env={env_name} model={model_name}")


def _print_step(step: int, action_str: str, reward: float, done: bool, error: Optional[str]) -> None:
    """Print the mandatory STEP line."""

    err = error if error else "null"
    print(f"[STEP] step={step} action={action_str} reward={reward:.2f} done={_fmt_bool(done)} error={err}")


def _print_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    """Print the mandatory END line."""

    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={_fmt_bool(success)} steps={steps} score={score:.3f} rewards={rewards_str}")


def _build_system_prompt() -> str:
    """Build the system prompt for the model."""

    return (
        "You are an expert Python code reviewer. You will receive buggy code. "
        "Your job is to identify real bugs by adding comments with exact line numbers. "
        "Be precise — false positives are penalized. When done reviewing, call done."
    )


def _build_user_message(observation: Dict[str, Any]) -> str:
    """Build the user message from observation."""

    return (
        "Review this pull request.\n\n"
        f"step_number: {observation.get('step_number')}\n"
        f"max_steps: {observation.get('max_steps')}\n\n"
        "full_file:\n"
        f"{observation.get('full_file')}\n\n"
        "code_diff:\n"
        f"{observation.get('code_diff')}\n\n"
        "existing_comments (JSON):\n"
        f"{json.dumps(observation.get('existing_comments', []))}\n\n"
        "Respond with EXACTLY one JSON object representing the next action.\n"
        "Examples:\n"
        "{\"operation\":\"add_comment\",\"line_number\":12,\"severity\":\"major\",\"category\":\"bug\",\"message\":\"...\"}\n"
        "{\"operation\":\"done\"}\n"
    )


def _call_env_reset(client: httpx.Client, base_url: str, task_id: str) -> Dict[str, Any]:
    """Call POST /reset and return observation JSON."""

    r = client.post(f"{base_url}/reset", json={"task_id": task_id}, timeout=30.0)
    r.raise_for_status()
    return r.json()


def _call_env_step(client: httpx.Client, base_url: str, action: Dict[str, Any]) -> Dict[str, Any]:
    """Call POST /step and return step result JSON."""

    r = client.post(f"{base_url}/step", json=action, timeout=30.0)
    r.raise_for_status()
    return r.json()


def _llm_next_action(
    llm: OpenAI,
    model_name: str,
    history: List[Dict[str, str]],
) -> Tuple[Dict[str, Any], Optional[str], str]:
    """Ask the model for the next action.

    Args:
        llm: OpenAI client configured with base_url and api_key.
        model_name: Model identifier.
        history: Chat messages list.

    Returns:
        Tuple of (action_dict, parse_error_or_none, raw_text).
    """

    resp = llm.chat.completions.create(model=model_name, messages=history, temperature=0.2)
    text = (resp.choices[0].message.content or "").strip()
    action, err = _safe_json_loads(text)
    if action is None:
        return {"operation": "done"}, err, text
    return action, None, text


def run_task(task_id: str, *, env_base_url: str, model_name: str, hf_token: str, timeout_s: int) -> None:
    """Run one task episode end-to-end and print required logs."""

    env_name = "code-review-env"
    _print_start(task_id, env_name, model_name)

    rewards: List[float] = []
    score: float = 0.0
    success: bool = False
    steps_taken: int = 0

    start_t = time.time()
    try:
        llm = OpenAI(base_url=os.getenv("API_BASE_URL", env_base_url), api_key=hf_token)
        with httpx.Client() as http:
            obs = _call_env_reset(http, env_base_url, task_id)

            history: List[Dict[str, str]] = [{"role": "system", "content": _build_system_prompt()}]
            max_steps = int(obs.get("max_steps", 1))

            for step in range(1, max_steps + 1):
                if time.time() - start_t > float(timeout_s):
                    action = {"operation": "done"}
                    result = _call_env_step(http, env_base_url, action)
                    reward = float(result["reward"])
                    done = bool(result["done"])
                    info = result["info"]
                    score = float(info.get("current_score", score))
                    rewards.append(reward)
                    steps_taken = step
                    _print_step(step, json.dumps(action, separators=(",", ":")), reward, done, "timeout")
                    break

                history.append({"role": "user", "content": _build_user_message(obs)})
                action, parse_err, raw_text = _llm_next_action(llm, model_name, history)
                history.append({"role": "assistant", "content": raw_text})

                result = _call_env_step(http, env_base_url, action)
                obs = result["observation"]
                reward = float(result["reward"])
                done = bool(result["done"])
                info = result["info"]
                score = float(info.get("current_score", score))

                rewards.append(reward)
                steps_taken = step
                _print_step(step, json.dumps(action, separators=(",", ":")), reward, done, parse_err or info.get("error"))
                if done:
                    break

            success = score >= 0.5
    except Exception as e:
        success = False
        if steps_taken == 0:
            steps_taken = 1
        _print_step(steps_taken, "{\"operation\":\"done\"}", 0.00, True, str(e))
    finally:
        _print_end(success, steps_taken, score, rewards)


def main() -> int:
    """Entry point for baseline inference over easy/medium/hard tasks."""

    env_base_url = os.getenv("ENV_BASE_URL", "http://127.0.0.1:7860")
    model_name = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("HF_TOKEN is required", file=sys.stderr)
        return 2

    os.environ.setdefault("API_BASE_URL", "https://router.huggingface.co/v1")

    for task_id, timeout_s in [("easy", 360), ("medium", 360), ("hard", 360)]:
        run_task(task_id, env_base_url=env_base_url, model_name=model_name, hf_token=hf_token, timeout_s=timeout_s)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

