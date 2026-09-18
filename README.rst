..
    Copyright (C) 2021 CERN.
    Copyright (C) 2024-2026 Graz University of Technology.
    Copyright (C) 2024 TU Wien.

    Invenio-Curations is free software; you can redistribute it and/or
    modify it under the terms of the MIT License; see LICENSE file for more
    details.

Invenio-Curations
=================

.. image:: https://github.com/tu-graz-library/invenio-curations/workflows/CI/badge.svg
        :target: https://github.com/tu-graz-library/invenio-curations/actions?query=workflow%3ACI

.. image:: https://img.shields.io/github/tag/tu-graz-library/invenio-curations.svg
        :target: https://github.com/tu-graz-library/invenio-curations/releases

.. image:: https://img.shields.io/pypi/dm/invenio-curations.svg
        :target: https://pypi.python.org/pypi/invenio-curations

.. image:: https://img.shields.io/github/license/tu-graz-library/invenio-curations.svg
        :target: https://github.com/tu-graz-library/invenio-curations/blob/master/LICENSE


What *is* `Invenio-Curations`?
------------------------------

`Invenio-Curations` is an Invenio package that adds curation reviews to InvenioRDM.

The primary purpose of this package is to satisfy the need of some institutions to restrict the possibility for users to self-publish unreviewed records.
One of the reasons why institutions may want this is if they are pursuing a `Core Trust Seal <https://www.coretrustseal.org/>`_ or similar certification for their (InvenioRDM-based) repository.


Aren't there community reviews already?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Out of the box, InvenioRDM already provides reviews for records as part of the submission or inclusion into communities.
However, there is no requirement per default for records to be part of any community at all.
Thus, it is generally easy for users to self-publish records in standard InvenioRDM without any further review.

Further, the set of reviewers for community submission/inclusion requests depends on the target community in question.
In contrast, `Invenio-Curations` defines a fixed group of users to act as reviewers for all records in the system.


Requirements
------------

Requires InvenioRDM v12 or higher (``invenio-app-rdm >= 12.0.7``).


How to set up
-------------

Installation & Automatic Setup (Zero-Config)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install the package in your InvenioRDM environment:

.. code-block:: console

    pip install invenio-curations

When installed in a vanilla InvenioRDM instance, `Invenio-Curations` automatically registers the necessary service components, permission policies, request search facets, notification builders, and UI component overrides during application initialization.

**No manual configuration in ``invenio.cfg`` is required for the default TU Graz vanilla curation workflow to work.**

Manual Configuration (Optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your instance already uses custom permission policies, customized service components, or instance-specific templates, `Invenio-Curations` preserves your existing configurations. You can also explicitly customize the backend wiring in ``invenio.cfg`` as described in the sections below:

Add `notification builders` for `groups`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Currently, requests can only be sent to a single `receiver`.
However, curation reviews are typically performed by a `group` of people rather than one single fixed `user`.
Thus, the curation requests are sent to a `group` rather than a single `user` in the system so that all users with a certain `role` can receive and act on curation requests.

Additionally, notification builders have to be configured so that notifications are sent out to the involved users whenever something's happening in the curation review.

.. code-block:: python

    from invenio_app_rdm.config import NOTIFICATIONS_BUILDERS
    from invenio_curations.config import CURATIONS_NOTIFICATIONS_BUILDERS

    # enable sending of notifications when something's happening in the review
    NOTIFICATIONS_BUILDERS = {
        **NOTIFICATIONS_BUILDERS,
        # Curation request
        **CURATIONS_NOTIFICATIONS_BUILDERS
    }


Add service component
^^^^^^^^^^^^^^^^^^^^^

In order to require an accepted curation request before publishing a record, the component has to be appended to the RDM record service:

.. code-block:: python

    from invenio_curations.services.components import CurationComponent
    from invenio_rdm_records.services.components import DefaultRecordsComponents

    # NOTE: the curation component should be added at the end
    RDM_RECORDS_SERVICE_COMPONENTS = DefaultRecordsComponents + [
        CurationComponent,
    ]


Set the search facets
^^^^^^^^^^^^^^^^^^^^^

To show friendlier names than the internal identifiers for the new request type and its status values in the search facets, you need to set the following configuration:

.. code-block:: python

   from invenio_curations.services import facets as curations_facets

    REQUESTS_FACETS = {
        "type": {
            "facet": curations_facets.type,
            "ui": {
                "field": "type",
            },
        },
        "status": {
            "facet": curations_facets.status,
            "ui": {
                "field": "status",
            },
        },
    }


Set requests permission policy
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Setting the requests permission is done due to the following reasons:

Additional actions have to be specified.

Reading a request and creating comments depends on the state. Since new states are added, these states have to be included for these two permissions.

In the default InvenioRDM implementation, a user can submit an unpublished record to a community. Doing so will result in a `CommunitySubmission` request.
If this request is accepted, the record would also get published. Our `CurationComponent` would already stop the publish action. However, in the UI, the button to accept and publish is still visible and pushing it will present the user with a generic error.
In order to prevent this, the request permissions can be adapted such that the button is not shown in the first place.
Since we only want to change the behaviour of these community submission requests, we first check the type and then check the associated record. If the record has been accepted, the general request permissions will be applied. Otherwise, no one can accept the community submission.

.. code-block:: python

    from invenio_rdm_records.requests import CommunitySubmission
    from invenio_rdm_records.services.permissions import RDMRequestsPermissionPolicy
    from invenio_requests.services.generators import Creator, Receiver

    from invenio_curations.requests.curation import CurationRequest
    from invenio_curations.services.generators import (
        IfCurationRequestAccepted,
        IfCurationRequestBasedExists,
        IfRequestTypes,
        TopicPermission,
    )


    class CurationRDMRequestsPermissionPolicy(RDMRequestsPermissionPolicy):
        """Customized permission policy for sane handling of curation requests."""

        curation_request_record_review = IfRequestTypes(
            [CurationRequest],
            then_=[TopicPermission(permission_name="can_review")],
            else_=[],
        )

        # Only allow community-submission requests to be accepted after the rdm-curation request has been accepted
        can_action_accept: Final = [
            IfRequestTypes(
                request_types=[CommunitySubmission],
                then_=[
                    IfCurationRequestBasedExists(
                        then_=[
                            IfCurationRequestAccepted(
                                then_=RDMRequestsPermissionPolicy.can_action_accept,
                                else_=[],
                            ),
                        ],
                        else_=RDMRequestsPermissionPolicy.can_action_accept,
                    ),
                ],
                else_=RDMRequestsPermissionPolicy.can_action_accept,
            ),
        ]

        # Update can read and can comment with new states
        can_read = [
            # Have to explicitly check the request type and circumvent using status, as creator/receiver will add a query filter where one entity must be the user.
            IfRequestTypes(
                [CurationRequest],
                then_=[
                    Creator(),
                    Receiver(),
                    TopicPermission(permission_name="can_review"),
                ],
                else_=RDMRequestsPermissionPolicy.can_read,
            )
        ]

        can_create_comment = can_read
        can_reply_comment = can_create_comment

        # Update submit to also allow record reviewers/managers for curation requests
        can_action_submit = RDMRequestsPermissionPolicy.can_action_submit + [
            curation_request_record_review
        ]
        # Add new actions
        can_action_review = RDMRequestsPermissionPolicy.can_action_accept
        can_action_critique = RDMRequestsPermissionPolicy.can_action_accept

        can_action_resubmit = can_action_submit
        can_action_pending_resubmission = can_action_resubmit

    REQUESTS_PERMISSION_POLICY = CurationRDMRequestsPermissionPolicy


Permit the moderators to view the draft under review
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For curation reviews to make sense, it is of course vital for the moderators to be able to view the drafts in question.

`Invenio-Curations` offers two permission generators that can come in handy for this purpose: ``CurationModerators`` and ``IfCurationRequestExists``.
The former creates ``RoleNeed`` for the configured ``CURATIONS_MODERATION_ROLE``.
It is intended to be used together with the latter, which checks if an ``rdm-curation`` request exists for the given record/draft.

However, please note that overriding the permission policy for records is significantly more complex than overriding the one for requests!
In fact, it's out of scope for this README - or is it?


Set RDM permission policy
^^^^^^^^^^^^^^^^^^^^^^^^^

Reasons to not rely on access grants:
- They can be completely disabled for an instance
- They can be managed by users which means they can just remove access for the moderators

Thus, we provide a very basic adaptation of the RDM record permission policy used in a vanilla instance. This adapted policy should serve as
an easy way to test the package as well as provide a starting point to understand which permissions have to be adapted for this module to work as expected.

.. code-block:: python

    from invenio_curations.services.permissions import CurationRDMRecordPermissionPolicy
    RDM_PERMISSION_POLICY = CurationRDMRecordPermissionPolicy


Make the new workflow available through the UI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The changes so far have dealt with setting up the mechanism for the curation workflow in the backend.
To also make the workflow accessible for users through the UI, some frontend components have to be updated as well.

`Invenio-Curations` provides a few `component overrides <https://inveniordm.docs.cern.ch/develop/howtos/override_components/>`_.
These overrides need to be registered in the overridable registry (i.e. in your instance's ``assets/js/invenio_app_rdm/overridableRegistry/mapping.js``):

.. code-block:: javascript

    import { curationComponentOverrides } from "@js/invenio_curations/requests";
    import { DepositBox } from "@js/invenio_curations/deposit/DepositBox";

    export const overriddenComponents = {
        // ... after your other overrides ...
        ...curationComponentOverrides,
        "InvenioAppRdm.Deposit.CardDepositStatusBox.container": DepositBox,
    };

The ``DepositBox`` overrides the record's lifecycle management box on the deposit form.
It takes care of rendering the "publish" button only when appropriate in the curation workflow.
The other ``curationComponentOverrides`` provide better rendering for the new elements (e.g. event types) in the request page.


Optional UI: Set Curation request custom field
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Because there could be a need to inform the user about the curation workflow, a custom field at the end can be added just to show
a specific message. In order to set this up, a basic invenio custom field in your instance could be configured.

Create a new javascript file at assets/templates/custom_fields/RdmCuration.js

.. code-block:: javascript

    import React from 'react';
    import { i18next } from "@translations/invenio_app_rdm/i18next";

    const RdmCuration = () => {
      return (
        <div className='ui visible warning message'>
          <h4>
          {i18next.t(
            "Please create a curation request after saving the \
            draft by clicking on Start Publication Process")}
          </h4>
        </div>
      );
    };

    export default RdmCuration;


Then add this block to the invenio.cfg to link the component to the actual custom-field.

.. code-block:: python

    from invenio_records_resources.services.custom_fields import BaseListCF
    from marshmallow_utils.fields import SanitizedUnicode

    class RdmCurationCF(BaseListCF):
        """Experiments with title and program."""

        def __init__(self, name, **kwargs):
            """Constructor."""
            super().__init__(
              name,
              **kwargs
            )

        @property
        def mapping(self):
            """Return the mapping."""
            return {"type": "text"}

    RDM_CUSTOM_FIELDS = [
        RdmCurationCF(
            name="rdm-curation",
            field_cls=SanitizedUnicode
        ),
    ]

    RDM_CUSTOM_FIELDS_UI = [
        {
            "section": _("Curation request"),
            "fields": [
                dict(
                    field="rdm-curation",
                    ui_widget="RdmCuration",
                ),
            ],
            "hide_from_landing_page": True
        }
    ]


Option: Activate automatically generated request comments.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This feature enables the creation and update of custom request comments (i.e events) that should track the differences between metadata states of a draft found in the curation phase.
How to enable it:

1. Make sure to set the ``CURATIONS_ENABLE_REQUEST_COMMENTS`` variable

.. code-block:: python

    CURATIONS_ENABLE_REQUEST_COMMENTS = True


2. Register the custom event type. This is **required** for the comment feature to work. Without it, the ``CurationCommentEventType`` payload schema will not be loaded, resulting in a ``ValidationError`` for the ``reference_draft`` field.

.. code-block:: python

    from invenio_curations.services.events import CurationCommentEventType
    from invenio_requests.customizations import LogEventType

    REQUESTS_REGISTERED_EVENT_TYPES = [
        LogEventType(),
        CurationCommentEventType(),
    ]


3. Setup the jinja template for the comment in the running instance's **./templates** folder. This is the the basic template and of course can be changed.
   The actual updates should be kept in whatever template is eventually used. Variables for those are: **adds**, **changes**, **removes**.

.. code-block:: html

    <!DOCTYPE html>
    <html>
        <body>
            <h3>{{header}}</h3>

            {% if adds|length > 0 %}
                <h3>
                    {{ _("Added") }}
                </h3>
                <ul>
                {% for add in adds %}
                    <li>{{add}}</li>
                {% endfor %}
                </ul>
            {% endif %}

            {% if changes|length > 0 %}
                <h3>
                    {{ _("Changed") }}
                </h3>
                <ul>
                {% for change in changes %}
                    <li>{{change}}</li>
                {% endfor %}
                </ul>
            {% endif %}

            {% if removes|length > 0 %}
                <h3>
                    {{ _("Removed") }}
                </h3>
                <ul>
                {% for remove in removes %}
                    <li>{{remove}}</li>
                {% endfor %}
                </ul>
            {% endif %}
        </body>
    </html>

3. Optional: Update the Request Events component

   If your instance needs to hide these comments from regular users, you can use this component to achieve this:

.. code-block:: python

    from invenio_requests.config import REQUESTS_EVENTS_SERVICE_COMPONENTS as REQUESTS_EVENTS_SERVICE_COMPONENTS_BASE
    from invenio_curations.services.components import CurationEventsComponent
    REQUESTS_EVENTS_SERVICE_COMPONENTS = REQUESTS_EVENTS_SERVICE_COMPONENTS_BASE + [CurationEventsComponent]


4. Optional: Configure the template file.

.. code-block:: python

    # default value
    CURATIONS_COMMENT_TEMPLATE_FILE = "comment-template.html"


5. Optional: Extend or replace field rendering classes.

.. code-block:: python

    from invenio_curations.services import DiffDescription
    CURATIONS_COMMENTS_CLASSES = [DiffDescription] # + MyCustomClass


Create curator role
~~~~~~~~~~~~~~~~~~~

The permission to manage curation requests is controlled by a specific role in the system.
The name of this role can be specified via a configuration variable ``CURATIONS_MODERATION_ROLE``.

The following ``invenio roles`` command can be used to create the role if it doesn't exist yet: ``invenio roles create <name-of-curation-role>``.

After the role has been created, it can be assigned to users via: ``invenio roles add <user-email-address> <name-of-curation-role>``.

Configuration Reference
~~~~~~~~~~~~~~~~~~~~~~~

All optional features and adaptations default to off (``False`` / ``None``) so that installing this module preserves the original TU Graz vanilla curation behavior out-of-the-box. Every adaptation is individually configurable in ``invenio.cfg``.

Summary Table
^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 35 10 15 40

   * - Variable
     - Type
     - Default
     - Description / Primary Use Case
   * - ``CURATIONS_AUTO_PUBLISH_ON_ACCEPT``
     - bool
     - ``False``
     - Auto-publish record on curation accept; removes manual post-approval publish step.
   * - ``CURATIONS_AUTO_SUBMIT_COMMUNITY``
     - bool
     - ``False``
     - Force a pending community-submission through on curation accept, bypassing separate community review.
   * - ``CURATIONS_ALLOW_PUBLISHING_EDITS``
     - bool
     - ``False``
     - Allow publishing metadata edits to existing records without re-curation.
   * - ``CURATIONS_BLOCK_EDIT_DURING_REVIEW``
     - bool
     - ``False``
     - Freeze draft edits (and block starting a new edit of a published record) for creators while request is actively under curator review.
   * - ``CURATIONS_ALLOW_CREATOR_CANCEL``
     - bool
     - ``False``
     - Permit record creators to withdraw / cancel their own curation requests.
   * - ``CURATIONS_CONSENT_MODAL_ENABLED``
     - bool
     - ``False``
     - Require confirmation modal with checkboxes before initiating curation.
   * - ``CURATIONS_CONSENT_CHECKBOX_TEXTS``
     - list[str]
     - 3 default texts
     - Mandatory checkbox labels for the consent modal.
   * - ``CURATIONS_TIMELINE_ABSOLUTE_DATES``
     - bool
     - ``False``
     - Show absolute formatted datetimes in timeline instead of relative times.
   * - ``CURATIONS_NOTIFICATIONS_OVERRIDE_EMAIL``
     - str | None
     - ``None``
     - Redirect all notification emails to a single test address (staging/dev).
   * - ``CURATIONS_ENABLE_REQUEST_COMMENTS``
     - bool
     - ``False``
     - Enable automatic diff comments on draft changes during curation.
   * - ``CURATIONS_COMMENTS_USE_USER_IDENTITY``
     - bool
     - ``False``
     - Attribute diff comments to the acting user instead of system identity.
   * - ``CURATIONS_COMMENT_TEMPLATE_FILE``
     - str
     - ``"invenio_curations/comment-template.html"``
     - Jinja template path for formatting curation diff comments.
   * - ``CURATIONS_COMMENTS_CLASSES``
     - list
     - ``[DiffDescription]``
     - Extensible diff element renderer classes.
   * - ``CURATIONS_MODERATION_ROLE``
     - str
     - ``"administration-rdm-records-curation"``
     - Identifier of role assigned to curation reviewers.
   * - ``CURATIONS_PRIVILEGED_ROLES``
     - list[str]
     - ``["administration"]``
     - Roles that bypass the curation workflow entirely (direct publish).
   * - ``CURATIONS_MODERATORS_CAN_MANAGE_FILES``
     - bool
     - ``False``
     - Grant moderators file-management rights on records/drafts with an associated curation request.
   * - ``CURATIONS_TIMELINE_PAGE_SIZE``
     - int
     - ``15``
     - Pagination size for curation request timeline items.
   * - ``CURATIONS_SEARCH_REQUESTS``
     - dict
     - facets & sort dict
     - Facets and sort options for the curation dashboard search.

Detailed Configuration Guide
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``CURATIONS_AUTO_PUBLISH_ON_ACCEPT``
""""""""""""""""""""""""""""""""""""

* **Type:** ``bool``
* **Default:** ``False``
* **Behavior:**
  When ``False`` (TU Graz default), accepting a curation request closes the request as ``accepted`` and leaves the record in draft state. The author or curator must subsequently open the deposit form and click "Publish" manually.
  When ``True``, accepting the curation request automatically publishes the record in a post-commit transaction hook, and the action button in the curation request UI is labeled "Accept and publish".
* **Use Case:**
  Institutions where curator approval is the definitive final authorization step and datasets should be made publicly available immediately without requiring the author to log back in to push "Publish".

.. code-block:: python

    CURATIONS_AUTO_PUBLISH_ON_ACCEPT = True


``CURATIONS_AUTO_SUBMIT_COMMUNITY``
"""""""""""""""""""""""""""""""""""

* **Type:** ``bool``
* **Default:** ``False``
* **Behavior:**
  Only relevant when ``CURATIONS_AUTO_PUBLISH_ON_ACCEPT = True`` and the record has a pending community-submission request.

  When ``False`` (default, "production" mode), the record is published immediately regardless of community status. The stale community-submission request is withdrawn and replaced with a community-*inclusion* request (``require_review=True``) against the now-published record, so a community manager can independently accept or decline it later without blocking publication - declining just leaves the record published without that community. As an exception, if the record's creator is themselves an owner/manager/curator of the target community, the community-submission is finished automatically instead: they already had the right to accept their own submission, so a further separate go-ahead would add nothing.

  When ``True`` ("migration" mode), the pending community-submission is submitted (if needed) and accepted right away regardless of who created it, hard-forcing the record into the community without any separate community review.
* **Use Case:**
  ``False`` for day-to-day operation, where community inclusion should stay under that community's own control unless the submitter already manages it. ``True`` for bulk migrations where every curated record must land in its community without extra manual steps.

.. code-block:: python

    CURATIONS_AUTO_SUBMIT_COMMUNITY = True


``CURATIONS_ALLOW_PUBLISHING_EDITS``
""""""""""""""""""""""""""""""""""""

* **Type:** ``bool``
* **Default:** ``False``
* **Behavior:**
  When ``False`` (default), any edits to the metadata of an already-published record require a new curation review before the revised version can be published.
  When ``True``, users can edit the metadata of their published records and publish those updates directly without another curation review.
* **Use Case:**
  Instances that consider an initial quality check sufficient and want to reduce staff workload for minor post-publication corrections (e.g. typo fixes, adding an ORCID or funding reference).

.. code-block:: python

    CURATIONS_ALLOW_PUBLISHING_EDITS = True


``CURATIONS_BLOCK_EDIT_DURING_REVIEW``
""""""""""""""""""""""""""""""""""""""

* **Type:** ``bool``
* **Default:** ``False``
* **Behavior:**
  When ``False`` (default), record creators can continue modifying and saving their draft while a curator is actively reviewing it.
  When ``True``, editing and saving drafts is blocked for non-curators while the request is in the ``review`` state - both continuing an already-open draft and starting a new edit of an already-published record (which would otherwise reopen it as a draft). The deposit save button and landing page edit button are disabled for creators. Curators retain permission to edit the draft to make corrections.
* **Use Case:**
  Prevents race conditions where an author changes metadata or files while a curator is in the middle of reviewing them.

.. code-block:: python

    CURATIONS_BLOCK_EDIT_DURING_REVIEW = True


``CURATIONS_ALLOW_CREATOR_CANCEL``
""""""""""""""""""""""""""""""""""

* **Type:** ``bool``
* **Default:** ``False``
* **Behavior:**
  When ``False`` (default), only curators or administrators can cancel a curation request.
  When ``True``, the creator of the record is permitted to cancel their own pending curation request.
* **Use Case:**
  Empowers authors to retract a submission if they realize they made a mistake or forgot an attachment, allowing them to make corrections and re-submit without waiting for a curator rejection.

.. code-block:: python

    CURATIONS_ALLOW_CREATOR_CANCEL = True


``CURATIONS_CONSENT_MODAL_ENABLED`` & ``CURATIONS_CONSENT_CHECKBOX_TEXTS``
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

* **Type:** ``bool`` (modal enabled), ``list[str]`` (checkbox labels)
* **Default:** ``CURATIONS_CONSENT_MODAL_ENABLED = False``
* **Behavior:**
  When ``False`` (default, TU Graz origin behavior), clicking "Start publication process" directly initiates the curation request without a modal popup.
  When ``True``, clicking the button opens a confirmation modal displaying mandatory checkboxes. The user must check all checkboxes before the "Confirm" button becomes active.
* **Use Case:**
  Legal compliance requiring researchers to explicitly certify data privacy adherence, institutional deposit policy agreement, or license confirmation prior to curation submission.

.. code-block:: python

    CURATIONS_CONSENT_MODAL_ENABLED = True
    CURATIONS_CONSENT_CHECKBOX_TEXTS = [
        "I accept the terms of service and repository policy.",
        "I confirm that this dataset contains no unanonymized personal data.",
        "I agree that this submission may be published upon curation approval.",
    ]


``CURATIONS_TIMELINE_ABSOLUTE_DATES``
"""""""""""""""""""""""""""""""""""""

* **Type:** ``bool``
* **Default:** ``False`` (also configurable via env var ``INVENIO_CURATIONS_TIMELINE_ABSOLUTE_DATES=true``)
* **Behavior:**
  When ``False`` (default), dates in the request timeline and metadata sidebar are rendered as relative times (e.g. "3 hours ago", "2 days ago").
  When ``True``, timestamps are displayed as locale-formatted absolute datetimes (e.g. "Sep 14, 2026, 10:30 AM").
* **Use Case:**
  Auditing, compliance, or institutional archives where exact chronological records of curation actions are legally or organizationally required.

.. code-block:: python

    CURATIONS_TIMELINE_ABSOLUTE_DATES = True


``CURATIONS_NOTIFICATIONS_OVERRIDE_EMAIL``
""""""""""""""""""""""""""""""""""""""""""

* **Type:** ``str | None``
* **Default:** ``None``
* **Behavior:**
  When set to an email address string, all curation-related notification emails (submit, resubmit, review, accept, critique) are redirected exclusively to this address, bypassing normal recipient resolution.
  When ``None`` (default), notifications are sent to the normal recipients (curation group members and creators).
* **Use Case:**
  Development, staging, and user-acceptance testing environments where notification flows must be verified without emailing real end-users or production mailing lists.

.. code-block:: python

    CURATIONS_NOTIFICATIONS_OVERRIDE_EMAIL = "curation-dev-testing@example.org"


``CURATIONS_ENABLE_REQUEST_COMMENTS`` & ``CURATIONS_COMMENTS_USE_USER_IDENTITY``
""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

* **Type:** ``bool``
* **Default:** ``False``
* **Behavior:**
  ``CURATIONS_ENABLE_REQUEST_COMMENTS = True`` activates automatic generation of metadata diff comments whenever a draft is updated during curation. The diff comments are posted into the curation request conversation.
  ``CURATIONS_COMMENTS_USE_USER_IDENTITY = True`` attributes these diff comments to the acting user's profile instead of the generic system identity.
* **Use Case:**
  Collaborative curation where curators need a quick, visual change-log of what the submitter modified in response to requested changes.

.. code-block:: python

    CURATIONS_ENABLE_REQUEST_COMMENTS = True
    CURATIONS_COMMENTS_USE_USER_IDENTITY = True


``CURATIONS_MODERATION_ROLE`` & ``CURATIONS_PRIVILEGED_ROLES``
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

* **Type:** ``str`` (moderation role), ``list[str]`` (privileged roles)
* **Default:**
  - ``CURATIONS_MODERATION_ROLE = "administration-rdm-records-curation"``
  - ``CURATIONS_PRIVILEGED_ROLES = ["administration"]``
* **Behavior:**
  Users with ``CURATIONS_MODERATION_ROLE`` have permission to review, critique, accept, and cancel curation requests.
  Users with any role in ``CURATIONS_PRIVILEGED_ROLES`` bypass the curation workflow entirely and can publish records directly without a curation review.
* **Use Case:**
  Assigning curation permissions to dedicated library or research data management teams, and allowing system administrators or batch data loaders to publish without review delays.

.. code-block:: python

    CURATIONS_MODERATION_ROLE = "rdm-curators"
    CURATIONS_PRIVILEGED_ROLES = ["administration", "system-importer"]


``CURATIONS_MODERATORS_CAN_MANAGE_FILES``
"""""""""""""""""""""""""""""""""""""""""

* **Type:** ``bool``
* **Default:** ``False``
* **Behavior:**
  When ``False`` (default), file management (uploading, removing, or reordering files) follows the normal record permissions only, independent of any curation request.
  When ``True``, users with ``CURATIONS_MODERATION_ROLE`` are also granted file-management rights on any record/draft that has an associated curation request, regardless of that request's status.
* **Use Case:**
  Lets curators fix file-level issues (wrong format, missing file, accidental upload) as part of the review, without needing to hand editing rights back to the creator first.

.. code-block:: python

    CURATIONS_MODERATORS_CAN_MANAGE_FILES = True
