# -*- coding: utf-8 -*-
#
# Copyright (C) 2024-2025 Graz University of Technology.
#
# Invenio-Curations is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""View functions for curations."""

import os
from typing import cast

from flask import Blueprint, Flask

# Comment-processing (services/diff.py) renders CURATIONS_COMMENT_TEMPLATE_FILE
# via `render_template` while handling draft updates, which happen on the API
# app. The UI blueprint's template folder (views/ui.py) is only registered on
# the UI app, so without this the lookup fails with TemplateNotFound and the
# comment silently never gets created (exception is swallowed in comment.py).
_TEMPLATE_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")


def create_curations_bp(app: Flask) -> Blueprint:
    """Create curations blueprint."""
    ext = app.extensions["invenio-curations"]
    bp = cast(Blueprint, ext.curations_resource.as_blueprint())
    bp.template_folder = _TEMPLATE_FOLDER
    return bp
