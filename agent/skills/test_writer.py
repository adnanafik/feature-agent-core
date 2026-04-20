"""Skill 5: Writes pytest tests via Claude."""

from __future__ import annotations

import logging
from typing import Any

from agent.benchmark import BenchmarkTracker
from agent.event_emitter import EventEmitter
from agent.llm import LLMProvider
from agent.skill_base import Skill, SkillError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are writing pytest tests for a new feature in an existing Python codebase.

You write tests against the REQUIREMENT, ACCEPTANCE CRITERIA, and the user's
CLARIFICATION ANSWERS — NOT against any specific implementation. Tests must validate
that the feature behaves as the user asked, so that an incomplete or incorrect
implementation FAILS the test (which is the point). Do NOT soften assertions to match
what you assume the code does. Do NOT skip a behavior just because you suspect it
wasn't implemented.

URL PATHS, ROUTE METHODS, AND FIELD TYPES come from the existing codebase, not from
guesses. The "Existing route definitions" and "Existing schema definitions" sections
below show the actual URLs and types you must use:
- Copy URL paths VERBATIM from the routers file (including trailing slashes —
  FastAPI returns 307 redirects for missing trailing slashes and tests will fail).
- Use the exact HTTP method shown in the router (POST/PATCH/PUT/GET/DELETE).
- Match field types from the Pydantic schemas exactly. If the schema field is `date`,
  send `"2025-12-31"` not `"2025-12-31T23:59:59"`. If it's `datetime`, send the full
  ISO timestamp.

Match the assertion style and fixture usage of the "Existing test file" below.

Return ONLY this JSON:
{
  "test_changes": [
    {
      "path": "tests/test_file.py",
      "new_content": "complete test file content",
      "change_summary": "one sentence"
    }
  ]
}
Return JSON only."""


def _collect_files(codebase: dict[str, Any], substr_or_filter) -> str:
    """Concatenate file contents from relevant_files matching a path predicate."""
    out = ""
    for f in codebase.get("relevant_files", []):
        path = f.get("path", "")
        if callable(substr_or_filter):
            match = substr_or_filter(path)
        else:
            match = substr_or_filter in path
        if match:
            out += f"\n--- {path} ---\n{f.get('content', '')}\n"
    return out


class TestWriterSkill(Skill):
    """Writes pytest tests for the implemented feature."""

    name = "test_writer"

    async def execute(
        self,
        task_id: str,
        context: dict[str, Any],
        llm: LLMProvider,
        benchmark: BenchmarkTracker,
        emitter: EventEmitter,
    ) -> dict[str, Any]:
        benchmark.start_skill(self.name)
        try:
            await self._emit_start(task_id, emitter, 5, 7, "Writing tests...")

            requirement = context.get("requirement", {})
            clarification = context.get("clarification", {})
            codebase = context.get("codebase", {})

            qa_pairs = ""
            if clarification and clarification.get("answers"):
                for a in clarification["answers"]:
                    qa_pairs += f"Q: {a.get('question', '')}\nA: {a.get('answer', '')}\n\n"

            # Pull in routers, schemas, and any existing test files so the LLM can
            # extract real URL paths, field types, and assertion conventions.
            routers_str = _collect_files(codebase, "/routers/")
            schemas_str = _collect_files(codebase, "/schemas/")
            models_str = _collect_files(codebase, "/models/")
            existing_tests_str = _collect_files(
                codebase,
                lambda p: p.startswith("tests/") and "test_" in p.split("/")[-1],
            )
            conftest_str = _collect_files(codebase, "conftest")

            response = await llm.call(
                system=SYSTEM_PROMPT,
                user=(
                    f"Write tests for this feature:\n{requirement.get('title', '')}\n\n"
                    f"Requirements:\n{requirement.get('requirements', [])}\n\n"
                    f"Acceptance criteria to test:\n{requirement.get('acceptance_criteria', [])}\n\n"
                    f"Clarification answers from the user (these refine the spec):\n{qa_pairs}\n"
                    f"Existing route definitions (use these URL paths and methods VERBATIM):\n"
                    f"{routers_str}\n"
                    f"Existing schema definitions (use these field types VERBATIM):\n"
                    f"{schemas_str}\n"
                    f"Existing model definitions (for ORM construction):\n{models_str}\n"
                    f"Existing test file(s) for reference style:\n{existing_tests_str}\n"
                    f"Test fixtures available:\n{conftest_str}\n"
                    "Write comprehensive tests against the requirement. Copy URL paths "
                    "and field types VERBATIM from the routers and schemas above. JSON only."
                ),
                max_tokens=8192,
                model="powerful",
            )
            benchmark.record_llm_call(self.name, response, "Write tests")

            result = await llm.parse_json(
                response.content, max_tokens=8192, model="powerful"
            )
            test_changes = result.get("test_changes", [])

            await self._emit_log(
                task_id, emitter, f"Generated {len(test_changes)} test file(s)"
            )

            benchmark.end_skill(self.name, "success")
            await self._emit_done(task_id, emitter, benchmark)

            return {"test_changes": test_changes}

        except SkillError:
            benchmark.end_skill(self.name, "failed")
            raise
        except Exception as exc:
            benchmark.end_skill(self.name, "failed")
            raise SkillError(self.name, str(exc), detail=str(exc)) from exc
