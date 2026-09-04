"""Pure, deterministic DAT-PRE-002 classification evaluation and guarded classify-eligibility checks."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from .models import ClassificationAction, ClassificationDecision, DemoFile

# Demo-only, filename-based content-category marker. A production control would use a
# Purview trainable classifier or real content inspection instead of a filename marker.
CONTENT_CATEGORY_MARKERS: dict[str, str] = {
    "confidential": "confidential",
    "public": "public",
}


def infer_content_category(file_name: str) -> str | None:
    """Return the demo's synthetic content category for a file name, or None if unknown."""
    lowered = file_name.lower()
    for marker, category in CONTENT_CATEGORY_MARKERS.items():
        if marker in lowered:
            return category
    return None


def required_label_id(
    content_category: str | None,
    confidential_label_id: str,
    public_label_id: str,
) -> str | None:
    if content_category == "confidential":
        return confidential_label_id
    if content_category == "public":
        return public_label_id
    return None


def _decision_id(item_id: str, evaluated_at: datetime) -> str:
    material = f"{item_id}|{evaluated_at.isoformat()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def evaluate_classification(
    file: DemoFile,
    current_label_ids: tuple[str, ...] | None,
    confidential_label_id: str,
    public_label_id: str,
    evaluated_at: datetime,
) -> ClassificationDecision:
    """Evaluate one file's classification state without model reasoning."""
    if evaluated_at.tzinfo is None:
        raise ValueError("evaluated_at must be timezone-aware")
    evaluated_at = evaluated_at.astimezone(UTC)
    decision_id = _decision_id(file.item_id, evaluated_at)

    if file.extraction_failed or current_label_ids is None:
        return ClassificationDecision(
            decision_id=decision_id,
            control_id="DAT-PRE-002",
            action=ClassificationAction.BLOCKED,
            item_id=file.item_id,
            file_name=file.name,
            content_category=file.content_category,
            current_label_ids=(),
            required_label_id=None,
            reason=(
                "Sensitivity-label extraction was unavailable; the file cannot be "
                "cleared automatically."
            ),
        )

    required = required_label_id(file.content_category, confidential_label_id, public_label_id)
    if required is None:
        return ClassificationDecision(
            decision_id=decision_id,
            control_id="DAT-PRE-002",
            action=ClassificationAction.BLOCKED,
            item_id=file.item_id,
            file_name=file.name,
            content_category=file.content_category,
            current_label_ids=current_label_ids,
            required_label_id=None,
            reason="File content category is unknown; classification policy cannot be evaluated.",
        )

    if required in current_label_ids:
        return ClassificationDecision(
            decision_id=decision_id,
            control_id="DAT-PRE-002",
            action=ClassificationAction.COMPLIANT,
            item_id=file.item_id,
            file_name=file.name,
            content_category=file.content_category,
            current_label_ids=current_label_ids,
            required_label_id=required,
            reason="The required sensitivity label is already assigned.",
        )

    return ClassificationDecision(
        decision_id=decision_id,
        control_id="DAT-PRE-002",
        action=ClassificationAction.FLAGGED,
        item_id=file.item_id,
        file_name=file.name,
        content_category=file.content_category,
        current_label_ids=current_label_ids,
        required_label_id=required,
        reason="Sensitivity label is missing or does not match the required classification.",
    )


def evaluate_classify_request(
    decision: ClassificationDecision,
    current_label_ids: tuple[str, ...],
) -> tuple[bool, str]:
    """Deterministically decide whether a guarded classify action may be submitted."""
    if decision.action is not ClassificationAction.FLAGGED:
        return False, "Only flagged files are eligible for a classify action."
    if decision.required_label_id is None:
        return False, "No required label was determined for this file."
    if current_label_ids != decision.current_label_ids:
        return False, (
            "The file's label state changed since the decision was evaluated; rescan first."
        )
    return True, "Classify permitted for the evaluated, unchanged file."
