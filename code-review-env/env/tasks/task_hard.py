"""Hard task definition.

Provides a realistic async Python service function with exactly 4 real bugs and
1 red herring, plus ground truth metadata with exact line numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from env.models import GroundTruthBug


@dataclass(frozen=True)
class TaskSpec:
    """Container for a task specification used by the environment."""

    task_id: str
    max_steps: int
    pr_title: str
    pr_description: str
    full_file: str
    code_diff: str
    ground_truth: List[GroundTruthBug]


def get_task() -> TaskSpec:
    """Return the hard task specification (buggy code + ground truth)."""

    full_file = "\n".join(
        [
            "from __future__ import annotations",
            "",
            "import asyncio",
            "from typing import Dict, List, Optional",
            "",
            "",
            "class FakeAsyncDB:",
            '    """Simplified async DB facade used by a background service."""',
            "",
            "    async def fetch_user(self, user_id: str) -> Dict[str, str]:",
            "        await asyncio.sleep(0)",
            "        return {\"id\": user_id, \"email\": f\"{user_id}@example.com\"}",
            "",
            "    async def fetch_orders_for_user(self, user_id: str) -> List[Dict[str, str]]:",
            "        await asyncio.sleep(0)",
            "        return [{\"id\": \"o1\", \"amount\": \"10\"}]",
            "",
            "",
            "_CACHE: Dict[str, Dict[str, str]] = {}",
            "",
            "",
            "async def build_user_summaries(user_ids: List[str]) -> Dict[str, Dict[str, str]]:",
            '    """Build per-user summaries by fetching user + order details asynchronously."""',
            "    db = FakeAsyncDB()",
            "    summaries: Dict[str, Dict[str, str]] = {}",
            "    audit_fh = open(\"audit.log\", \"a\", encoding=\"utf-8\")",
            "    try:",
            "        for uid in user_ids:",
            "            user = await db.fetch_user(uid)",
            "            orders = await db.fetch_orders_for_user(uid)",
            "            total_amount = sum(int(o[\"amount\"]) for o in orders)",
            "            summaries[uid] = {\"email\": user[\"email\"], \"total\": str(total_amount)}",
            "            _CACHE[uid] = summaries[uid]",
            "            audit_fh.write(f\"built summary for {uid}\\n\")",
            "        suspicious__nonce = \"ok\"",
            "        return summaries",
            "    except:",
            "        pass",
            "",
        ]
    )

    code_diff = "\n".join(
        [
            "--- a/service.py",
            "+++ b/service.py",
            "@@",
            "+async def build_user_summaries(user_ids: List[str]) -> Dict[str, Dict[str, str]]:",
            "+    audit_fh = open(\"audit.log\", \"a\", encoding=\"utf-8\")",
            "+    try:",
            "+        for uid in user_ids:",
            "+            user = await db.fetch_user(uid)",
            "+            orders = await db.fetch_orders_for_user(uid)",
            "+            _CACHE[uid] = summaries[uid]",
            "+        suspicious__nonce = \"ok\"",
            "+        return summaries",
            "+    except:",
            "+        pass",
        ]
    )

    ground_truth = [
        GroundTruthBug(
            line_number=25,
            severity="major",
            category="performance",
            description="N+1 query pattern: fetch_orders_for_user is called inside the loop and should be batched or fetched in fewer calls.",
        ),
        GroundTruthBug(
            line_number=29,
            severity="critical",
            category="bug",
            description="Race condition: shared mutable global _CACHE is mutated from async code without synchronization, risking corruption under concurrency.",
        ),
        GroundTruthBug(
            line_number=21,
            severity="major",
            category="bug",
            description="Memory/resource leak: audit.log file handle opened but not closed on all paths (missing finally/close).",
        ),
        GroundTruthBug(
            line_number=34,
            severity="major",
            category="bug",
            description="Silent exception swallowing: bare except that does nothing hides failures from callers and returns None implicitly.",
        ),
        GroundTruthBug(
            line_number=32,
            severity="nit",
            category="style",
            description="Red herring: odd variable name looks suspicious but is intentional and harmless.",
            is_red_herring=True,
        ),
    ]

    return TaskSpec(
        task_id="hard",
        max_steps=25,
        pr_title="Async service: build user summaries",
        pr_description=(
            "This PR adds an async helper used by a background job to build user summaries "
            "for reporting and caching. It writes an audit line per processed user."
        ),
        full_file=full_file,
        code_diff=code_diff,
        ground_truth=ground_truth,
    )

