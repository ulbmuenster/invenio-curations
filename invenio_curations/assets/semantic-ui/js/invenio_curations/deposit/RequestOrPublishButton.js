// This file is part of InvenioRDM
// Copyright (C) 2024 TU Wien.
// Copyright (C) 2024 Graz University of Technology.
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
  const { request, record, handleCreateRequest, handleResubmitRequest, loading } =
    props;
  const recordCurateable = record?.id != null && record?.savedSuccessfully;
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

  if (request) {
    switch (request.status) {
      case "accepted":
        elem = <PublishButton fluid record={record} />;
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
          content={i18next.t(
            "Before creating a curation request, the draft has to be saved without any errors."
          )}
          position="top center"
          trigger={
            <span>
              <Button
                onClick={handleCreateRequest}
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
        onClick={() => setModalOpen(true)}
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
        {i18next.t("Start publication process")}
        </Button>

        <Modal open={modalOpen} onClose={() => setModalOpen(false)} size="tiny">
        <Modal.Header>{i18next.t("Start publication process")}</Modal.Header>
        <Modal.Content>
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
          <Button onClick={() => setModalOpen(false)}>
            {i18next.t("Cancel")}
          </Button>
          <Button
            primary
            onClick={() => {
            if (!allChecked) return;
            // pass-through to caller; adjust if you need to send checkbox state
            handleCreateRequest();
            setModalOpen(false);
            }}
            loading={loading}
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
  handleCreateRequest: PropTypes.func.isRequired,
  handleResubmitRequest: PropTypes.func.isRequired,
  loading: PropTypes.bool,
};

RequestOrPublishButton.defaultProps = {
  request: null,
  record: null,
  loading: false,
};
