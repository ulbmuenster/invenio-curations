# -*- coding: utf-8 -*-
#
# Copyright (C) 2024-2026 Graz University of Technology.
#
# Invenio-Curation is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.

"""Curation request type."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from flask_principal import Identity
from invenio_access.permissions import system_identity
from invenio_db.uow import Operation
from invenio_i18n import lazy_gettext as _
from invenio_notifications.services.uow import NotificationOp
from invenio_rdm_records.proxies import current_rdm_records_service
from invenio_records_resources.services import EndpointLink
from invenio_records_resources.services.uow import UnitOfWork
from invenio_requests.customizations import RequestState, RequestType, actions
from invenio_requests.customizations.actions import RequestAction

from invenio_curations.notifications.builders import (
    CurationRequestAcceptNotificationBuilder,
    CurationRequestCritiqueNotificationBuilder,
    CurationRequestResubmitNotificationBuilder,
    CurationRequestReviewNotificationBuilder,
    CurationRequestSubmitNotificationBuilder,
)


class PublishRecordOp(Operation):
    """Operation to publish a record after curation request is accepted."""

    # Class variable to track if we're in auto-publish mode
    _in_auto_publish = False

    def __init__(self, identity: Identity, record_id: str) -> None:
        """Initialize the publish operation."""
        super().__init__()
        self._identity = identity
        self._record_id = record_id

    def on_post_commit(self, uow: UnitOfWork) -> None:
        """Publish the record after the transaction is committed."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"PublishRecordOp.on_post_commit: Attempting to publish record {self._record_id}"
        )
        try:
            # Set flag to indicate we're in auto-publish mode
            # This allows the CurationComponent to skip redundant checks
            PublishRecordOp._in_auto_publish = True

            result = current_rdm_records_service.publish(
                identity=self._identity,
                id_=self._record_id,
            )
            logger.info(
                f"PublishRecordOp.on_post_commit: Successfully published record {self._record_id}"
            )
        except Exception as e:
            # Log the error but don't fail the accept action
            logger.exception(
                f"PublishRecordOp.on_post_commit: Failed to auto-publish record {self._record_id}: {e}"
            )
        finally:
            # Always reset the flag
            PublishRecordOp._in_auto_publish = False


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

    # Require to go through review before accepting
    status_from: ClassVar[list[str]] = ["review"]

    def execute(self, identity: Identity, uow: UnitOfWork) -> None:
        """Execute the accept action."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"CurationAcceptAction.execute called for request {self.request.id}, status: {self.request.status}"
        )

        uow.register(
            NotificationOp(
                CurationRequestAcceptNotificationBuilder.build(
                    identity=identity,
                    request=self.request,
                ),
            ),
        )

        logger.info("About to call super().execute()")
        super().execute(identity, uow)
        logger.info("super().execute() completed successfully")

        # Register operation to publish the record after the transaction commits
        try:
            logger.info("Attempting to resolve topic and register publish operation")
            topic = self.request.topic.resolve()
            logger.info(f"Topic resolved: {topic['id']}")
            uow.register(
                PublishRecordOp(
                    identity=identity,
                    record_id=topic["id"],
                ),
            )
            logger.info("PublishRecordOp registered successfully")
        except Exception as e:
            # Log the error but don't fail the accept action
            logger.exception(f"Failed to register auto-publish operation: {e}")


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
        "cancelled",
        "created",
        "critiqued",
        "declined",
        "expired",
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
    ]


class CurationReviewAction(actions.RequestAction):
    """Mark request as review."""

    status_from: Final[list[str]] = ["submitted", "resubmitted"]
    status_to: Final[str] = "review"

    def execute(self, identity: Identity, uow: UnitOfWork) -> None:
        """Execute the review action."""
        uow.register(
            NotificationOp(
                CurationRequestReviewNotificationBuilder.build(
                    identity=identity,
                    request=self.request,
                ),
            ),
        )

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
        "pending_resubmission": RequestState.CLOSED,
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

    links_item: Final = {
        "self_html": EndpointLink(
            "invenio_app_rdm_requests.read_request",
            params=["request_pid_value"],
            vars=lambda _, values: (
                values.update(request_pid_value=values["request"].id)
            ),
        ),
    }
