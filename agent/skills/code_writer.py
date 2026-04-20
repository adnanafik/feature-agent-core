"""Skill 4: Writes code changes via Claude."""

from __future__ import annotations

import logging
from typing import Any

from agent.benchmark import BenchmarkTracker
from agent.event_emitter import EventEmitter
from agent.llm import LLMProvider
from agent.skill_base import Skill, SkillError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are implementing a software feature in an existing Python codebase.

CRITICAL SCOPE RULES:
- Only modify files DIRECTLY REQUIRED by the feature.
- If you are not SURE a file needs changes, OMIT IT.
- Unrelated files (other routers, unrelated services, existing migrations, CI configs, docs) MUST be left untouched.
- Reference files are provided for style and pattern matching ONLY — do not include them in file_changes unless the feature requires editing them.
- Never reformat, re-indent, re-order imports, or rename symbols in files that don't functionally need changes for this feature.

OUTPUT FORMAT:
For each file you create or modify, return the COMPLETE new file content in `new_content`. There is no partial-edit mode — always emit the full final file.

{
  "path": "app/models/task.py",
  "new_content": "...complete file content...",
  "change_summary": "one sentence"
}

CRITICAL RULES:
- For files that ALREADY EXIST, `new_content` MUST contain the entire existing file with your changes merged in. Anything you omit will be deleted from the file.
- Shared files like `conftest.py`, `__init__.py`, registries, and helpers are especially dangerous — preserve every existing fixture, helper, import, and unrelated definition.
- Follow existing code style and patterns exactly.
- Never add comments that were not in the original.
- Include an Alembic migration ONLY if the model schema actually changes.

Return ONLY this JSON:
{
  "files_to_modify": ["path/1.py", "path/2.py"],
  "file_changes": [ ... ],
  "implementation_notes": "brief technical notes"
}

The `files_to_modify` list and the `path` values in `file_changes` must match exactly.
Return JSON only."""


class CodeWriterSkill(Skill):
    """Writes code changes for the feature using Claude."""

    name = "code_writer"

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
            await self._emit_start(task_id, emitter, 4, 7, "Writing code changes...")

            requirement = context.get("requirement", {})
            clarification = context.get("clarification", {})
            codebase = context.get("codebase", {})
            iteration = context.get("iteration", 0)
            test_failure = context.get("test_failure")

            # Format clarification Q&A
            qa_pairs = ""
            if clarification and clarification.get("answers"):
                answers = clarification["answers"]
                for a in answers:
                    qa_pairs += f"Q: {a.get('question', '')}\nA: {a.get('answer', '')}\n\n"

            # Always send the full original codebase context (relevant files +
            # architecture). Trimming this on retry causes the model to hallucinate
            # imports and break things further.
            relevant_files_str = ""
            for f in codebase.get("relevant_files", []):
                relevant_files_str += f"\n--- {f['path']} ---\n{f['content']}\n"

            base_prompt = (
                f"Implement this feature:\n"
                f"Title: {requirement.get('title', '')}\n"
                f"Requirements: {requirement.get('requirements', [])}\n"
                f"Acceptance criteria: {requirement.get('acceptance_criteria', [])}\n\n"
                f"Clarifications (user answers — these are part of the spec):\n{qa_pairs}\n"
                f"Codebase architecture:\n{codebase.get('architecture_summary', '')}\n\n"
                f"Relevant files (current state on disk):\n{relevant_files_str}\n"
            )

            if iteration > 0 and test_failure:
                # On retry, also include the full content of files we previously
                # wrote, so the model can repair from a known baseline instead of
                # guessing at imports/structure.
                prior_changes = context.get("code_changes", [])
                prior_full = ""
                for c in prior_changes:
                    prior_full += (
                        f"\n--- {c.get('path', '')} (your previous attempt) ---\n"
                        f"{c.get('new_content', '')}\n"
                    )
                user_prompt = (
                    base_prompt
                    + f"\nYour PREVIOUS attempt wrote these files (they were applied, "
                    f"then tests ran):\n{prior_full}\n"
                    f"Tests reported:\n{test_failure}\n\n"
                    "ITERATE: return a NEW file_changes list that keeps your prior "
                    "fixes intact and only adjusts what's needed to make the failing "
                    "tests pass. Do NOT revert fixes that weren't related to the "
                    "failure. Verify imports against the actual files shown above — "
                    "do not guess module paths.\n"
                    "NOT NULL / required-column errors are almost always fixture-level "
                    "— include the fixture file in edits if so.\n"
                    "\nReturn complete file contents. JSON only."
                )
            else:
                user_prompt = base_prompt + "\nReturn complete file contents. JSON only."

            response = await llm.call(
                system=SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=8192,
                model="powerful",
            )
            benchmark.record_llm_call(self.name, response, "Write code changes")

            # Match correction budget to the original call — full-file outputs
            # are large, and a smaller budget would silently truncate the retry.
            result = await llm.parse_json(
                response.content, max_tokens=8192, model="powerful"
            )

            code_changes = result.get("file_changes", [])
            files_to_modify = set(result.get("files_to_modify", []))
            if files_to_modify:
                code_changes = [
                    c for c in code_changes if c.get("path") in files_to_modify
                ]
            for change in code_changes:
                await self._emit_progress(
                    task_id, emitter, f"Writing {change.get('path', '?')}"
                )

            context_update: dict[str, Any] = {
                "code_changes": code_changes,
                "implementation_notes": result.get("implementation_notes", ""),
            }

            benchmark.end_skill(self.name, "success")
            await self._emit_done(task_id, emitter, benchmark)

            return context_update

        except SkillError:
            benchmark.end_skill(self.name, "failed")
            raise
        except Exception as exc:
            benchmark.end_skill(self.name, "failed")
            raise SkillError(self.name, str(exc), detail=str(exc)) from exc
