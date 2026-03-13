// This file is part of InvenioRDM
// Copyright (C) 2024 TU Wien.
// Copyright (C) 2024-2025 Graz University of Technology.
//
// Invenio-Curations is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.

import React, { useState } from "react";
import { Button, Icon, Popup, Checkbox, Modal } from "semantic-ui-react";
import RequestStatusLabel from "@js/invenio_requests/request/RequestStatusLabel";
import { PublishButton } from "@js/invenio_rdm_records";
import PropTypes from "prop-types";
import { i18next } from "@translations/invenio_curations/i18next";

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
  let elem = null;

  // moved hooks out of conditional so they're always called
  const [modalOpen, setModalOpen] = useState(false);
  const [checks, setChecks] = useState({
    opt1: false,
    opt2: false,
    opt3: false,
  });

  const toggle = (key) => {
    setChecks((p) => ({ ...p, [key]: !p[key] }));
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
  }

  if (request) {
    switch (request.status) {
      case "accepted":
        // For published records, user must resubmit changes for review
        if (record?.is_published) {
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
    // show a tooltip when NOT curateable, otherwise show a modal with 3 checkboxes
    if (!recordCurateable) {
      elem = (
        <Popup
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
                onClick={handleCreateRequest}
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
      );
    } else {
      // curateable: show modal with three checkboxes
      const allChecked = checks.opt1 && checks.opt2 && checks.opt3;

    elem = (
      <>
        <Button
        onClick={() => {
          console.log("[CURATIONS] Start publication button clicked - opening modal");
          setModalOpen(true);
        }}
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

        <Modal open={modalOpen} onClose={() => setModalOpen(false)}>
        <Modal.Header>{i18next.t("Are you sure you want to publish this entry?")}</Modal.Header>
        <Modal.Content>
          <div className="ui warning message">
            <strong>
              <i class="exclamation triangle icon"></i>
            {i18next.t("Once the record is published you will no longer be able to change the files in the upload! However, you will still be able to update the record's metadata later.")}
            </strong>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <div className="ui checkbox">
              <input
                type="checkbox"
                checked={checks.opt1}
                onChange={() => toggle("opt1")}
              />
              <label onClick={() => toggle("opt1")}>
                {i18next.t("I accept the")}{" "}
                <a
                  href="/terms-of-service"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  {i18next.t("terms of service")}
                </a>{" "}
                {i18next.t("and")}{" "}
                <a
                  href="/privacy-policy"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  {i18next.t("privacy policy")}
                </a>
              </label>
            </div>
            <div className="ui checkbox">
              <input
                type="checkbox"
                checked={checks.opt2}
                onChange={() => toggle("opt2")}
              />
              <label onClick={() => toggle("opt2")}>
                {i18next.t("I accept the")}{" "}
                <a
                  href="/curation-policy"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  {i18next.t("curation policy")}
                </a>
              </label>
            </div>
            <Checkbox
            label={i18next.t("I confirm that ULB will publish my dataset in its final form.")}
            checked={checks.opt3}
            onChange={() => toggle("opt3")}
            />
          </div>
        </Modal.Content>
        <Modal.Actions>
          <Button className={"left floated"} onClick={() => setModalOpen(false)}>
            {i18next.t("Cancel")}
          </Button>
          <Button
            primary
            onClick={async () => {
            if (!allChecked) {
              return;
            }
            try {
              // pass-through to caller; adjust if you need to send checkbox state
              await handleCreateRequest();
            } catch (error) {
              console.error("Curation request failed:", error);
            }
            setModalOpen(false);
            }}
            loading={!hasUploadInProgress && loading}
            disabled={!allChecked}
          >
            {i18next.t("Confirm")}
          </Button>
        </Modal.Actions>
        </Modal>
      </>
    );
    }
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
