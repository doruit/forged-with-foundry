from app.pri_001.document_pii import _collect_findings, _safe_blob_name


def test_blob_name_does_not_retain_uploaded_filename() -> None:
    uploaded_name = "person-name-private-record.docx"

    blob_name = _safe_blob_name(uploaded_name)

    assert uploaded_name not in blob_name
    assert blob_name.endswith("/source.docx")


def test_structured_findings_exclude_entity_values() -> None:
    service_result = {
        "entities": [
            {
                "text": "sensitive value",
                "category": "PersonType",
                "confidenceScore": 0.9876,
            }
        ]
    }

    findings = _collect_findings(service_result)

    assert len(findings) == 1
    assert findings[0].category == "PersonType"
    assert findings[0].confidence == 0.988
    assert not hasattr(findings[0], "text")
