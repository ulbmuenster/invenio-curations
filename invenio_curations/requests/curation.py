# -*- coding: utf-8 -*-
#
# Copyright (C) 2024-2026 Graz University of Technology.
#
# Invenio-Curation is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.

"""Curation request type."""

from __future__ import annotations

import contextvars
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Final

from flask import current_app
from flask_principal import Identity
from invenio_access.permissions import system_identity
from invenio_communities.members.records.api import Member
from invenio_db.uow import Operation
from invenio_i18n import lazy_gettext as _
from invenio_notifications.services.uow import NotificationOp
from invenio_rdm_records.proxies import (
    current_rdm_records_service,
    current_record_communities_service,
)
from invenio_records_resources.services import EndpointLink
from invenio_records_resources.services.uow import UnitOfWork
from invenio_requests.customizations import RequestState, RequestType, actions
from invenio_requests.customizations.actions import RequestAction
from invenio_requests.proxies import current_requests_service
from invenio_users_resources.proxies import current_users_service
from marshmallow.fields import String
from marshmallow_utils.fields import SanitizedUnicode

from invenio_curations.notifications.builders import (
    CurationRequestAcceptNotificationBuilder,
    CurationRequestCritiqueNotificationBuilder,
    CurationRequestResubmitNotificationBuilder,
    CurationRequestReviewNotificationBuilder,
    CurationRequestSubmitNotificationBuilder,
)

# ContextVar is used instead of a class-level flag to avoid cross-request pollution
# under multi-threaded WSGI workers (each request has its own context).
_auto_publish_ctx: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_auto_publish_ctx",
    default=False,
)


class PublishRecordOp(Operation):
    """Operation to publish a record after curation request is accepted."""

    def __init__(self, record_id: str) -> None:
        """Initialize the publish operation."""
        super().__init__()
        self._record_id = record_id

    _WITHDRAW_ACTION_BY_STATUS: Final[dict[str, str]] = {
        "created": "delete",
        "submitted": "cancel",
    }

    # Same roles CommunitySubmission itself treats as eligible to accept a
    # submission to their community (see its `needs_context`).
    _COMMUNITY_SELF_APPROVE_ROLES: Final[set[str]] = {"owner", "manager", "curator"}

    @classmethod
    def _creator_can_self_approve(cls, review: dict) -> bool:
        """Check if the community-submission's creator already has accept rights.

        If the record's creator is themselves an owner/manager/curator of the
        target community, they could have accepted their own
        community-submission request anyway - so there is nothing gained by
        making them (or someone else) go through that step again separately
        from the curation (SPP) approval.
        """
        creator_user_id = review.get("created_by", {}).get("user")
        community_id = review["receiver"]["community"]
        if creator_user_id is None:
            return False

        memberships = Member.get_memberships(SimpleNamespace(id=creator_user_id))
        return any(
            comm_id == community_id and role in cls._COMMUNITY_SELF_APPROVE_ROLES
            for comm_id, role in memberships
        )

    def on_post_commit(self, uow: UnitOfWork) -> None:  # noqa: ARG002
        """Publish the record after the transaction is committed.

        Community-submission reviews are finalized one of two ways:

        - Auto-finished (submitted, if needed, and accepted right away,
          finalizing the community inclusion and publishing in one step):
          when CURATIONS_AUTO_SUBMIT_COMMUNITY is enabled ("migration" mode,
          hard-forcing every record into its community regardless of who
          created it), or when the record's creator is themselves an
          owner/manager/curator of the target community - they already had
          the right to accept their own submission, so requiring a separate
          go-ahead (from themselves or anyone else) would add nothing.

        - Otherwise ("production" mode, e.g. an outside contributor
          submitting into a community they don't manage): curation acceptance
          publishes the record, independent of any community-submission
          review. Publishing a draft that still has an open
          community-submission request would leave that request referencing a
          draft that no longer exists (publish() deletes it), so instead we
          withdraw it (delete/cancel, depending on its status) and - if it was
          for a community - re-create the community relationship as a
          community-*inclusion* request (`require_review=True`) against the
          now-published record. That request type is designed for
          already-published records, so a community manager can independently
          accept or decline it later without blocking publication: declining
          just leaves the record published without that community.
        """
        token = _auto_publish_ctx.set(True)
        try:
            draft = current_rdm_records_service.draft_cls.pid.resolve(
                self._record_id,
                registered_only=False,
            )
            review = draft.get_review()
            is_community_submission = (
                review is not None and review["type"] == "community-submission"
            )
            auto_finish_community = is_community_submission and (
                current_app.config.get("CURATIONS_AUTO_SUBMIT_COMMUNITY", False)
                or self._creator_can_self_approve(review)
            )

            if auto_finish_community:
                status = review["status"]
                if status == "created":
                    current_requests_service.execute_action(
                        identity=system_identity,
                        id_=review.id,
                        action="submit",
                    )
                if status in ("created", "submitted"):
                    current_requests_service.execute_action(
                        identity=system_identity,
                        id_=review.id,
                        action="accept",
                    )
                # else: request already accepted/declined/cancelled/expired -
                # nothing to do.
                return

            community_id = None
            if (
                is_community_submission
                and review["status"] in self._WITHDRAW_ACTION_BY_STATUS
            ):
                community_id = review["receiver"]["community"]
                if review["status"] == "submitted":
                    # CommunitySubmission's CancelAction already clears
                    # draft.parent.review (or draft.review) itself as part of
                    # its execute(), which is what publish() otherwise refuses
                    # to proceed with (ReviewExistsError) - nothing more to do.
                    current_requests_service.execute_action(
                        identity=system_identity,
                        id_=review.id,
                        action="cancel",
                    )
                else:
                    # "created" (never submitted): no action clears the field
                    # for us, so use review.delete() instead, which both
                    # clears it and hard-deletes the request, since it was
                    # never a real pending request to begin with.
                    current_rdm_records_service.review.delete(
                        identity=system_identity,
                        id_=self._record_id,
                    )

            current_rdm_records_service.publish(
                identity=system_identity,
                id_=self._record_id,
            )

            if community_id is not None:
                current_record_communities_service.add(
                    identity=system_identity,
                    id_=self._record_id,
                    data={"communities": [{"id": community_id, "require_review": True}]},
                )
        except Exception:
            current_app.logger.exception(
                "Auto-publish failed for record %s after curation acceptance",
                self._record_id,
            )
        finally:
            _auto_publish_ctx.reset(token)


class CurationCreateAndSubmitAction(actions.CreateAndSubmitAction):
    """Create and submit a request."""

    def execute(self, identity: Identity, uow: UnitOfWork) -> None:
        """Execute the create & submit action."""
        uow.register(
            NotificationOp(
                CurationRequestSubmitNotificationBuilder.build(
                    identity=identity,
                    request=self.request,
                ),
            ),
        )

        super().execute(identity, uow)


class CurationSubmitAction(actions.SubmitAction):
    """Submit action for user access requests."""

    # list of statuses this action can be performed from
    status_from: Final[list[str]] = ["created"]

    def execute(self, identity: Identity, uow: UnitOfWork) -> None:
        """Execute the submit action."""
        uow.register(
            NotificationOp(
                CurationRequestSubmitNotificationBuilder.build(
                    identity=identity,
                    request=self.request,
                ),
            ),
        )
        super().execute(identity, uow)


class CurationAcceptAction(actions.AcceptAction):
    """Accept a request."""

    # Require to go through review before accepting.
    # Also allowed when a draft for a published record is deleted/discarded
    status_from: Final[list[str]] = ["review", "pending_resubmission"]

    def execute(self, identity: Identity, uow: UnitOfWork) -> None:
        """Execute the accept action."""
        uow.register(
            NotificationOp(
                CurationRequestAcceptNotificationBuilder.build(
                    identity=identity,
                    request=self.request,
                ),
            ),
        )

        super().execute(identity, uow)

        # Register operation to publish the record after the transaction commits.
        # PublishRecordOp itself decides whether to publish directly or, if a
        # community-submission review is still pending, submit/accept that
        # request instead - see its on_post_commit for the reasoning.
        if current_app.config.get("CURATIONS_AUTO_PUBLISH_ON_ACCEPT", False):
            try:
                topic = self.request.topic.resolve()
                uow.register(
                    PublishRecordOp(
                        record_id=topic["id"],
                    ),
                )
            except Exception:
                current_app.logger.exception(
                    "Failed to register auto-publish operation after curation acceptance",
                )


class CurationDeclineAction(actions.DeclineAction):
    """Decline a request."""

    # Instead of declining, the record should be critiqued.
    status_from: Final[list[str]] = []


class CurationCancelAction(actions.CancelAction):
    """Cancel a request."""

    # A user might want to cancel their request.
    # Also done when a draft for an already published record is deleted/discarded
    status_from: Final[list[str]] = [
        "accepted",
        "created",
        "critiqued",
        "declined",
        "expired",
        "pending_resubmission",
        "resubmitted",
        "review",
        "submitted",
    ]


class CurationExpireAction(actions.ExpireAction):
    """Expire a request."""

    status_from: Final[list[str]] = ["submitted", "critiqued", "resubmitted"]


class CurationDeleteAction(actions.DeleteAction):
    """Delete a request."""

    # When a user deletes their draft, the request will get deleted. Should be possible from every state.
    # Usually delete is only possible programmatically, as the base permissions allow user driven deletion
    # only during `created` status
    status_from: Final[list[str]] = [
        "accepted",
        "cancelled",
        "created",
        "critiqued",
        "declined",
        "expired",
        "resubmitted",
        "review",
        "submitted",
        "pending_resubmission",
    ]


def _resolve_user_display_name(identity: Identity) -> str | None:
    """Resolve a display name (full name or username) for the given identity."""
    user_id = getattr(identity, "id", None)
    if not user_id:
        return None

    try:
        user = current_users_service.read(identity, user_id).to_dict()
    except Exception:
        current_app.logger.exception(
            "Could not resolve display name for user %s",
            user_id,
        )
        return None

    return user.get("profile", {}).get("full_name") or user.get("username")


class CurationReviewAction(actions.RequestAction):
    """Mark request as review."""

    status_from: Final[list[str]] = ["submitted", "resubmitted"]
    status_to: Final[str] = "review"

    def execute(self, identity: Identity, uow: UnitOfWork) -> None:
        """Execute the review action."""
        if self.request["status"] == "submitted":
            uow.register(
                NotificationOp(
                    CurationRequestReviewNotificationBuilder.build(
                        identity=identity,
                        request=self.request,
                    ),
                ),
            )

        display_name = _resolve_user_display_name(identity)
        if display_name:
            self.request["payload"] = {
                "review_started_by": display_name,
                "review_started_at": datetime.now(timezone.utc).isoformat(),
            }

        super().execute(identity, uow)


class CurationCritiqueAction(actions.RequestAction):
    """Request changes for request."""

    status_from: Final[list[str]] = ["review"]
    status_to: Final[str] = "critiqued"

    def execute(self, identity: Identity, uow: UnitOfWork) -> None:
        """Execute the critique action."""
        uow.register(
            NotificationOp(
                CurationRequestCritiqueNotificationBuilder.build(
                    identity=identity,
                    request=self.request,
                ),
            ),
        )

        super().execute(identity, uow)


class CurationResubmitAction(actions.RequestAction):
    """Mark request as ready for review."""

    status_from: Final[list[str]] = [
        "accepted",
        "critiqued",
        "pending_resubmission",
        "cancelled",
        "declined",
    ]
    status_to: Final[str] = "resubmitted"

    def execute(self, identity: Identity, uow: UnitOfWork) -> None:
        """Execute the resubmit action."""
        uow.register(
            NotificationOp(
                CurationRequestResubmitNotificationBuilder.build(
                    identity=identity,
                    request=self.request,
                ),
            ),
        )
        super().execute(identity, uow)


class CurationPendingResubmissionAction(actions.RequestAction):
    """Mark request in a pending state, waiting to be resubmitted."""

    status_from: Final[list[str]] = [
        "accepted",
        "cancelled",
        "declined",
    ]
    status_to: Final[str] = "pending_resubmission"

    def execute(self, identity: Identity, uow: UnitOfWork) -> None:
        """Execute the pending_resubmit action."""
        super().execute(identity, uow)


#
# Request
#
class CurationRequest(RequestType):
    """Curation request type."""

    type_id: Final[str] = "rdm-curation"
    name: Final[str] = _("Curation")

    # Dict mapping action names to action classes
    available_actions: Final[dict[str, type[RequestAction]]] = {
        **RequestType.available_actions,
        "create": CurationCreateAndSubmitAction,
        "submit": CurationSubmitAction,
        "accept": CurationAcceptAction,
        "decline": CurationDeclineAction,
        "cancel": CurationCancelAction,
        "expire": CurationExpireAction,
        "delete": CurationDeleteAction,
        "review": CurationReviewAction,
        "critique": CurationCritiqueAction,
        "resubmit": CurationResubmitAction,
        "pending_resubmission": CurationPendingResubmissionAction,
    }

    # Dict mapping status names to RequestState values
    available_statuses: Final[dict[str, RequestState]] = {
        **RequestType.available_statuses,
        "review": RequestState.OPEN,
        "critiqued": RequestState.OPEN,
        "resubmitted": RequestState.OPEN,
        "pending_resubmission": RequestState.OPEN,
    }
    """Available statuses for the request.

    The keys in this dictionary is the set of available statuses, and their
    values are indicators whether this request is considered to be open, closed
    or undefined.
    """

    create_action: Final[str] = "create"
    """Defines the action that's able to create this request.

    This must be set to one of the available actions for the custom request type.
    """

    creator_can_be_none: Final[bool] = False
    topic_can_be_none: Final[bool] = False
    allowed_creator_ref_types: Final[list[str]] = ["user", "community"]
    allowed_receiver_ref_types: Final[list[str]] = ["group"]
    allowed_topic_ref_types: Final[list[str]] = ["record"]

    payload_schema: Final = {
        "review_started_by": SanitizedUnicode(),
        # A plain string: ISODateString would truncate the ISO timestamp to a date.
        "review_started_at": String(),
    }
    """Payload storing who last started the curation review, and when.

    This is a display-only snapshot (not indexed/filterable, as the request
    payload field is not indexed), updated every time the ``review`` action
    is executed.
    """

    links_item: Final = {
        "self_html": EndpointLink(
            "invenio_app_rdm_requests.read_request",
            params=["request_pid_value"],
            vars=lambda _, values: (
                values.update(request_pid_value=values["request"].id)
            ),
        ),
    }
