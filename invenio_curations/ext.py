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
from invenio_rdm_records.services.components import DefaultRecordsComponents
from invenio_rdm_records.services.permissions import (
    RDMRecordPermissionPolicy,
    RDMRequestsPermissionPolicy,
)
from invenio_requests.proxies import current_requests_service
from invenio_requests.services import RequestsService

from . import config
from .proxies import unproxy
from .resources import CurationsResource, CurationsResourceConfig
from .services import (
    CurationRequestService,
    CurationsServiceConfig,
)
from .services.components import CurationComponent
from .services.permissions import (
    CurationRDMRecordPermissionPolicy,
    CurationRDMRequestsPermissionPolicy,
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
    app.extensions["invenio-curations"].sync_services(app)
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

        components = list(
            app.config.get("RDM_RECORDS_SERVICE_COMPONENTS", DefaultRecordsComponents),
        )
        if CurationComponent not in components:
            components.append(CurationComponent)
        app.config["RDM_RECORDS_SERVICE_COMPONENTS"] = components

        if (
            app.config.get("RDM_PERMISSION_POLICY", RDMRecordPermissionPolicy)
            is RDMRecordPermissionPolicy
        ):
            app.config["RDM_PERMISSION_POLICY"] = CurationRDMRecordPermissionPolicy
        if (
            app.config.get("REQUESTS_PERMISSION_POLICY", RDMRequestsPermissionPolicy)
            is RDMRequestsPermissionPolicy
        ):
            app.config["REQUESTS_PERMISSION_POLICY"] = (
                CurationRDMRequestsPermissionPolicy
            )

        javascript_template = app.config.get(
            "THEME_JAVASCRIPT_TEMPLATE",
            "invenio_app_rdm/javascript.html",
        )
        if javascript_template != "invenio_curations/javascript.html":
            app.config["_CURATIONS_BASE_JAVASCRIPT_TEMPLATE"] = javascript_template
            app.config["THEME_JAVASCRIPT_TEMPLATE"] = (
                "invenio_curations/javascript.html"
            )
        else:
            app.config.setdefault(
                "_CURATIONS_BASE_JAVASCRIPT_TEMPLATE",
                "invenio_app_rdm/javascript.html",
            )
        if (
            app.config.get("CURATIONS_BLOCK_EDIT_DURING_REVIEW")
            and app.config.get("APP_RDM_RECORD_LANDING_PAGE_TEMPLATE")
            == "invenio_app_rdm/records/detail.html"
        ):
            app.config["APP_RDM_RECORD_LANDING_PAGE_TEMPLATE"] = (
                "invenio_curations/records/detail.html"
            )
        if app.config.get("REQUESTS_REVIEWERS_ENABLED"):
            msg = "Invenio-curations cannot be installed with reviewers feature enabled yet."
            raise Exception(msg)

        self.sync_services(app)

    def sync_services(self, app: Flask) -> None:
        """Apply automatic wiring to services initialized before this extension."""
        rdm = app.extensions.get("invenio-rdm-records")
        if rdm is not None:
            for name in ("records_service", "records_media_files_service"):
                service = getattr(rdm, name)
                components = list(service.config.components)
                if CurationComponent not in components:
                    components.append(CurationComponent)
                    service.config.components = components
                if service.config.permission_policy_cls is RDMRecordPermissionPolicy:
                    service.config.permission_policy_cls = (
                        CurationRDMRecordPermissionPolicy
                    )

        requests = app.extensions.get("invenio-requests")
        if requests is not None:
            for name in (
                "requests_service",
                "request_events_service",
                "request_files_service",
            ):
                service = getattr(requests, name)
                if service.config.permission_policy_cls is RDMRequestsPermissionPolicy:
                    service.config.permission_policy_cls = (
                        CurationRDMRequestsPermissionPolicy
                    )

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
