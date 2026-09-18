# -*- coding: utf-8 -*-
#
# Copyright (C) 2024-2025 Graz University of Technology.
#
# Invenio-Curations is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Module tests."""

from types import SimpleNamespace

from flask import Flask, render_template
from invenio_rdm_records.services.permissions import (
    RDMRecordPermissionPolicy,
    RDMRequestsPermissionPolicy,
)
from invenio_requests.customizations import CommentEventType, LogEventType
from jinja2 import PackageLoader

from invenio_curations import InvenioCurations, __version__
from invenio_curations.services.components import CurationComponent
from invenio_curations.services.events import CurationCommentEventType
from invenio_curations.services.permissions import (
    CurationRDMRecordPermissionPolicy,
    CurationRDMRequestsPermissionPolicy,
)
from invenio_curations.views import ui


def test_version() -> None:
    """Test version import."""
    assert __version__


def test_init() -> None:
    """Test extension initialization."""
    app = Flask("testapp")
    app.config["APP_RDM_RECORD_LANDING_PAGE_TEMPLATE"] = (
        "invenio_app_rdm/records/detail.html"
    )
    ext = InvenioCurations(app)
    ext.init_config(app)
    assert "invenio-curations" in app.extensions
    assert CurationComponent in app.config["RDM_RECORDS_SERVICE_COMPONENTS"]
    assert app.config["RDM_PERMISSION_POLICY"] is CurationRDMRecordPermissionPolicy
    assert (
        app.config["REQUESTS_PERMISSION_POLICY"] is CurationRDMRequestsPermissionPolicy
    )
    assert (
        app.config["THEME_JAVASCRIPT_TEMPLATE"] == "invenio_curations/javascript.html"
    )
    assert (
        app.config["_CURATIONS_BASE_JAVASCRIPT_TEMPLATE"]
        == "invenio_app_rdm/javascript.html"
    )
    assert (
        app.config["APP_RDM_RECORD_LANDING_PAGE_TEMPLATE"]
        == "invenio_app_rdm/records/detail.html"
    )

    app = Flask("testapp")
    app.config.update(
        APP_RDM_RECORD_LANDING_PAGE_TEMPLATE="invenio_app_rdm/records/detail.html",
        CURATIONS_BLOCK_EDIT_DURING_REVIEW=True,
    )
    InvenioCurations(app)
    assert (
        app.config["APP_RDM_RECORD_LANDING_PAGE_TEMPLATE"]
        == "invenio_curations/records/detail.html"
    )

    app = Flask("testapp")
    ext = InvenioCurations()
    assert "invenio-curations" not in app.extensions
    ext.init_app(app)
    assert "invenio-curations" in app.extensions


def test_init_preserves_custom_integration() -> None:
    """Automatic wiring preserves custom policies and JavaScript templates."""

    class CustomRecordPolicy:
        pass

    class CustomRequestsPolicy:
        pass

    app = Flask("testapp")
    app.config.update(
        RDM_PERMISSION_POLICY=CustomRecordPolicy,
        REQUESTS_PERMISSION_POLICY=CustomRequestsPolicy,
        THEME_JAVASCRIPT_TEMPLATE="my_instance/javascript.html",
    )

    InvenioCurations(app)

    assert app.config["RDM_PERMISSION_POLICY"] is CustomRecordPolicy
    assert app.config["REQUESTS_PERMISSION_POLICY"] is CustomRequestsPolicy
    assert app.config["_CURATIONS_BASE_JAVASCRIPT_TEMPLATE"] == (
        "my_instance/javascript.html"
    )
    assert app.config["THEME_JAVASCRIPT_TEMPLATE"] == (
        "invenio_curations/javascript.html"
    )


def test_sync_services_initialized_earlier() -> None:
    """Finalization updates services regardless of extension load order."""
    record_config = SimpleNamespace(
        components=[],
        permission_policy_cls=RDMRecordPermissionPolicy,
    )
    media_config = SimpleNamespace(
        components=[],
        permission_policy_cls=RDMRecordPermissionPolicy,
    )
    requests_configs = [
        SimpleNamespace(permission_policy_cls=RDMRequestsPermissionPolicy)
        for _ in range(3)
    ]
    app = Flask("testapp")
    app.extensions["invenio-rdm-records"] = SimpleNamespace(
        records_service=SimpleNamespace(config=record_config),
        records_media_files_service=SimpleNamespace(config=media_config),
    )
    app.extensions["invenio-requests"] = SimpleNamespace(
        requests_service=SimpleNamespace(config=requests_configs[0]),
        request_events_service=SimpleNamespace(config=requests_configs[1]),
        request_files_service=SimpleNamespace(config=requests_configs[2]),
    )

    InvenioCurations().sync_services(app)

    assert CurationComponent in record_config.components
    assert CurationComponent in media_config.components
    assert record_config.permission_policy_cls is CurationRDMRecordPermissionPolicy
    assert media_config.permission_policy_cls is CurationRDMRecordPermissionPolicy
    assert all(
        config.permission_policy_cls is CurationRDMRequestsPermissionPolicy
        for config in requests_configs
    )


def test_init_merges_shared_config() -> None:
    """Extension setup preserves instance values and adds curation defaults."""
    app = Flask("testapp")
    app.config["REQUESTS_FACETS"] = {"custom": {}}
    app.config["NOTIFICATIONS_BUILDERS"] = {"custom": object()}

    InvenioCurations(app)

    assert {"type", "status", "custom"} <= app.config["REQUESTS_FACETS"].keys()
    assert "custom" in app.config["NOTIFICATIONS_BUILDERS"]
    assert "curation-request.accept" in app.config["NOTIFICATIONS_BUILDERS"]

    app = Flask("testapp")
    app.config["CURATIONS_FACETS"] = {"curation-custom": {}}
    app.config["CURATIONS_NOTIFICATIONS_BUILDERS"] = {"curation-custom": object()}

    InvenioCurations(app)

    assert "curation-custom" in app.config["REQUESTS_FACETS"]
    assert "curation-custom" in app.config["NOTIFICATIONS_BUILDERS"]


def test_comments_register_event_type_and_default_template() -> None:
    """Enabling comments needs no event or template override in the instance."""
    app = Flask("testapp")
    app.config.update(
        CURATIONS_ENABLE_REQUEST_COMMENTS=True,
        REQUESTS_REGISTERED_EVENT_TYPES=[LogEventType(), CommentEventType()],
    )

    InvenioCurations(app)

    comment_type = next(
        item
        for item in app.config["REQUESTS_REGISTERED_EVENT_TYPES"]
        if item.type_id == "C"
    )
    assert isinstance(comment_type, CurationCommentEventType)

    app.jinja_loader = PackageLoader("invenio_curations", "templates/semantic-ui")
    app.jinja_env.globals["_"] = lambda value: value
    with app.test_request_context():
        rendered = render_template(
            app.config["CURATIONS_COMMENT_TEMPLATE_FILE"],
            header="Header",
            adds=["value"],
            changes=[],
            removes=[],
        )
    assert "Header" in rendered
    assert "value" in rendered


def test_get_curation_request_for_record_disabled() -> None:
    """Disabled edit blocking skips curation lookup."""
    app = Flask("testapp")
    app.config["CURATIONS_BLOCK_EDIT_DURING_REVIEW"] = False

    with app.app_context():
        assert ui.get_curation_request_for_record({"id": "abc"}) is None


def test_get_curation_request_for_record(monkeypatch) -> None:
    """Enabled edit blocking looks up the draft curation request."""
    app = Flask("testapp")
    app.config["CURATIONS_BLOCK_EDIT_DURING_REVIEW"] = True
    review = object()
    draft = object()

    class DummyPid:
        @staticmethod
        def resolve(record_id: str, *, registered_only: bool = False) -> object:
            assert record_id == "abc"
            assert registered_only is False
            return draft

    class DummyService:
        @staticmethod
        def get_review(
            *,
            identity: object,
            topic: object,
            expand: bool = False,
        ) -> object:
            assert identity is ui.system_identity
            assert topic is draft
            assert expand is False
            return review

    monkeypatch.setattr(ui.RDMDraft, "pid", DummyPid)
    monkeypatch.setattr(ui, "current_curations_service", DummyService)

    with app.app_context():
        assert ui.get_curation_request_for_record({"id": "abc"}) is review


def test_curation_record_context_uses_record_detail_endpoint(monkeypatch) -> None:
    """Record detail requests inject the current draft curation request."""
    app = Flask("testapp")
    app.add_url_rule(
        "/records/<pid_value>",
        endpoint="invenio_app_rdm_records.record_detail",
        view_func=lambda pid_value: pid_value,
    )
    review = object()

    monkeypatch.setattr(
        ui,
        "get_curation_request_for_record",
        lambda record: review if record == {"id": "abc"} else None,
    )

    with app.test_request_context("/records/abc"):
        app.preprocess_request()
        context = ui.curation_record_context()

    assert context["draft_curation_request"] is review
    assert (
        context["get_curation_request_for_record"] is ui.get_curation_request_for_record
    )
