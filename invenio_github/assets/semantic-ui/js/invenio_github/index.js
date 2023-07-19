// This file is part of InvenioGithub
// Copyright (C) 2023 CERN.
//
// Invenio Github is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.
import $ from "jquery";

function addResultMessage(element, color, icon, message) {
  element.classList.remove("hidden");
  element.classList.add(color);
  element.querySelector(`.icon`).className = `${icon} small icon`;
  element.querySelector(".content").textContent = message;
}

const sync_button = document.getElementById("sync_repos");
if (sync_button) {
  sync_button.addEventListener("click", function () {
    const resultMessage = document.getElementById("sync-result-message");
    const loaderIcon = document.getElementById("loader_icon");
    const buttonTextElem = document.getElementById("sync_repos_btn_text");
    const buttonText = buttonTextElem.innerHTML;
    const loadingText = sync_button.dataset.loadingText;
    const url = "/api/user/github/repositories/sync";
    const request = new Request(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    buttonTextElem.innerHTML = loadingText;
    loaderIcon.classList.add("loading");

    syncRepos(request);

    async function syncRepos(request) {
      try {
        const response = await fetch(request);
        loaderIcon.classList.remove("loading");
        buttonTextElem.innerHTML = buttonText;
        if (response.ok) {
          addResultMessage(resultMessage, "positive", "checkmark", "Repositories synced successfully. Please reload the page."
          );
          setTimeout(function () {
            resultMessage.classList.add("hidden");
          }, 10000);
        } else {
          addResultMessage(resultMessage,"negative", "cancel", `Request failed with status code: ${response.status}`
          );
          setTimeout(function () {
            resultMessage.classList.add("hidden");
          }, 10000);
        }
      } catch (error) {
        loaderIcon.classList.remove("loading");
        addResultMessage(resultMessage, "negative", "cancel", `There has been a problem: ${error}`);
        setTimeout(function () {
          resultMessage.classList.add("hidden");
        }, 7000);
      }
    }
  });
}

const repositories = document.getElementsByClassName("repository-item");
if (repositories) {
  for (const repo of repositories) {
    repo.addEventListener("change", function (event) {
      sendEnableDisableRequest(event.target.checked, repo);
    });
  }
}

function sendEnableDisableRequest(checked, repo) {
  const repo_id = repo.querySelector("input[data-repo-id]").getAttribute("data-repo-id");
  const switchMessage = repo.querySelector(".repo-switch-message");

  let url;
  if (checked === true) {
    url = "/api/user/github/repositories/" + repo_id + "/enable";
  } else {
    if (checked === false) {
      url = "/api/user/github/repositories/" + repo_id + "/disable";
    }
  }

  const request = new Request(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  sendRequest(request);

  async function sendRequest(request) {
    try {
      const response = await fetch(request);
      if (response.ok) {
        addResultMessage(switchMessage, "positive", "checkmark", "Repository synced successfully. Please reload the page."
        );
        setTimeout(function () {
          switchMessage.classList.add("hidden");
        }, 10000);
      }
      else {
        addResultMessage(switchMessage, "negative", "cancel", `Request failed with status code: ${response.status}`
        );
        setTimeout(function () {
          switchMessage.classList.add("hidden");
        }, 5000);
      }
    } catch (error) {
      addResultMessage(switchMessage, "negative", "cancel", `There has been a problem: ${error}`);
      setTimeout(function () {
        switchMessage.classList.add("hidden");
      }, 7000);
    }
  }
}


// DOI badge modal
$(".doi-badge-modal").modal({
  selector: {
    close: ".close.button"
  },
  onShow: function() {
    const modalId = $(this).attr("id");
    const $modalTrigger = $(`#${modalId}-trigger`);
    $modalTrigger.attr('aria-expanded', true);
  },
  onHide: function() {
    const modalId = $(this).attr("id");
    const $modalTrigger = $(`#${modalId}-trigger`);
    $modalTrigger.attr('aria-expanded', false);
  }
});

$(".doi-modal-trigger").on("click", function (event) {
  const modalId = $(event.target).attr("aria-controls");
  $(`#${modalId}.doi-badge-modal`).modal("show");
})

$(".doi-modal-trigger").on("keydown", function (event) {
  if(event.key === "Enter") {
    const modalId = $(event.target).attr("aria-controls");
    $(`#${modalId}.doi-badge-modal`).modal("show");
  }
})


// ON OFF toggle a11y
const $onOffToggle = $(".toggle.on-off");

$onOffToggle && $onOffToggle.on("change", (event) => {
  const target = $(event.target);
  const $onOffToggleCheckedAriaLabel = target.data("checked-aria-label");
  const $onOffToggleUnCheckedAriaLabel = target.data("unchecked-aria-label");
  if (event.target.checked) {
    target.attr("aria-label", $onOffToggleCheckedAriaLabel)
  } else {
    target.attr("aria-label", $onOffToggleUnCheckedAriaLabel)
  }
})
