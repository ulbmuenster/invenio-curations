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

/**
 * Render a single configurable checkbox item.
 *
 * Each item is a plain object from CURATIONS_PUBLISH_CONFIRM_CHECKBOXES:
 *   { label, link?, link_label? }
 *
 * When `link` is present it is appended as an anchor after the label text.
 */
const ConfirmCheckbox = ({ item, checked, onChange }) => {
  const label = item.link ? (
    <label>
      {item.label}{" "}
      <a
        href={item.link}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
      >
        {item.link_label || item.link}
      </a>
    </label>
  ) : (
    <label>{item.label}</label>
  );

  return <Checkbox checked={checked} onChange={onChange} label={label} />;
};

ConfirmCheckbox.propTypes = {
  item: PropTypes.shape({
    label: PropTypes.string.isRequired,
    link: PropTypes.string,
    link_label: PropTypes.string,
  }).isRequired,
  checked: PropTypes.bool.isRequired,
  onChange: PropTypes.func.isRequired,
};

export const RequestOrPublishButton = (props) => {
  const {
    request,
    record,
    curationsData,
    handleCreateRequest,
    handleResubmitRequest,
    loading,
  } = props;
  const recordCurateable = record?.id != null && record?.savedSuccessfully;

  const checkboxItems = curationsData?.publish_confirm_checkboxes ?? [];
  const hasCheckboxes = checkboxItems.length > 0;

  // Checkbox state: one boolean per configured item — always initialised
  // (hooks must not be called conditionally).
  const [modalOpen, setModalOpen] = useState(false);
  const [checks, setChecks] = useState(() => checkboxItems.map(() => false));
  const allChecked = checks.every(Boolean);

  const toggleCheck = (idx) =>
    setChecks((prev) => prev.map((v, i) => (i === idx ? !v : v)));

  const openModal = () => {
    setChecks(checkboxItems.map(() => false));
    setModalOpen(true);
  };

  const handleConfirm = async () => {
    setModalOpen(false);
    await handleCreateRequest();
  };

  let elem = null;

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
  } else if (
    !record?.is_published &&
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
        {i18next.t("Resubmit updated record")}
      </Button>
    );
    return elem;
  }

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
    const publishButton = (
      <Button
        onClick={hasCheckboxes ? openModal : handleCreateRequest}
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
    );

    elem = (
      <>
        <Popup
          disabled={recordCurateable}
          content={i18next.t(
            "Before creating a curation request, the draft has to be saved without any errors."
          )}
          position="top center"
          trigger={<span>{publishButton}</span>}
        />

        {hasCheckboxes && (
          <Modal open={modalOpen} onClose={() => setModalOpen(false)} size="small">
            <Modal.Header>
              {i18next.t("Are you sure you want to publish this entry?")}
            </Modal.Header>
            <Modal.Content>
              <div
                style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}
              >
                {checkboxItems.map((item, idx) => (
                  <ConfirmCheckbox
                    key={idx}
                    item={item}
                    checked={checks[idx]}
                    onChange={() => toggleCheck(idx)}
                  />
                ))}
              </div>
            </Modal.Content>
            <Modal.Actions>
              <Button onClick={() => setModalOpen(false)}>
                {i18next.t("Cancel")}
              </Button>
              <Button
                primary
                disabled={!allChecked}
                loading={loading}
                onClick={handleConfirm}
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
};

RequestOrPublishButton.defaultProps = {
  request: null,
  record: null,
  curationsData: null,
  loading: false,
};
