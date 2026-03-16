const root = document.documentElement;
const shell = document.querySelector(".shell");
const overviewContainer = document.getElementById("overview");
const keyContainer = document.getElementById("keys");
const notificationContainer = document.getElementById("notifications");
const usageTipContainer = document.getElementById("usage-tip");
const auditContainer = document.getElementById("audit");
const auditPanel = document.getElementById("audit-panel");
const auditToggleButton = document.getElementById("audit-toggle-button");
const clearFilterButton = document.getElementById("clear-filter-button");
const notificationStateButton = document.getElementById("notification-state-button");
const syslogModeButton = document.getElementById("syslog-mode-button");

let currentFilter = null;
let notificationStateFilter = "new";
let currentUsageTipKey = null;

const runtimeSettings = {
  httpPort: shell?.dataset.httpPort || "8000",
  smtpPort: shell?.dataset.smtpPort || "2525",
  syslogPort: shell?.dataset.syslogPort || "5514",
  emailDomain: shell?.dataset.emailDomain || "notifybridge.local",
};

function setAuditCollapsed(collapsed) {
  if (!auditPanel || !auditToggleButton) return;
  auditPanel.dataset.collapsed = collapsed ? "true" : "false";
  auditPanel.classList.toggle("collapsed", collapsed);
  auditToggleButton.textContent = collapsed ? "Expand Audit Log" : "Collapse Audit Log";
  localStorage.setItem("notifybridge-audit-collapsed", collapsed ? "true" : "false");
}

function setTheme(theme) {
  root.dataset.theme = theme;
  localStorage.setItem("notifybridge-theme", theme);
}

document.getElementById("theme-toggle")?.addEventListener("click", () => {
  setTheme(root.dataset.theme === "dark" ? "light" : "dark");
});

const savedTheme = localStorage.getItem("notifybridge-theme");
if (savedTheme) {
  setTheme(savedTheme);
}

const savedAuditCollapsed = localStorage.getItem("notifybridge-audit-collapsed");
setAuditCollapsed(savedAuditCollapsed !== "false");

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed with status ${response.status}`);
  }
  return payload;
}

function renderKey(item) {
  const classes = ["list-item"];
  if (!item.enabled) classes.push("disabled");
  if (currentFilter === item.api_key) {
    classes.push("active-filter");
  } else if (currentFilter) {
    classes.push("dimmed-filter");
  }
  const toggleLabel = item.enabled ? "Disable key" : "Enable key";
  return `
    <article class="${classes.join(" ")} key-card" data-key="${item.api_key}">
      <div class="item-topline">
        <div>
          <div class="item-title"><span class="status-dot ${item.enabled ? "success" : "danger"}"></span>${item.api_key}</div>
          <div class="count-summary">${item.new_count} new · ${item.read_count} read · ${item.total_count} total</div>
        </div>
        <div class="key-actions compact">
          <button
            class="button small ghost icon-button toggle-key"
            data-key="${item.api_key}"
            data-enabled="${item.enabled}"
            type="button"
            aria-label="${toggleLabel}"
            title="${toggleLabel}"
          >
            <span class="icon-power" aria-hidden="true"></span>
          </button>
          <button
            class="button small ghost icon-button usage-tip-key"
            data-key="${item.api_key}"
            type="button"
            aria-label="Show send guide"
            title="Show send guide"
          >
            <span class="icon-info" aria-hidden="true"></span>
          </button>
          <button
            class="button small ghost icon-button delete-key"
            data-key="${item.api_key}"
            type="button"
            aria-label="Delete key"
            title="Delete key"
          >
            <span class="icon-trash" aria-hidden="true"></span>
          </button>
        </div>
      </div>
    </article>
  `;
}

function renderOverview(keys, notifications, audit) {
  const unreadCount = notifications.filter((item) => item.state === "new").length;
  const readCount = notifications.filter((item) => item.state === "read").length;
  const activeKeys = keys.filter((item) => item.enabled).length;
  const failedAudit = audit.filter((item) => !String(item.auth_status).startsWith("accepted")).length;

  overviewContainer.innerHTML = `
    <div class="overview-card">
      <span class="overview-label">Configured keys</span>
      <span class="overview-value">${keys.length}</span>
      <div class="overview-hint">${activeKeys} active for intake</div>
    </div>
    <div class="overview-card">
      <span class="overview-label">Unread inbox</span>
      <span class="overview-value">${unreadCount}</span>
      <div class="overview-hint">${notificationStateFilter === "new" ? "Current default view" : "Unread messages available"}</div>
    </div>
    <div class="overview-card">
      <span class="overview-label">Read archive</span>
      <span class="overview-value">${readCount}</span>
      <div class="overview-hint">${currentFilter ? `Filtered to ${currentFilter}` : "Across all keys"}</div>
    </div>
    <div class="overview-card">
      <span class="overview-label">Failed attempts</span>
      <span class="overview-value">${failedAudit}</span>
      <div class="overview-hint">Highlighted in the audit log</div>
    </div>
  `;
}

function buildUsageTip(apiKey) {
  const host = window.location.hostname || "127.0.0.1";
  const emailAddress = `${apiKey}@${runtimeSettings.emailDomain}`;
  const webhookCommand = `curl -X POST http://${host}:${runtimeSettings.httpPort}/ingest/webhook/${apiKey} -H "Content-Type: application/json" -d '{"title":"Webhook demo","body":"Triggered from curl"}'`;
  const emailCommand = `printf 'Triggered from mail\\n' | mail -s 'NotifyBridge demo' -S smtp=${host}:${runtimeSettings.smtpPort} ${emailAddress}`;
  const syslogCommand = `logger -n ${host} -P ${runtimeSettings.syslogPort} "[nb:${apiKey}] Triggered from logger"`;

  return `
    <section class="usage-tip-card">
      <div class="panel-heading usage-tip-header">
        <div>
          <strong>Usage tip for ${apiKey}</strong>
          <div class="meta">Local commands for webhook, SMTP, and syslog input</div>
        </div>
        <button class="button small ghost close-usage-tip">Close</button>
      </div>
      <div class="usage-tip-grid">
        <div class="usage-tip-item">
          <strong>Webhook</strong>
          <div class="meta">Send JSON with <code>curl</code></div>
          <pre><code>${webhookCommand}</code></pre>
        </div>
        <div class="usage-tip-item">
          <strong>SMTP</strong>
          <div class="meta">Send mail to the primary <code>To:</code> address</div>
          <pre><code>${emailCommand}</code></pre>
        </div>
        <div class="usage-tip-item">
          <strong>Syslog</strong>
          <div class="meta">Send one line with <code>logger</code></div>
          <pre><code>${syslogCommand}</code></pre>
        </div>
      </div>
    </section>
  `;
}

function auditClasses(item) {
  const classes = ["list-item"];
  if (!String(item.auth_status).startsWith("accepted")) {
    classes.push("audit-failed");
  }
  return classes.join(" ");
}

function bindKeyActions() {
  document.querySelectorAll(".key-card").forEach((card) => {
    card.addEventListener("click", async (event) => {
      if (event.target.closest("button")) {
        return;
      }
      currentFilter = card.dataset.key;
      currentUsageTipKey = null;
      await refresh();
    });
  });

  document.querySelectorAll(".toggle-key").forEach((button) => {
    button.addEventListener("click", async () => {
      const apiKey = button.dataset.key;
      const enabled = button.dataset.enabled !== "true";
      await fetchJson(`/api/keys/${apiKey}/enabled`, {
        method: "POST",
        body: JSON.stringify({ enabled }),
      });
      await refresh();
    });
  });

  document.querySelectorAll(".delete-key").forEach((button) => {
    button.addEventListener("click", async () => {
      const apiKey = button.dataset.key;
      await fetchJson(`/api/keys/${apiKey}`, { method: "DELETE" });
      if (currentFilter === apiKey) {
        currentFilter = null;
      }
      await refresh();
    });
  });

  document.querySelectorAll(".usage-tip-key").forEach((button) => {
    button.addEventListener("click", async () => {
      currentUsageTipKey = button.dataset.key;
      await refresh();
    });
  });
}

function bindNotificationActions() {
  document.querySelectorAll(".mark-read").forEach((button) => {
    button.addEventListener("click", async () => {
      await fetchJson(`/api/notifications/${button.dataset.id}/read`, { method: "POST" });
      await refresh();
    });
  });
}

function bindUsageTipActions() {
  document.querySelector(".close-usage-tip")?.addEventListener("click", async () => {
    currentUsageTipKey = null;
    await refresh();
  });
}

function renderEmptyState(title, body) {
  return `
    <div class="empty-state">
      <strong>${title}</strong>
      <span>${body}</span>
    </div>
  `;
}

async function refresh() {
  const keys = await fetchJson("/api/keys");
  const notificationResponse = await fetchJson(
    currentFilter ? `/api/notifications?api_key=${encodeURIComponent(currentFilter)}` : "/api/notifications",
  );
  const auditResponse = await fetchJson("/api/audit");
  const notifications = notificationStateFilter === "new"
    ? notificationResponse.items.filter((item) => item.state === "new")
    : notificationResponse.items;
  if (currentUsageTipKey && !keys.keys.some((item) => item.api_key === currentUsageTipKey)) {
    currentUsageTipKey = null;
  }
  renderOverview(keys.keys, notificationResponse.items, auditResponse.items);

  keyContainer.innerHTML = keys.keys.length
    ? keys.keys.map(renderKey).join("")
    : renderEmptyState("No API keys yet", "Generate a key to start receiving webhook, SMTP, and syslog traffic.");
  bindKeyActions();
  syslogModeButton.textContent = keys.unassigned.enabled ? "Syslog: Open" : "Syslog: Strict";

  if (keys.unassigned.enabled) {
    keyContainer.innerHTML += `
      <div class="list-item">
        <div class="item-title">Unassigned syslog</div>
        <div class="meta-row">
          <span class="pill">${keys.unassigned.summary.total_count} total</span>
          <span class="pill accent">${keys.unassigned.summary.new_count} new</span>
        </div>
      </div>
    `;
  }

  clearFilterButton.textContent = currentFilter ? `All keys` : "All keys";
  clearFilterButton.disabled = currentFilter === null;
  notificationStateButton.textContent = notificationStateFilter === "new" ? "View: Unread" : "View: All";
  usageTipContainer.innerHTML = currentUsageTipKey ? buildUsageTip(currentUsageTipKey) : "";
  bindUsageTipActions();

  notificationContainer.innerHTML = notifications.length ? notifications.map((item) => `
    <div class="list-item ${item.state}">
      <div class="item-topline">
        <div>
          <div class="item-title">${item.title}</div>
          <div class="meta-row">
            <span class="pill accent">${item.source_type}</span>
            <span class="pill">${item.api_key || "unassigned"}</span>
            ${item.source_ip ? `<span class="pill">${item.source_ip}</span>` : ""}
            <span class="pill ${item.state === "new" ? "success" : ""}">${item.state}</span>
          </div>
        </div>
      </div>
      <p class="item-body">${item.body}</p>
      <div class="notification-actions">
        ${item.state === "new" ? `<button class="button small ghost mark-read" data-id="${item.id}">Mark read</button>` : ""}
      </div>
    </div>
  `).join("") : renderEmptyState(
    notificationStateFilter === "new" ? "Inbox clear" : "No notifications",
    currentFilter ? "Try clearing the key filter or switching back to unread messages." : "Incoming accepted messages will appear here.",
  );
  bindNotificationActions();

  auditContainer.innerHTML = auditResponse.items.length ? auditResponse.items.map((item) => `
    <div class="${auditClasses(item)}">
      <div class="item-topline">
        <div>
          <div class="item-title">${item.summary}</div>
          <div class="meta-row">
            <span class="pill accent">${item.source_type}</span>
            <span class="pill ${String(item.auth_status).startsWith("accepted") ? "success" : "danger"}">${item.auth_status}</span>
          </div>
        </div>
      </div>
    </div>
  `).join("") : renderEmptyState("Audit log is empty", "Rejected and accepted ingress attempts will appear here.");
}

document.getElementById("key-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await fetchJson("/api/keys", {
      method: "POST",
      body: "{}",
    });
    await refresh();
  } catch (error) {
    console.error(error);
  }
});

document.getElementById("clear-all-button")?.addEventListener("click", async () => {
  try {
    await fetchJson("/api/notifications", { method: "DELETE" });
    await refresh();
  } catch (error) {
    console.error(error);
  }
});

document.getElementById("random-button")?.addEventListener("click", async () => {
  try {
    await fetchJson("/api/demo/random", { method: "POST" });
    await refresh();
  } catch (error) {
    console.error(error);
  }
});

clearFilterButton?.addEventListener("click", async () => {
  currentFilter = null;
  currentUsageTipKey = null;
  await refresh();
});

notificationStateButton?.addEventListener("click", async () => {
  notificationStateFilter = notificationStateFilter === "new" ? "all" : "new";
  await refresh();
});

auditToggleButton?.addEventListener("click", () => {
  setAuditCollapsed(auditPanel?.dataset.collapsed !== "true");
});

document.addEventListener("keydown", async (event) => {
  if (event.key === "Escape" && currentUsageTipKey) {
    currentUsageTipKey = null;
    await refresh();
  }
});

syslogModeButton?.addEventListener("click", async () => {
  const allowWithoutApi = syslogModeButton.textContent === "Syslog: Strict";
  const previousLabel = syslogModeButton.textContent;
  syslogModeButton.disabled = true;
  syslogModeButton.textContent = allowWithoutApi ? "Opening syslog..." : "Closing syslog...";
  try {
    await fetchJson("/api/settings/syslog-mode", {
      method: "POST",
      body: JSON.stringify({ allow_without_api: allowWithoutApi }),
    });
    await refresh();
  } catch (error) {
    console.error(error);
    syslogModeButton.textContent = previousLabel;
  } finally {
    syslogModeButton.disabled = false;
  }
});

const events = new EventSource("/api/events");
events.onmessage = () => refresh();

refresh();
