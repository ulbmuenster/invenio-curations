# -*- coding: utf-8 -*-
#
# Copyright (C) 2024-2025 Graz University of Technology.
#
# Invenio-Curations is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Notification related filters for notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import current_app
from invenio_accounts.models import Role
from invenio_notifications.models import Recipient
from invenio_notifications.services.filters import RecipientFilter

CURATION_REQUEST_TYPE = "rdm-curation"

if TYPE_CHECKING:
    from invenio_notifications.models import Notification


class OverrideEmailRecipientFilter(RecipientFilter):
    """Redirect curation team recipients to a single configured email address.

    If ``CURATIONS_NOTIFICATIONS_OVERRIDE_EMAIL`` is set, recipients belonging
    to the curation team / moderation group are replaced with a single
    recipient pointing to the override email address. The request creator
    (author) and other non-curation recipients are preserved.
    """

    def __call__(
        self,
        notification: Notification,
        recipients: dict[str, Recipient],
    ) -> dict[str, Recipient]:
        """Filter recipients."""
        override_email = current_app.config.get(
            "CURATIONS_NOTIFICATIONS_OVERRIDE_EMAIL",
        )
        if not override_email:
            return recipients

        request = notification.context.get("request")
        if not request:
            return recipients

        if isinstance(request, dict):
            request_type = request.get("type")
        else:
            request_type = getattr(request, "type", None)
            if hasattr(request_type, "type_id"):
                request_type = request_type.type_id
            elif hasattr(request_type, "id"):
                request_type = request_type.id
            elif request_type is not None:
                request_type = str(request_type)

        if request_type != CURATION_REQUEST_TYPE:
            return recipients

        curator_user_ids: set[str] = set()

        def _collect_role_user_ids(role_ref: Any) -> None:
            if not role_ref:
                return
            if isinstance(role_ref, Role):
                curator_user_ids.update(str(u.id) for u in role_ref.users)
                return
            role_id = None
            if isinstance(role_ref, dict):
                role_id = role_ref.get("group") or role_ref.get("id")
            elif isinstance(role_ref, str):
                role_id = role_ref
            elif hasattr(role_ref, "id"):
                role_id = role_ref.id

            if role_id:
                try:
                    role = Role.query.filter(
                        (Role.name == role_id) | (Role.id == role_id)
                    ).one_or_none()
                    if role and hasattr(role, "users"):
                        curator_user_ids.update(str(u.id) for u in role.users)
                except Exception:
                    pass

        _collect_role_user_ids(current_app.config.get("CURATIONS_MODERATION_ROLE"))
        receiver = (
            request.get("receiver")
            if isinstance(request, dict)
            else getattr(request, "receiver", None)
        )
        _collect_role_user_ids(receiver)

        created_by = (
            request.get("created_by")
            if isinstance(request, dict)
            else getattr(request, "created_by", None)
        )
        creator_user_id: str | None = None
        if isinstance(created_by, dict):
            creator_user_id = created_by.get("user") or created_by.get("id")
        elif created_by is not None:
            creator_user_id = getattr(created_by, "id", None) or getattr(
                created_by, "user", None
            )

        if creator_user_id is not None:
            creator_user_id = str(creator_user_id)

        has_curators = False
        for key, recipient in list(recipients.items()):
            if key == "curation_override":
                continue

            user_id = (
                str(recipient.data["id"])
                if (recipient.data and "id" in recipient.data)
                else str(key)
            )

            # Preserve the request author even if the author is part of the moderation role
            if creator_user_id and (
                user_id == creator_user_id or str(key) == creator_user_id
            ):
                continue

            if user_id in curator_user_ids or str(key) in curator_user_ids:
                has_curators = True
                del recipients[key]

        if has_curators:
            recipients["curation_override"] = Recipient(data={"email": override_email})

        return recipients
