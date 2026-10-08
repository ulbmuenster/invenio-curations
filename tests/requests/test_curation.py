# -*- coding: utf-8 -*-
#
# Copyright (C) 2024-2026 Graz University of Technology.
#
# Invenio-Curations is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Test curation request types."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from invenio_access.permissions import system_identity
from marshmallow import ValidationError

from invenio_curations import config
from invenio_curations.requests import curation
from invenio_curations.requests.curation import PublishRecordOp


def test_optional_workflow_flags_default_off():
    """Optional workflow changes must not affect existing installations by default."""
    assert config.CURATIONS_AUTO_PUBLISH_ON_ACCEPT is False
    assert config.CURATIONS_AUTO_SUBMIT_COMMUNITY is False
    assert config.CURATIONS_COMMENTS_USE_USER_IDENTITY is False
    assert config.CURATIONS_BLOCK_EDIT_DURING_REVIEW is False
    assert config.CURATIONS_ALLOW_CREATOR_CANCEL is False
    assert config.CURATIONS_CONSENT_MODAL_ENABLED is False
    assert config.CURATIONS_CONSENT_CHECKBOX_TEXTS


def test_publish_record_op_uses_system_identity():
    """PublishRecordOp must publish via system_identity, not the curator's identity."""
    op = PublishRecordOp(record_id="test-123")
    mock_service = MagicMock()

    with patch(
        "invenio_curations.requests.curation.current_rdm_records_service",
        new=mock_service,
    ):
        op.on_post_commit(None)

    mock_service.publish.assert_called_once_with(
        identity=system_identity,
        id_="test-123",
    )


def _request_with_files(*, enabled, bucket, items):
    files = SimpleNamespace(enabled=enabled, bucket=bucket, items=lambda: items)
    draft = SimpleNamespace(files=files)
    return SimpleNamespace(topic=SimpleNamespace(resolve=lambda: draft))


@pytest.mark.parametrize(
    ("allowed", "mentions_metadata_only"),
    [(True, True), (False, False)],
)
def test_submit_rejects_enabled_files_without_uploads(
    monkeypatch, allowed, mentions_metadata_only
):
    """Submitting a draft with files enabled but none uploaded fails."""
    monkeypatch.setattr(curation, "_", lambda text: text)
    request = _request_with_files(enabled=True, bucket=object(), items=[])
    app = Flask("testapp")
    app.config["RDM_ALLOW_METADATA_ONLY_RECORDS"] = allowed
    with app.app_context(), pytest.raises(ValidationError) as exc:
        curation._ensure_draft_has_files(request)
    assert ("metadata-only" in str(exc.value)) is mentions_metadata_only


def test_submit_allows_metadata_only_or_uploaded_files():
    """Metadata-only drafts and drafts with files can be submitted."""
    curation._ensure_draft_has_files(
        _request_with_files(enabled=False, bucket=None, items=[]),
    )
    curation._ensure_draft_has_files(
        _request_with_files(enabled=True, bucket=object(), items=["a.pdf"]),
    )
