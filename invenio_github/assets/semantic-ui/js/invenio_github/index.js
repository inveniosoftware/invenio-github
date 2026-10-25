// This file is part of InvenioGithub
// Copyright (C) 2023-2026 CERN.
//
// Invenio Github is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.
import $ from "jquery";

function addResultMessage(element, color, icon, message) {
  element.classList.remove("hidden", "positive", "negative", "warning");
  element.classList.add(color);
  element.querySelector(`.icon`).className = `${icon} small icon`;
  element.querySelector(".content").textContent = message;
}

function hideAfter(element, delay) {
  setTimeout(function () {
    element.classList.add("hidden");
  }, delay);
}

// function from https://www.w3schools.com/js/js_cookies.asp
function getCookie(cname) {
  let name = cname + "=";
  let decodedCookie = decodeURIComponent(document.cookie);
  let ca = decodedCookie.split(";");
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) === " ") {
      c = c.substring(1);
    }
    if (c.indexOf(name) === 0) {
      return c.substring(name.length, c.length);
    }
  }
  return "";
}

const REQUEST_HEADERS = {
  "Content-Type": "application/json",
  "X-CSRFToken": getCookie("csrftoken"),
};

// Ids rendered by settings/index.html and settings/helpers.html.
const REPOSITORIES_ID = "github-repositories";
const LAST_SYNC_ID = "sync_repos_help_text";

function initDoiBadgeModals(container) {
  $(container)
    .find(".doi-badge-modal")
    .modal({
      selector: {
        close: ".close.button",
      },
      onShow: function () {
        const modalId = $(this).attr("id");
        $(`#${modalId}-trigger`).attr("aria-expanded", true);
      },
      onHide: function () {
        const modalId = $(this).attr("id");
        $(`#${modalId}-trigger`).attr("aria-expanded", false);
      },
    });
}

/**
 * Replace the content of a container, keeping keyboard focus on the same
 * control (a switch, a badge or a link) if it was inside.
 */
function replaceKeepingFocus(container, html) {
  const focused = document.activeElement;
  let selector = null;
  if (container.contains(focused) && focused !== container) {
    if (focused.dataset.repoId) {
      selector = `input[data-repo-id="${focused.dataset.repoId}"]`;
    } else if (focused.id) {
      selector = `[id="${focused.id}"]`;
    } else if (focused.getAttribute("href")) {
      selector = `[href="${focused.getAttribute("href")}"]`;
    }
  }
  container.innerHTML = html;
  if (selector) {
    container.querySelector(selector)?.focus();
  }
}

/**
 * Re-render the repository lists and the last sync time from the server.
 *
 * Resolves to false, and never throws, when the page cannot be refreshed in
 * place: when it was rendered by templates without the refresh ids, when the
 * session expired or when the request failed. Callers then ask the user to
 * reload the page instead.
 */
async function refreshRepositoryLists() {
  const lists = document.getElementById(REPOSITORIES_ID);
  if (!lists) {
    return false;
  }

  try {
    const response = await fetch(window.location.href, {
      cache: "no-store",
      credentials: "same-origin",
    });
    if (!response.ok) {
      console.warn(`Repository lists not refreshed: HTTP ${response.status}`);
      return false;
    }
    const page = new DOMParser().parseFromString(
      await response.text(),
      "text/html"
    );
    const freshLists = page.getElementById(REPOSITORIES_ID);
    if (!freshLists) {
      console.warn("Repository lists not refreshed: no lists in the response");
      return false;
    }

    // Initialised modals live in the page dimmer, outside of the lists; remove
    // them so that their re-rendered copies do not duplicate their ids.
    $(".doi-badge-modal").remove();
    replaceKeepingFocus(lists, freshLists.innerHTML);
    initDoiBadgeModals(lists);

    const lastSync = document.getElementById(LAST_SYNC_ID);
    const freshLastSync = page.getElementById(LAST_SYNC_ID);
    if (lastSync && freshLastSync) {
      lastSync.innerHTML = freshLastSync.innerHTML;
    }
    return true;
  } catch (error) {
    console.warn("Repository lists not refreshed:", error);
    return false;
  }
}

const syncButton = document.getElementById("sync_repos");

/**
 * Allow one sync or enable/disable at a time.
 *
 * Each of them re-renders the lists when it completes, which would replace the
 * switch of another request still in flight and lose its result.
 */
function setBusy(busy) {
  if (syncButton) {
    syncButton.disabled = busy;
    syncButton.classList.toggle("disabled", busy);
  }
  if (busy) {
    // Switches the server rendered as disabled are left alone.
    document
      .querySelectorAll(".repository-item input[data-repo-id]:not(:disabled)")
      .forEach((toggle) => {
        toggle.disabled = true;
        toggle.dataset.busy = "true";
      });
  } else {
    document
      .querySelectorAll(".repository-item input[data-busy]")
      .forEach((toggle) => {
        toggle.disabled = false;
        delete toggle.dataset.busy;
      });
  }
}

function fetchWithTimeout(url, options, timeout = 100000) {
  /** Timeout set to 100000 ms = 1m40s .*/
  return Promise.race([
    fetch(url, options),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error("timeout")), timeout)
    ),
  ]);
}

if (syncButton) {
  syncButton.addEventListener("click", function () {
    const resultMessage = document.getElementById("sync-result-message");
    const loaderIcon = document.getElementById("loader_icon");
    const buttonTextElem = document.getElementById("sync_repos_btn_text");
    const buttonText = buttonTextElem.innerHTML;
    const loadingText = syncButton.dataset.loadingText;

    buttonTextElem.innerHTML = loadingText;
    loaderIcon.classList.add("loading");
    setBusy(true);

    syncRepos();

    async function syncRepos() {
      try {
        const response = await fetchWithTimeout(
          "/api/user/github/repositories/sync",
          { method: "POST", headers: REQUEST_HEADERS }
        );
        if (response.ok) {
          const refreshed = await refreshRepositoryLists();
          addResultMessage(
            resultMessage,
            "positive",
            "checkmark",
            refreshed
              ? "Repositories synced successfully."
              : "Repositories synced successfully. Some items may still be updating, please reload the page in about a minute."
          );
        } else {
          addResultMessage(
            resultMessage,
            "negative",
            "cancel",
            `Request failed with status code: ${response.status}`
          );
        }
        hideAfter(resultMessage, 10000);
      } catch (error) {
        if (error.message === "timeout") {
          addResultMessage(
            resultMessage,
            "warning",
            "hourglass",
            "This action seems to take some time, refresh the page after several minutes to inspect the synchronisation."
          );
        } else {
          addResultMessage(
            resultMessage,
            "negative",
            "cancel",
            `There has been a problem: ${error}`
          );
          hideAfter(resultMessage, 7000);
        }
      } finally {
        loaderIcon.classList.remove("loading");
        buttonTextElem.innerHTML = buttonText;
        setBusy(false);
      }
    }
  });
}

function switchMessageOf(toggle) {
  return toggle
    .closest(".repository-item")
    .querySelector(".repo-switch-message");
}

function showSwitchResult(toggle, color, icon, message, delay) {
  const switchMessage = switchMessageOf(toggle);
  addResultMessage(switchMessage, color, icon, message);
  hideAfter(switchMessage, delay);
}

function revertToggle(toggle) {
  toggle.checked = !toggle.checked;
  updateToggleAriaLabel(toggle);
}

async function toggleRepository(toggle) {
  const repoId = toggle.dataset.repoId;
  const enable = toggle.checked;
  const action = enable ? "enable" : "disable";

  setBusy(true);
  let failure = null;
  try {
    const response = await fetch(
      `/api/user/github/repositories/${repoId}/${action}`,
      { method: "POST", headers: REQUEST_HEADERS }
    );
    if (!response.ok) {
      failure = `Request failed with status code: ${response.status}`;
    }
  } catch (error) {
    failure = `There has been a problem: ${error}`;
  }

  // Only a successful request changed the server state worth re-rendering.
  const refreshed = !failure && (await refreshRepositoryLists());
  setBusy(false);

  let result;
  if (failure) {
    revertToggle(toggle);
    result = ["negative", "cancel", failure, 7000];
  } else if (refreshed) {
    const text = enable ? "Repository enabled." : "Repository disabled.";
    result = ["positive", "checkmark", text, 10000];
  } else {
    const text = "Repository synced successfully. Please reload the page.";
    result = ["positive", "checkmark", text, 10000];
  }

  // Look the switch up again: a refresh replaces it, in its new list.
  const current = document.querySelector(
    `.repository-item input[data-repo-id="${repoId}"]`
  );
  if (!current) {
    // Gone from the refreshed lists, e.g. deleted on GitHub meanwhile.
    const resultMessage = document.getElementById("sync-result-message");
    addResultMessage(resultMessage, ...result.slice(0, 3));
    hideAfter(resultMessage, result[3]);
    return;
  }
  // Keep the user's place on the repository, unless they moved on meanwhile.
  const focused = document.activeElement;
  if (!focused || focused === document.body || focused === current) {
    current.focus();
  }
  showSwitchResult(current, ...result);
}

// Delegated, so that switches keep working after the lists are re-rendered.
document.addEventListener("change", function (event) {
  if (event.target.matches(".repository-item input[data-repo-id]")) {
    toggleRepository(event.target);
  }
});

// DOI badge modal
initDoiBadgeModals(document);

function showDoiBadgeModal(trigger) {
  const modalId = $(trigger).attr("aria-controls");
  $(`#${modalId}.doi-badge-modal`).modal("show");
}

// Delegated, so that badges keep working after the lists are re-rendered.
$(document).on("click", ".doi-modal-trigger", function (event) {
  showDoiBadgeModal(event.target);
});

$(document).on("keydown", ".doi-modal-trigger", function (event) {
  if (event.key === "Enter") {
    showDoiBadgeModal(event.target);
  }
});

// ON OFF toggle a11y
function updateToggleAriaLabel(toggle) {
  const $toggle = $(toggle);
  const label = toggle.checked
    ? $toggle.data("checked-aria-label")
    : $toggle.data("unchecked-aria-label");
  $toggle.attr("aria-label", label);
}

$(document).on("change", ".toggle.on-off input", function (event) {
  updateToggleAriaLabel(event.target);
});
