// This file is part of InvenioGithub
// Copyright (C) 2023 CERN.
//
// Invenio Github is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.
import $ from "jquery";

function addResultMessage(element, color, message) {
  element.classList.remove("hidden");
  element.classList.add("basic");
  element.classList.add(color);
  element.textContent = message;
}

const sync_button = document.getElementById("sync_repos");
if (sync_button) {
  sync_button.addEventListener("click", function () {
    const resultMessage = document.getElementById("sync-result-message");
    const loaderIcon = document.getElementById("loaderIcon");
    loaderIcon.classList.add("loading");
    const url = "/api/user/github/repositories/sync";
    const request = new Request(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    syncRepos(request);

    async function syncRepos(request) {
      try {
        const response = await fetch(request);
        loaderIcon.classList.remove("loading");
        if (response.ok) {
          addResultMessage(resultMessage,"green","Repositories synced successfully. Please reload the page."
          );
          setTimeout(function () {
            resultMessage.classList.add("hidden");
          }, 5000);
        } else {
          addResultMessage(resultMessage,"red", `Request failed with status code: ${response.status}`
          );
          setTimeout(function () {
            resultMessage.classList.add("hidden");
          }, 5000);
        }
      } catch (error) {
        loaderIcon.classList.remove("loading");
        addResultMessage(resultMessage, "red", `There has been a problem: ${error}`);
        setTimeout(function () {
          resultMessage.classList.add("hidden");
        }, 7000);
      }
    }
  });
}

const repositories = document.getElementsByClassName("repositories-list");
if (repositories) {
  for (const repo of repositories) {
    repo.addEventListener("change", function (event) {
      sendEnableDisableRequest(event.target.checked, repo);
    });
  }
}

function sendEnableDisableRequest(checked, repo) {
  const repo_id = repo.querySelector("input[data-repo-id]").getAttribute("data-repo-id");
  const switchMessage = repo.querySelector("#repo-switch-message");

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
      if (!response.ok) {
        addResultMessage(switchMessage, "red", `Request failed with status code: ${response.status}`
        );
        setTimeout(function () {
          switchMessage.classList.add("hidden");
        }, 5000);
      }
    } catch (error) {
      addResultMessage(switchMessage, "red", `There has been a problem: ${error}`);
      setTimeout(function () {
        switchMessage.classList.add("hidden");
      }, 7000);
    }
  }
}

$(".doi-badge-img").on("click", function () {
  $(".doi-badge-modal").modal("show");
});
