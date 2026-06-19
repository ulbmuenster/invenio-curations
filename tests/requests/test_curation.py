# -*- coding: utf-8 -*-
#
# Copyright (C) 2024-2026 Graz University of Technology.
#
# Invenio-Curations is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Test curation request types."""

from unittest.mock import MagicMock, patch

from invenio_access.permissions import system_identity

from invenio_curations.requests.curation import PublishRecordOp


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
