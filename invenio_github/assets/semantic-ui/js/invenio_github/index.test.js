// This file is part of InvenioGithub
// Copyright (C) 2026 CERN.
//
// Invenio Github is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.

// Markup mirrors templates/semantic-ui/invenio_github/settings/{index,helpers,index_item}.html.
function doiBadge(id) {
  return `
    <img role="button" tabindex="0" id="modal-${id}-trigger" aria-controls="modal-${id}"
      class="doi-modal-trigger" alt="DOI" />
    <div id="modal-${id}" class="ui modal doi-badge-modal"></div>`;
}

// `locked`: managed by another user of the organisation, rendered disabled.
function repositoryItem({ id, name, enabled, doi = false, locked = false }) {
  return `
    <li class="ui segment">
      <div class="ui grid repository-item">
        <a href="/account/settings/github/repository/${name}"><b>${name}</b></a>
        ${doi ? doiBadge(id) : ""}
        <div class="repo-switch-message ui message hidden">
          <i class="icon"></i><p role="alert" class="content"></p>
        </div>
        <div class="ui toggle on-off checkbox">
          <input type="checkbox" ${enabled ? "checked" : ""} ${
    locked ? "disabled" : ""
  } data-repo-id="${id}"
            data-checked-aria-label="Disable ${name}" data-unchecked-aria-label="Enable ${name}"
            aria-label="${enabled ? "disable" : "enable"} ${name}" />
          <label></label>
        </div>
      </div>
    </li>`;
}

function repositoryLists(repositories) {
  if (repositories.length === 0) {
    return `<section aria-label="Repositories"><p>You have no repositories on GitHub.</p></section>`;
  }
  const enabled = repositories.filter((repo) => repo.enabled);
  const disabled = repositories.filter((repo) => !repo.enabled);
  return `
    <section aria-label="Enabled Repositories"><ul>${enabled
      .map(repositoryItem)
      .join("")}</ul></section>
    <section aria-label="Repositories"><ul>${disabled
      .map(repositoryItem)
      .join("")}</ul></section>`;
}

function settingsPage({
  repositories,
  lastSync = "(updated an hour ago)",
  markers = true,
}) {
  const lists = repositoryLists(repositories);
  return `
    <section id="github-view">
      <p ${
        markers ? 'id="sync_repos_help_text"' : ""
      }><small>${lastSync}</small></p>
      <button id="sync_repos" data-loading-text="Syncing">
        <i id="loader_icon" class="sync alternate icon"></i>
        <span id="sync_repos_btn_text">Sync now</span>
      </button>
      <div id="sync-result-message" class="ui message hidden">
        <i class="icon"></i><p role="alert" class="content"></p>
      </div>
    </section>
    ${markers ? `<div id="github-repositories">${lists}</div>` : lists}`;
}

function statusResponse(status) {
  return { ok: status < 400, status, text: () => Promise.resolve("") };
}

function htmlResponse(body, status = 200) {
  return { ok: status < 400, status, text: () => Promise.resolve(body) };
}

// The module wires its handlers on import, so every test loads a fresh copy.
// Returns the jQuery instance the module uses, with Semantic UI's modal stubbed.
function loadModule() {
  let jquery;
  jest.isolateModules(() => {
    jquery = require("jquery");
    jquery.fn.modal = jest.fn().mockReturnThis();
    require("./index");
  });
  return jquery;
}

// Lets the awaited fetch/text promises inside the handlers settle.
function flushPromises() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

const REPOS = [
  { id: 1, name: "auser/arepo", enabled: false },
  { id: 2, name: "auser/repo-1", enabled: true },
];

// Every test loads the module again; drop the delegated listeners the previous
// copy left on the shared document.
let documentListeners = [];
const addDocumentListener = document.addEventListener.bind(document);

beforeEach(() => {
  global.fetch = jest.fn();
  jest.spyOn(console, "warn").mockImplementation(() => {});
  jest.spyOn(document, "addEventListener").mockImplementation((...listener) => {
    documentListeners.push(listener);
    addDocumentListener(...listener);
  });
});

afterEach(() => {
  documentListeners.forEach((listener) =>
    document.removeEventListener(...listener)
  );
  documentListeners = [];
  jest.restoreAllMocks();
});

function syncMessage() {
  return document.querySelector("#sync-result-message .content").textContent;
}

function listsHtml() {
  return document.getElementById("github-repositories").innerHTML;
}

async function clickSync() {
  document.getElementById("sync_repos").click();
  await flushPromises();
}

describe("sync", () => {
  it("refreshes the lists and the last sync time in place", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    const synced = [
      ...REPOS,
      { id: 3, name: "auser/new-repo", enabled: false },
    ];
    global.fetch
      .mockResolvedValueOnce(statusResponse(200))
      .mockResolvedValueOnce(
        htmlResponse(
          settingsPage({ repositories: synced, lastSync: "(updated just now)" })
        )
      );
    loadModule();

    await clickSync();

    expect(global.fetch).toHaveBeenLastCalledWith(
      window.location.href,
      expect.objectContaining({ cache: "no-store" })
    );
    expect(listsHtml()).toContain("auser/new-repo");
    expect(document.getElementById("sync_repos_help_text").textContent).toBe(
      "(updated just now)"
    );
    expect(syncMessage()).toBe("Repositories synced successfully.");
  });

  it("asks for a reload when the page has no refresh markers", async () => {
    document.body.innerHTML = settingsPage({
      repositories: REPOS,
      markers: false,
    });
    global.fetch.mockResolvedValueOnce(statusResponse(200));
    loadModule();

    await clickSync();

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(syncMessage()).toMatch(/please reload the page/);
  });

  it("asks for a reload when the fetched page has no repository lists", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    const before = listsHtml();
    global.fetch
      .mockResolvedValueOnce(statusResponse(200))
      .mockResolvedValueOnce(htmlResponse("<html><body>Log in</body></html>"));
    loadModule();

    await clickSync();

    expect(listsHtml()).toBe(before);
    expect(syncMessage()).toMatch(/please reload the page/);
  });

  it.each([
    [
      "an error status",
      () =>
        Promise.resolve(htmlResponse(settingsPage({ repositories: [] }), 500)),
    ],
    ["a network error", () => Promise.reject(new TypeError("Failed to fetch"))],
  ])(
    "asks for a reload when the page refresh fails with %s",
    async (_, refresh) => {
      document.body.innerHTML = settingsPage({ repositories: REPOS });
      const before = listsHtml();
      global.fetch
        .mockResolvedValueOnce(statusResponse(200))
        .mockImplementationOnce(refresh);
      loadModule();

      await clickSync();

      expect(listsHtml()).toBe(before);
      expect(syncMessage()).toMatch(/please reload the page/);
    }
  );

  it("leaves the lists untouched when the sync fails", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    const before = listsHtml();
    global.fetch.mockResolvedValueOnce(statusResponse(500));
    loadModule();

    await clickSync();

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(listsHtml()).toBe(before);
    expect(syncMessage()).toBe("Request failed with status code: 500");
  });

  it("keeps DOI badge modals working after a refresh", async () => {
    const withBadge = [
      { id: 2, name: "auser/repo-1", enabled: true, doi: true },
    ];
    const synced = [
      ...withBadge,
      { id: 3, name: "auser/new-repo", enabled: false },
    ];
    document.body.innerHTML = settingsPage({ repositories: withBadge });
    global.fetch
      .mockResolvedValueOnce(statusResponse(200))
      .mockResolvedValueOnce(
        htmlResponse(settingsPage({ repositories: synced }))
      );
    const $ = loadModule();
    // Semantic UI moves initialised modals out of the lists, into the page dimmer.
    document.body.appendChild(document.getElementById("modal-2"));

    $.fn.modal.mockClear();
    await clickSync();

    expect(listsHtml()).toContain("auser/new-repo");
    expect(document.querySelectorAll("#modal-2")).toHaveLength(1);
    const init = $.fn.modal.mock.calls.findIndex(
      ([options]) => typeof options === "object"
    );
    const [options] = $.fn.modal.mock.calls[init];
    const initialised = $.fn.modal.mock.contexts[init];
    expect(options.selector).toEqual({ close: ".close.button" });
    expect(initialised[0]).toBe(document.getElementById("modal-2"));
    options.onShow.call(initialised[0]);
    expect(
      document.getElementById("modal-2-trigger").getAttribute("aria-expanded")
    ).toBe("true");

    const trigger = document.getElementById("modal-2-trigger");
    $.fn.modal.mockClear();
    trigger.click();
    expect($.fn.modal).toHaveBeenCalledWith("show");
    $.fn.modal.mockClear();
    trigger.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true })
    );
    expect($.fn.modal).toHaveBeenCalledWith("show");
  });

  it("shows the repositories after the first sync", async () => {
    document.body.innerHTML = settingsPage({ repositories: [] });
    global.fetch
      .mockResolvedValueOnce(statusResponse(200))
      .mockResolvedValueOnce(
        htmlResponse(settingsPage({ repositories: REPOS }))
      );
    loadModule();

    await clickSync();

    expect(listOf(1)).toBe("Repositories");
    expect(listOf(2)).toBe("Enabled Repositories");
  });

  it("keeps keyboard focus on the same link across the refresh", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    global.fetch
      .mockResolvedValueOnce(statusResponse(200))
      .mockResolvedValueOnce(
        htmlResponse(settingsPage({ repositories: REPOS }))
      );
    loadModule();
    const link = '[href="/account/settings/github/repository/auser/repo-1"]';
    document.querySelector(link).focus();

    await clickSync();

    expect(document.activeElement).toBe(document.querySelector(link));
  });

  it("sends the CSRF token", async () => {
    document.cookie = "csrftoken=token-123";
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    global.fetch.mockResolvedValueOnce(statusResponse(500));
    loadModule();

    await clickSync();

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/user/github/repositories/sync",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-CSRFToken": "token-123" }),
      })
    );
  });

  it("blocks the switches while syncing and restores the button after", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    let respond;
    global.fetch.mockReturnValueOnce(
      new Promise((resolve) => {
        respond = resolve;
      })
    );
    loadModule();

    await clickSync();
    expect(document.getElementById("sync_repos").disabled).toBe(true);
    expect(document.getElementById("sync_repos_btn_text").textContent).toBe(
      "Syncing"
    );
    expect(toggleOf(1).disabled).toBe(true);

    respond(statusResponse(500));
    await flushPromises();
    expect(document.getElementById("sync_repos").disabled).toBe(false);
    expect(document.getElementById("sync_repos_btn_text").textContent).toBe(
      "Sync now"
    );
    expect(
      document.getElementById("loader_icon").classList.contains("loading")
    ).toBe(false);
    expect(toggleOf(1).disabled).toBe(false);
  });

  it("reports a sync that cannot be sent", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    global.fetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    loadModule();

    await clickSync();

    expect(syncMessage()).toBe(
      "There has been a problem: TypeError: Failed to fetch"
    );
  });

  it("warns when the sync takes too long", async () => {
    jest.useFakeTimers();
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    global.fetch.mockReturnValueOnce(new Promise(() => {}));
    loadModule();

    document.getElementById("sync_repos").click();
    await jest.advanceTimersByTimeAsync(100000);
    jest.useRealTimers();

    expect(syncMessage()).toMatch(/This action seems to take some time/);
    expect(document.getElementById("sync_repos").disabled).toBe(false);
  });

  it("reports a successful sync even if the re-render breaks", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    global.fetch
      .mockResolvedValueOnce(statusResponse(200))
      .mockResolvedValueOnce(
        htmlResponse(settingsPage({ repositories: REPOS }))
      );
    const $ = loadModule();
    $.fn.modal.mockImplementation(() => {
      throw new Error("modal failed");
    });

    await clickSync();

    expect(syncMessage()).toMatch(
      /^Repositories synced successfully\. .*please reload the page/
    );
    expect(console.warn).toHaveBeenCalled();
  });
});

function toggleOf(repoId) {
  return document.querySelector(`input[data-repo-id="${repoId}"]`);
}

function listOf(repoId) {
  return toggleOf(repoId).closest("section").getAttribute("aria-label");
}

function messageOf(repoId) {
  return toggleOf(repoId)
    .closest(".repository-item")
    .querySelector(".repo-switch-message .content").textContent;
}

async function flip(repoId) {
  const toggle = toggleOf(repoId);
  toggle.checked = !toggle.checked;
  toggle.dispatchEvent(new Event("change", { bubbles: true }));
  await flushPromises();
}

function withState(repoId, enabled) {
  return REPOS.map((repo) =>
    repo.id === repoId ? { ...repo, enabled } : repo
  );
}

describe("enable/disable", () => {
  it("moves an enabled repository to the enabled list", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    global.fetch
      .mockResolvedValueOnce(statusResponse(201))
      .mockResolvedValueOnce(
        htmlResponse(settingsPage({ repositories: withState(1, true) }))
      );
    loadModule();

    await flip(1);

    expect(global.fetch).toHaveBeenNthCalledWith(
      1,
      "/api/user/github/repositories/1/enable",
      expect.objectContaining({ method: "POST" })
    );
    expect(listOf(1)).toBe("Enabled Repositories");
    expect(toggleOf(1).checked).toBe(true);
    expect(document.activeElement).toBe(toggleOf(1));
    expect(messageOf(1)).toBe("Repository enabled.");
  });

  it("moves a disabled repository back to the repositories list", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    global.fetch
      .mockResolvedValueOnce(statusResponse(204))
      .mockResolvedValueOnce(
        htmlResponse(settingsPage({ repositories: withState(2, false) }))
      );
    loadModule();

    await flip(2);

    expect(global.fetch).toHaveBeenNthCalledWith(
      1,
      "/api/user/github/repositories/2/disable",
      expect.objectContaining({ method: "POST" })
    );
    expect(listOf(2)).toBe("Repositories");
    expect(document.activeElement).toBe(toggleOf(2));
    expect(messageOf(2)).toBe("Repository disabled.");
  });

  it("reverts the switch when the request is refused", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    global.fetch.mockResolvedValueOnce(statusResponse(400));
    loadModule();

    await flip(1);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(listOf(1)).toBe("Repositories");
    expect(toggleOf(1).checked).toBe(false);
    expect(toggleOf(1).getAttribute("aria-label")).toBe("Enable auser/arepo");
    expect(messageOf(1)).toBe("Request failed with status code: 400");
  });

  it("reverts the switch when the request cannot be sent", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    global.fetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    loadModule();

    await flip(2);

    expect(toggleOf(2).checked).toBe(true);
    expect(toggleOf(2).getAttribute("aria-label")).toBe("Disable auser/repo-1");
    expect(messageOf(2)).toBe(
      "There has been a problem: TypeError: Failed to fetch"
    );
  });

  it("blocks every switch and Sync while a request is in flight", async () => {
    const locked = { id: 9, name: "org/shared", enabled: true, locked: true };
    document.body.innerHTML = settingsPage({
      repositories: [...REPOS, locked],
    });
    let respond;
    global.fetch.mockReturnValueOnce(
      new Promise((resolve) => {
        respond = resolve;
      })
    );
    loadModule();

    await flip(1);
    expect(toggleOf(1).disabled).toBe(true);
    expect(toggleOf(2).disabled).toBe(true);
    expect(document.getElementById("sync_repos").disabled).toBe(true);

    respond(statusResponse(400));
    await flushPromises();
    expect(toggleOf(1).disabled).toBe(false);
    expect(toggleOf(2).disabled).toBe(false);
    expect(document.getElementById("sync_repos").disabled).toBe(false);
    expect(toggleOf(9).disabled).toBe(true);
  });

  it("sends the CSRF token", async () => {
    document.cookie = "csrftoken=token-123";
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    global.fetch.mockResolvedValueOnce(statusResponse(400));
    loadModule();

    await flip(1);

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/user/github/repositories/1/enable",
      expect.objectContaining({
        headers: expect.objectContaining({ "X-CSRFToken": "token-123" }),
      })
    );
  });

  it("keeps the switch flipped when only the re-render breaks", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    global.fetch
      .mockResolvedValueOnce(statusResponse(201))
      .mockResolvedValueOnce(
        htmlResponse(settingsPage({ repositories: withState(1, true) }))
      );
    const $ = loadModule();
    $.fn.modal.mockImplementation(() => {
      throw new Error("modal failed");
    });

    await flip(1);

    expect(toggleOf(1).checked).toBe(true);
    expect(messageOf(1)).toBe(
      "Repository synced successfully. Please reload the page."
    );
  });

  it("does not take focus back from a control the user moved to", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    let respond;
    global.fetch
      .mockReturnValueOnce(
        new Promise((resolve) => {
          respond = resolve;
        })
      )
      .mockResolvedValueOnce(
        htmlResponse(settingsPage({ repositories: withState(1, true) }))
      );
    loadModule();
    const link = '[href="/account/settings/github/repository/auser/repo-1"]';

    await flip(1);
    document.querySelector(link).focus();
    respond(statusResponse(201));
    await flushPromises();

    expect(listOf(1)).toBe("Enabled Repositories");
    expect(document.activeElement).toBe(document.querySelector(link));
  });

  it("reports the result when the repository is gone after the refresh", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    global.fetch
      .mockResolvedValueOnce(statusResponse(201))
      .mockResolvedValueOnce(
        htmlResponse(settingsPage({ repositories: [REPOS[1]] }))
      );
    loadModule();

    await flip(1);

    expect(toggleOf(1)).toBeNull();
    expect(syncMessage()).toBe("Repository enabled.");
  });

  it("asks for a reload when the page has no refresh markers", async () => {
    document.body.innerHTML = settingsPage({
      repositories: REPOS,
      markers: false,
    });
    global.fetch.mockResolvedValueOnce(statusResponse(201));
    loadModule();

    await flip(1);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(toggleOf(1).checked).toBe(true);
    expect(messageOf(1)).toBe(
      "Repository synced successfully. Please reload the page."
    );
  });

  it("keeps switches working after the lists are re-rendered", async () => {
    document.body.innerHTML = settingsPage({ repositories: REPOS });
    global.fetch
      .mockResolvedValueOnce(statusResponse(201))
      .mockResolvedValueOnce(
        htmlResponse(settingsPage({ repositories: withState(1, true) }))
      )
      .mockResolvedValueOnce(statusResponse(204))
      .mockResolvedValueOnce(
        htmlResponse(settingsPage({ repositories: REPOS }))
      );
    loadModule();

    await flip(1);
    await flip(1);

    expect(global.fetch).toHaveBeenNthCalledWith(
      3,
      "/api/user/github/repositories/1/disable",
      expect.objectContaining({ method: "POST" })
    );
    expect(listOf(1)).toBe("Repositories");
  });
});
