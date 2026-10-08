# -*- coding: utf-8 -*-
#
# Copyright (C) 2024-2026 Graz University of Technology.
#
# Invenio-Curations is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Invenio module for generic and customizable curations."""

from flask import Flask, g
from flask_menu import current_menu
from invenio_i18n import lazy_gettext as _
from invenio_requests.proxies import current_requests_service
from invenio_requests.services import RequestsService

from . import config
from .proxies import unproxy
from .resources import CurationsResource, CurationsResourceConfig
from .services import (
    CurationRequestService,
    CurationsServiceConfig,
)
from .views.ui import user_has_curations_management_role


def _get_requests_service() -> RequestsService:
    return unproxy(current_requests_service)


class ServiceConfigs:
    """Customized service configs."""

    def __init__(self, app: Flask) -> None:
        """Constructs."""
        self._curations: CurationsServiceConfig = CurationsServiceConfig.build(app)

    @property
    def curations(self) -> CurationRequestService:
        """The curation service."""
        return self._curations


def finalize_app(app: Flask) -> None:
    """Finalize app."""
    init_menu(app)


def init_menu(app: Flask) -> None:  # noqa: ARG001
    """Initialize flask menu."""
    user_dashboard = current_menu.submenu("dashboard")
    user_dashboard.submenu("curation-overview").register(
        "invenio_curations.curation_requests_overview",
        text=_("Curation Requests"),
        order=100,
        visible_when=lambda: user_has_curations_management_role(g.identity),
    )


class InvenioCurations:
    """Invenio-Curations extension."""

    def __init__(self, app: Flask | None = None) -> None:
        """Extension initialization."""
        self.curations_service: CurationRequestService | None = None
        self.curations_resource: CurationsResource | None = None
        if app:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Flask application initialization."""
        self.init_config(app)
        self.init_event_types(app)
        self.init_services(app)
        self.init_resources(app)
        app.extensions["invenio-curations"] = self

    def init_config(self, app: Flask) -> None:
        """Initialize configuration."""
        for k in dir(config):
            if k.startswith("CURATIONS_"):
                app.config.setdefault(k, getattr(config, k))
        app.config["REQUESTS_FACETS"] = {
            **app.config["CURATIONS_FACETS"],
            **app.config.get("REQUESTS_FACETS", {}),
        }
        app.config["NOTIFICATIONS_BUILDERS"] = {
            **app.config["CURATIONS_NOTIFICATIONS_BUILDERS"],
            **app.config.get("NOTIFICATIONS_BUILDERS", {}),
        }
        notifications = app.extensions.get("invenio-notifications")
        if notifications is not None:
            notifications.manager.builders = app.config["NOTIFICATIONS_BUILDERS"]

        if app.config.get("REQUESTS_REVIEWERS_ENABLED"):
            msg = "Invenio-curations cannot be installed with reviewers feature enabled yet."
            raise Exception(msg)

    def init_event_types(self, app: Flask) -> None:
        """Register the extended comment event type when comments are enabled."""
        if not app.config["CURATIONS_ENABLE_REQUEST_COMMENTS"]:
            return

        from .services.events import CurationCommentEventType

        event_type = CurationCommentEventType()
        registered_types = app.config.get("REQUESTS_REGISTERED_EVENT_TYPES")
        if registered_types is not None:
            registered_types = [
                event_type if item.type_id == event_type.type_id else item
                for item in registered_types
            ]
            if not any(item.type_id == event_type.type_id for item in registered_types):
                registered_types.append(event_type)
            app.config["REQUESTS_REGISTERED_EVENT_TYPES"] = registered_types

        requests = app.extensions.get("invenio-requests")
        if requests is not None:
            requests.event_type_registry.register_type(event_type, force=True)

    def service_configs(self, app: Flask) -> ServiceConfigs:
        """Customized service configs."""
        return ServiceConfigs(app)

    def init_services(self, app: Flask) -> None:
        """Initialize the service and resource for curations."""
        service_configs = self.service_configs(app)

        self.curations_service = CurationRequestService(
            config=service_configs.curations,
            requests_service=_get_requests_service(),
        )

    def init_resources(self, app: Flask) -> None:
        """Init resources."""
        self.curations_resource = CurationsResource(
            service=self.curations_service,
            config=CurationsResourceConfig.build(app),
        )
