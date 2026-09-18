# -*- coding: utf-8 -*-
#
# Copyright (C) 2024-2025 Graz University of Technology.
#
# Invenio-Curations is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Invenio module for curations."""

from .notifications.builders import (
    CurationRequestAcceptNotificationBuilder,
    CurationRequestCritiqueNotificationBuilder,
    CurationRequestResubmitNotificationBuilder,
    CurationRequestReviewNotificationBuilder,
    CurationRequestSubmitNotificationBuilder,
)
from .services import facets
from .services.diff import DiffDescription

CURATIONS_FACETS = {
    "type": {
        "facet": facets.type,
        "ui": {
            "field": "type",
        },
    },
    "status": {
        "facet": facets.status,
        "ui": {
            "field": "status",
        },
    },
}
"""Invenio requests facets."""


CURATIONS_ALLOW_PUBLISHING_EDITS = False
"""Allow publishing of metadata edits for already published records.

This allows users to modify their record's metadata and publish those changes
without going through another curation review.
The idea here is that the record has already passed through an initial quality check
anyway and it's very unlikely that anybody would update the metadata afterwards in
a way that decreases their quality.
Even if that happens, InvenioRDM stores `revisions` for record metadata.
"""

CURATIONS_TIMELINE_PAGE_SIZE = 15
"""Amount of items per page on the request details timeline"""

CURATIONS_MODERATION_ROLE = "administration-rdm-records-curation"
"""ID of the Role used for record curation."""

CURATIONS_SEARCH_REQUESTS = {
    "facets": ["type", "status"],
    "sort": ["bestmatch", "newest", "oldest"],
}
"""Curation requests search configuration (i.e list of curations requests)"""

CURATIONS_NOTIFICATIONS_BUILDERS = {
    builder.type: builder
    for builder in [
        CurationRequestAcceptNotificationBuilder,
        CurationRequestCritiqueNotificationBuilder,
        CurationRequestResubmitNotificationBuilder,
        CurationRequestReviewNotificationBuilder,
        CurationRequestSubmitNotificationBuilder,
    ]
}
"""Curation related notification builders as map for easy import."""

CURATIONS_ENABLE_REQUEST_COMMENTS = False
"""Enable or disable the generation of diff comments on ``rdm-curation`` requests.

Set this in order to activate the automatic creation/update of request comments
based on the difference found between draft states of an unpublished record
that is in the curation phase.
"""

CURATIONS_COMMENTS_CLASSES = [DiffDescription]
"""Extend curations comment classes for more diff customization.

List with all custom classes defined for rendering a change in a draft field.
"""

CURATIONS_COMMENT_TEMPLATE_FILE = "invenio_curations/comment-template.html"
"""Curation comment template file.

Override this path to use an instance-specific request comment template.
"""

CURATIONS_AUTO_PUBLISH_ON_ACCEPT = False
"""Automatically publish the record when a curation request is accepted.

When set to ``False`` (default, TU Graz origin behavior), accepting a curation
request marks the request as accepted and leaves the record in draft state so that
the submitter or curator can perform a final review and manually click "Publish".

When set to ``True``, accepting the curation request automatically publishes the
record via a post-commit transaction hook, and changes the action button label in
the curation request UI to "Accept and publish".

Use case: Repositories where curator approval is the definitive final gate and
publication should occur immediately without requiring an additional manual step.
"""

CURATIONS_AUTO_SUBMIT_COMMUNITY = False
"""Automatically submit pending community inclusion requests after curation accept.

When set to ``True``, if the draft record has an associated pending community-submission
request, that community request is automatically submitted as part of accepting the
curation request.

When set to ``False`` (default), community inclusion requests remain separate and must be
handled independently.

Use case: Multi-step submission pipelines where records are destined for a specific
community and should advance automatically to community review once institutional
curation approval is granted.
"""

CURATIONS_COMMENTS_USE_USER_IDENTITY = False
"""Use the user's identity for comment actions instead of system identity.

When set to ``False`` (default), automatically generated metadata diff comments
are attributed to the internal system identity.

When set to ``True``, diff comments are posted using the identity of the user
who made the draft changes.

Use case: Improves audit transparency on collaborative records by clearly attributing
who triggered each metadata change comment in the request conversation.
"""

CURATIONS_BLOCK_EDIT_DURING_REVIEW = False
"""Block editing of drafts while a curation request is under review.

When set to ``False`` (default, TU Graz origin behavior), record creators can
continue modifying their draft while curators are reviewing it.

When set to ``True``, draft modifications and saves are blocked for non-curators
while the curation request is in the ``review`` status - this includes both
continuing to edit an already-open draft, and starting a new edit of an
already-published record (which would otherwise reopen it as a draft). In the
UI, the deposit form save button and landing page edit button are disabled
for creators, while curators retain permission to make corrections.

Use case: Prevents race conditions and review inconsistencies by ensuring curators
evaluate an immutable draft snapshot during active review.
"""

CURATIONS_ALLOW_CREATOR_CANCEL = False
"""Allow record creators to cancel their own curation requests.

When set to ``False`` (default, TU Graz origin behavior), only curators and administrators
with the moderation role can cancel curation requests.

When set to ``True``, the creator of a record is also granted permission to cancel their
own curation request.

Use case: Empowers researchers to withdraw an accidental submission or recall a draft
to make additional edits before curator review begins.
"""

CURATIONS_CONSENT_MODAL_ENABLED = False
"""Require confirmation checkboxes before creating a curation request.

When set to ``False`` (default, TU Graz origin behavior), clicking the "Start publication
process" button directly creates and submits the curation request.

When set to ``True``, clicking the button displays a modal dialog with mandatory checkboxes
(configured via ``CURATIONS_CONSENT_CHECKBOX_TEXTS``) that must all be checked before the
request can be confirmed and submitted.

Use case: Institutions requiring explicit legal confirmation, data deposit policy compliance,
or terms of service consent prior to initiating formal curation.
"""

CURATIONS_CONSENT_CHECKBOX_TEXTS = [
    "I accept the terms of service and privacy policy.",
    "I accept the curation policy.",
    "I confirm that the record may be published in its final form.",
]
"""Checkbox labels shown in the curation consent modal.

Only applicable when ``CURATIONS_CONSENT_MODAL_ENABLED = True``. Each item in this list
is rendered as a mandatory checkbox in the confirmation modal.
"""

CURATIONS_PRIVILEGED_ROLES = ["administration"]
"""Curation privileged roles.

Users or processes with these roles can bypass curation checks.
Note: this does not apply for community curations. This config should be used just
to allow admins to publish records without having to perform the extra steps necessary
for approval.
Also used for creating rdm-records demo records in testing.
"""

CURATIONS_NOTIFICATIONS_OVERRIDE_EMAIL = None
"""If set, redirect all curation request notification emails to this address.

When set to a single email address, all curation-related notification emails
(submit, resubmit, review, accept, critique) are sent only to this address,
instead of the actually resolved recipients (e.g. all members of the curation
group, or the request creator).

Leave unset (``None``) to send notifications to the normal recipients.
"""

CURATIONS_TIMELINE_ABSOLUTE_DATES = False
"""Display absolute dates instead of relative dates in the curation timeline.

When set to ``True``, timestamps in timeline events and the request metadata sidebar
are rendered as locale-formatted datetime strings (e.g. "Jun 30, 2026, 2:30 PM")
instead of relative values (e.g. "3 minutes ago").

Can be toggled via the environment variable
``INVENIO_CURATIONS_TIMELINE_ABSOLUTE_DATES=true``.
"""

CURATIONS_MODERATORS_CAN_MANAGE_FILES = False
"""Grant curation moderators file-management rights on curated records.

When set to ``False`` (default, TU Graz origin behavior), file management
(uploading, removing, or reordering files) follows the normal record
permissions only, independent of any curation request.

When set to ``True``, users with the moderation role are also granted
file-management rights on any record/draft that has an associated curation
request, regardless of that request's status.

Use case: Lets curators fix file-level issues (wrong format, missing file,
accidental upload) as part of the review, without needing to hand editing
rights back to the creator first.
"""
