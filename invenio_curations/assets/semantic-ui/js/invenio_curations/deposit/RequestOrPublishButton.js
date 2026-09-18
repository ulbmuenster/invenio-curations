// This file is part of InvenioRDM
// Copyright (C) 2024 TU Wien.
// Copyright (C) 2024-2025 Graz University of Technology.
//
// Invenio-Curations is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.

import React, { useState } from "react";
import { Button, Checkbox, Icon, Modal, Popup } from "semantic-ui-react";
import RequestStatusLabel from "@js/invenio_requests/request/RequestStatusLabel";
import { PublishButton } from "@js/invenio_rdm_records";
import PropTypes from "prop-types";
import { i18next } from "@translations/invenio_curations/i18next";

const defaultConsentCheckboxTexts = [
  i18next.t("I accept the terms of service and privacy policy."),
  i18next.t("I accept the curation policy."),
  i18next.t("I confirm that the record may be published in its final form."),
];

export const RequestOrPublishButton = (props) => {
  const {
    request,
    record,
    curationsData,
    handleCreateRequest,
    handleResubmitRequest,
    loading,
    formik,
    files,
  } = props;

  // Check if any files are currently uploading
  // InvenioRDM tracks this with isFileUploadInProgress flag in the files state
  const hasUploadInProgress = files?.isFileUploadInProgress || false;

  const recordCurateable =
    record?.id != null && record?.savedSuccessfully && !hasUploadInProgress;
  const isDirty = formik?.dirty;
  const consentModal = curationsData?.consent_modal;
  const consentEnabled = consentModal?.enabled ?? false;
  const checkboxTexts = consentModal?.checkbox_texts || defaultConsentCheckboxTexts;
  const [consentOpen, setConsentOpen] = useState(false);
  const [checked, setChecked] = useState({});
  let elem = null;

  const closeConsent = () => {
    setConsentOpen(false);
    setChecked({});
  };

  // 2 special cases:
  // - user is privileged: should bypass curation workflow
  // - record is published && user edits it && allow_publishing_edits=false => action
  // is rather a "resubmit" than a "publish"
  if (curationsData?.is_privileged) {
    elem = <PublishButton fluid record={record} />;
    return elem;
  }
  if (
    record?.is_published &&
    !curationsData?.publishing_edits &&
    request?.status == "pending_resubmission"
  ) {
    elem = (
      <Button
        onClick={handleResubmitRequest}
        loading={loading}
        primary
        size="medium"
        type="button"
        disabled={!recordCurateable}
        positive
        icon
        labelPosition="left"
        fluid
      >
        <Icon name="paper hand outline" />
        {i18next.t("Resubmit published record")}
      </Button>
    );
    return elem;
  } else if (!record?.is_published && request?.status == "pending_resubmission") {
    elem = (
      <Button
        onClick={handleResubmitRequest}
        loading={loading}
        primary
        size="medium"
        type="button"
        disabled={!recordCurateable}
        positive
        icon
        labelPosition="left"
        fluid
      >
        <Icon name="paper hand outline" />
        {i18next.t("Resubmit updated record")}
      </Button>
    );
    return elem;
  }

  if (request) {
    switch (request.status) {
      case "accepted":
        // When auto-publish on accept is enabled, accepted records are already published automatically.
        // Thus an unpublished draft for an already published record represents new changes that need resubmission.
        // When auto-publish is off (vanilla TU Graz behavior), the user can publish their accepted record.
        if (
          curationsData?.auto_publish_on_accept &&
          record?.is_published &&
          !curationsData?.publishing_edits
        ) {
          elem = (
            <Button
              onClick={handleResubmitRequest}
              loading={loading}
              primary
              size="medium"
              type="button"
              disabled={!recordCurateable}
              positive
              icon
              labelPosition="left"
              fluid
            >
              <Icon name="paper hand outline" />
              {i18next.t("Resubmit for review")}
            </Button>
          );
        } else if (isDirty || !record?.savedSuccessfully) {
          elem = (
            <Popup
              content={i18next.t("Please save your changes before publishing.")}
              trigger={
                <span>
                  <Button
                    primary
                    disabled
                    fluid
                    size="medium"
                    type="button"
                    icon
                    labelPosition="left"
                  >
                    <Icon name="upload" />
                    {i18next.t("Publish")}
                  </Button>
                </span>
              }
            />
          );
        } else {
          elem = <PublishButton fluid record={record} />;
        }
        break;

      case "critiqued":
        elem = (
          <Button
            onClick={handleResubmitRequest}
            loading={loading}
            primary
            size="medium"
            type="button"
            disabled={!recordCurateable}
            positive
            icon
            labelPosition="left"
            fluid
          >
            <Icon name="paper hand outline" />
            {i18next.t("Resubmit updated record")}
          </Button>
        );
        break;

      default:
        elem = (
          <span style={{ display: "flex", gap: "0.25em" }}>
            <Button
              as="a"
              href={`/me/requests/${request.id}`}
              icon
              labelPosition="left"
              size="medium"
              positive
              fluid
            >
              {i18next.t("View request")}
              <Icon name="right arrow" />
            </Button>
            <RequestStatusLabel status={request.status} />
          </span>
        );
    }
  } else {
    const createRequest = consentEnabled
      ? () => setConsentOpen(true)
      : handleCreateRequest;
    const allChecked = checkboxTexts.every((_, index) => checked[index]);

    elem = (
      <>
        <Popup
          disabled={recordCurateable}
          content={
            hasUploadInProgress
              ? i18next.t(
                  "Please wait for all file uploads to complete before starting the publication process."
                )
              : i18next.t(
                  "Before creating a curation request, the draft has to be saved without any errors."
                )
          }
          position="top center"
          trigger={
            <span>
              <Button
                onClick={createRequest}
                loading={!hasUploadInProgress && loading}
                primary
                size="medium"
                type="button"
                disabled={!recordCurateable}
                positive
                icon
                labelPosition="left"
                fluid
              >
                <Icon name="paper hand outline" />
                {i18next.t("Start publication process")}
              </Button>
            </span>
          }
        />
        {consentEnabled && (
          <Modal open={consentOpen} onClose={closeConsent}>
            <Modal.Header>
              {i18next.t("Are you sure you want to publish this entry?")}
            </Modal.Header>
            <Modal.Content>
              <div className="ui warning message">
                <strong>
                  <Icon name="exclamation triangle" />
                  {i18next.t(
                    "Once the record is published you will no longer be able to change the files in the upload! However, you will still be able to update the record's metadata later."
                  )}
                </strong>
              </div>
              {checkboxTexts.map((text, index) => (
                <Checkbox
                  key={text}
                  className="mb-10"
                  style={{ display: "block" }}
                  label={i18next.t(text)}
                  checked={Boolean(checked[index])}
                  onChange={() =>
                    setChecked((current) => ({
                      ...current,
                      [index]: !current[index],
                    }))
                  }
                />
              ))}
            </Modal.Content>
            <Modal.Actions>
              <Button className="left floated" onClick={closeConsent}>
                {i18next.t("Cancel")}
              </Button>
              <Button
                primary
                loading={loading}
                disabled={loading || !allChecked}
                onClick={async () => {
                  await handleCreateRequest();
                  closeConsent();
                }}
              >
                {i18next.t("Confirm")}
              </Button>
            </Modal.Actions>
          </Modal>
        )}
      </>
    );
  }

  return elem;
};

RequestOrPublishButton.propTypes = {
  request: PropTypes.object,
  record: PropTypes.object,
  curationsData: PropTypes.object,
  handleCreateRequest: PropTypes.func.isRequired,
  handleResubmitRequest: PropTypes.func.isRequired,
  loading: PropTypes.bool,
  formik: PropTypes.object,
  files: PropTypes.object,
};

RequestOrPublishButton.defaultProps = {
  request: null,
  record: null,
  curationsData: null,
  loading: false,
  formik: null,
  files: null,
};
