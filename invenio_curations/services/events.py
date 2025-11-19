# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 Graz University of Technology.
#
# Invenio-Curations is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.

"""Custom events module."""
from invenio_requests.customizations.event_types import CommentEventType
from invenio_requests.records.api import RequestEventFormat
from marshmallow import fields, validate
from marshmallow_utils import fields as utils_fields


class CurationCommentEventType(CommentEventType):
    """Curation Comment event type."""

    type_id = "C"  # Keep same type_id as CommentEventType for compatibility

    _schema_initialized = False

    @staticmethod
    def payload_schema():
        """Return payload schema as a dictionary including reference_draft."""
        return dict(
            content=utils_fields.SanitizedHTML(
                required=True, validate=validate.Length(min=1)
            ),
            format=fields.Str(
                validate=validate.OneOf(choices=[e.value for e in RequestEventFormat]),
                load_default=RequestEventFormat.HTML.value,
            ),
            # reference_draft represents the base of comparison for the content (a custom display of a diff)
            # if the comment needs an update, new data is compared with the data present in this field, thus
            # avoiding the need for draft revisions.
            reference_draft=fields.Str(required=False),
        )

    def __init__(self, payload=None):
        """Initialize and ensure schema is registered."""
        super().__init__(payload)
        # Ensure schema is initialized on first use
        if not CurationCommentEventType._schema_initialized:
            CurationCommentEventType._ensure_schema_registered()
            CurationCommentEventType._schema_initialized = True

    @classmethod
    def _ensure_schema_registered(cls):
        """Ensure our custom schema is registered and cached."""
        from invenio_requests.proxies import current_requests

        # Clear any cached schema for this type_id to ensure ours is used
        if hasattr(current_requests, '_events_schema_cache') and cls.type_id in current_requests._events_schema_cache:
            del current_requests._events_schema_cache[cls.type_id]

        # Create and cache our schema
        cls._create_marshmallow_schema()

    @classmethod
    def _create_marshmallow_schema(cls):
        """Override to ensure our custom schema is used."""
        return super()._create_marshmallow_schema()
