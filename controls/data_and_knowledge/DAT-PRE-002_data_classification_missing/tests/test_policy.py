from datetime import UTC, datetime

from src.dat_pre_002.models import ClassificationAction, DemoFile
from src.dat_pre_002.policy import (
    evaluate_classification,
    evaluate_classify_request,
    infer_content_category,
    required_label_id,
)

NOW = datetime(2026, 9, 4, tzinfo=UTC)
CONFIDENTIAL_LABEL = "11111111-1111-1111-1111-111111111111"
PUBLIC_LABEL = "22222222-2222-2222-2222-222222222222"


def file(
    *,
    name: str = "datpre002-demo-confidential-customer-record.txt",
    item_id: str = "item-1",
    content_category: str | None = "confidential",
    extraction_failed: bool = False,
) -> DemoFile:
    return DemoFile(
        name=name, item_id=item_id, content_category=content_category, extraction_failed=extraction_failed
    )


def test_infer_content_category_matches_markers():
    assert infer_content_category("datpre002-demo-confidential-customer-record.txt") == "confidential"
    assert infer_content_category("datpre002-demo-public-faq-draft.txt") == "public"
    assert infer_content_category("datpre002-demo-unlabeled-notes.txt") is None


def test_required_label_id_maps_category_to_label():
    assert required_label_id("confidential", CONFIDENTIAL_LABEL, PUBLIC_LABEL) == CONFIDENTIAL_LABEL
    assert required_label_id("public", CONFIDENTIAL_LABEL, PUBLIC_LABEL) == PUBLIC_LABEL
    assert required_label_id(None, CONFIDENTIAL_LABEL, PUBLIC_LABEL) is None


def test_compliant_when_required_label_already_present():
    decision = evaluate_classification(
        file(), (CONFIDENTIAL_LABEL,), CONFIDENTIAL_LABEL, PUBLIC_LABEL, NOW
    )
    assert decision.action is ClassificationAction.COMPLIANT


def test_flagged_when_label_missing():
    decision = evaluate_classification(file(), (), CONFIDENTIAL_LABEL, PUBLIC_LABEL, NOW)
    assert decision.action is ClassificationAction.FLAGGED
    assert decision.required_label_id == CONFIDENTIAL_LABEL


def test_flagged_when_label_mismatched():
    decision = evaluate_classification(
        file(), (PUBLIC_LABEL,), CONFIDENTIAL_LABEL, PUBLIC_LABEL, NOW
    )
    assert decision.action is ClassificationAction.FLAGGED


def test_extraction_failure_blocks_regardless_of_labels():
    decision = evaluate_classification(
        file(extraction_failed=True), None, CONFIDENTIAL_LABEL, PUBLIC_LABEL, NOW
    )
    assert decision.action is ClassificationAction.BLOCKED


def test_unknown_content_category_blocks():
    decision = evaluate_classification(
        file(content_category=None, name="datpre002-demo-unlabeled-notes.txt"),
        (),
        CONFIDENTIAL_LABEL,
        PUBLIC_LABEL,
        NOW,
    )
    assert decision.action is ClassificationAction.BLOCKED


def test_naive_datetime_is_rejected():
    try:
        evaluate_classification(
            file(), (), CONFIDENTIAL_LABEL, PUBLIC_LABEL, datetime(2026, 9, 4)
        )
    except ValueError:
        return
    raise AssertionError("expected ValueError for naive evaluated_at")


def test_classify_allowed_when_flagged_and_state_unchanged():
    decision = evaluate_classification(file(), (), CONFIDENTIAL_LABEL, PUBLIC_LABEL, NOW)
    allowed, _ = evaluate_classify_request(decision, ())
    assert allowed is True


def test_classify_denied_when_not_flagged():
    decision = evaluate_classification(
        file(), (CONFIDENTIAL_LABEL,), CONFIDENTIAL_LABEL, PUBLIC_LABEL, NOW
    )
    allowed, reason = evaluate_classify_request(decision, (CONFIDENTIAL_LABEL,))
    assert allowed is False
    assert "eligible" in reason


def test_classify_denied_when_state_changed_since_decision():
    decision = evaluate_classification(file(), (), CONFIDENTIAL_LABEL, PUBLIC_LABEL, NOW)
    allowed, reason = evaluate_classify_request(decision, (PUBLIC_LABEL,))
    assert allowed is False
    assert "changed" in reason


def test_safe_dict_excludes_label_ids_and_only_exposes_metadata():
    decision = evaluate_classification(file(), (), CONFIDENTIAL_LABEL, PUBLIC_LABEL, NOW)
    safe = decision.safe_dict()
    assert "current_label_ids" not in safe
    assert "required_label_id" not in safe
    assert safe["file_name"] == file().name
