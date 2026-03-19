"""Pipeline metering and explicit phase checkpoint contracts."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.processing_decision_service import ProcessingPhase


class PhaseCheckpointStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"


class PhaseCheckpointType(str, Enum):
    FIRST_RESULT = "first_result"
    FINALIZATION = "finalization"


class PhaseCheckpoint(BaseModel):
    """Observable checkpoint for a pipeline phase boundary."""

    model_config = ConfigDict(use_enum_values=True)

    phase: ProcessingPhase
    checkpoint: PhaseCheckpointType
    status: PhaseCheckpointStatus
    entry_stage: str
    exit_stage: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentMeteringService:
    """Record explicit phase boundaries and build persisted pipeline metadata."""

    def begin_phase(
        self,
        *,
        phase: ProcessingPhase,
        checkpoint: PhaseCheckpointType,
        entry_stage: str,
        metadata: dict[str, Any] | None = None,
    ) -> PhaseCheckpoint:
        return PhaseCheckpoint(
            phase=phase,
            checkpoint=checkpoint,
            status=PhaseCheckpointStatus.STARTED,
            entry_stage=entry_stage,
            started_at=datetime.utcnow(),
            metadata=metadata or {},
        )

    def complete_phase(
        self,
        checkpoint: PhaseCheckpoint,
        *,
        exit_stage: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        merged_metadata = dict(checkpoint.metadata)
        if metadata:
            merged_metadata.update(metadata)

        return checkpoint.model_copy(
            update={
                "status": PhaseCheckpointStatus.COMPLETED,
                "exit_stage": exit_stage,
                "completed_at": datetime.utcnow(),
                "metadata": merged_metadata,
            }
        ).model_dump(mode="json")

    def fail_phase(
        self,
        checkpoint: PhaseCheckpoint,
        *,
        exit_stage: str,
        error: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        merged_metadata = dict(checkpoint.metadata)
        merged_metadata["error"] = error
        if metadata:
            merged_metadata.update(metadata)

        return checkpoint.model_copy(
            update={
                "status": PhaseCheckpointStatus.FAILED,
                "exit_stage": exit_stage,
                "completed_at": datetime.utcnow(),
                "metadata": merged_metadata,
            }
        ).model_dump(mode="json")

    def build_pipeline_metadata(self, *, result) -> dict[str, Any]:
        metadata = {
            "stage_reached": result.stage_reached.value,
            "current_state": getattr(result, "current_state", "processing_phase_1"),
            "confidence_level": result.confidence_level.value,
            "needs_review": result.needs_review,
            "processing_time_ms": result.processing_time_ms,
            "phase_checkpoints": result.phase_checkpoints,
        }
        if result.processing_decision:
            metadata["processing_decision"] = result.processing_decision
        return metadata
