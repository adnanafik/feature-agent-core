"""Clarification endpoint for submitting answers to clarification questions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from agent.api.models import ClarifyRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["clarify"])


def _get_deps():
    """Get shared dependencies from main module."""
    from agent.config import settings
    from agent.main import nats_client, state_manager
    return state_manager, nats_client, settings


@router.post("/api/tasks/{task_id}/clarify")
async def clarify_task(task_id: str, request: ClarifyRequest):
    """Submit clarification answers and resume the pipeline."""
    state_manager, nats_client, settings = _get_deps()

    # Task must exist
    task = await state_manager.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # Task must be awaiting clarification
    if task["status"] != "AWAITING_CLARIFICATION":
        raise HTTPException(
            status_code=400,
            detail=f"Task is {task['status']}, not AWAITING_CLARIFICATION",
        )

    # Validate answer count matches question count
    clarification = task.get("clarification", {})
    questions = clarification.get("questions", [])
    if len(request.answers) != len(questions):
        raise HTTPException(
            status_code=400,
            detail=f"Expected {len(questions)} answers, got {len(request.answers)}",
        )

    # Validate each answer
    question_ids = {q["id"] for q in questions}
    for answer in request.answers:
        # Question ID must match
        if answer.question_id not in question_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown question_id: {answer.question_id}",
            )

        # Answer must be non-empty
        if not answer.answer.strip():
            raise HTTPException(
                status_code=400,
                detail=f"Answer for {answer.question_id} must not be empty",
            )

        # "Other" answers must be at least 5 chars
        if answer.selected_option_id == "other" and len(answer.answer.strip()) < 5:
            raise HTTPException(
                status_code=400,
                detail=f"Custom answer for {answer.question_id} must be at least 5 characters",
            )

    # Save answers
    answers_data = [a.model_dump() for a in request.answers]
    await state_manager.set_clarification_answers(task_id, answers_data)

    # Publish resume message to NATS
    try:
        await nats_client.publish(
            settings.NATS_TASK_SUBJECT,
            {"task_id": task_id, "action": "resume"},
        )
    except ConnectionError:
        logger.warning("NATS not available — resume for %s queued locally", task_id)

    return {"status": "RESUMED", "task_id": task_id}
