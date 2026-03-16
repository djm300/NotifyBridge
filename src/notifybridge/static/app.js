const root = document.documentElement;
const keyContainer = document.getElementById("keys");
const notificationContainer = document.getElementById("notifications");
const auditContainer = document.getElementById("audit");
const auditPanel = document.getElementById("audit-panel");
const auditToggleButton = document.getElementById("audit-toggle-button");
const clearFilterButton = document.getElementById("clear-filter-button");

let currentFilter = null;

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
  return response.json();
}

function renderKey(item) {
  const classes = ["list-item"];
  if (!item.enabled) classes.push("disabled");
  if (currentFilter === item.api_key) {
    classes.push("active-filter");
  } else if (currentFilter) {
    classes.push("dimmed-filter");
  }
  return `
    <div class="${classes.join(" ")}">
      <strong>${item.api_key}</strong>
      <div class="meta">${item.total_count} total, ${item.new_count} new, ${item.read_count} read</div>
      <div class="meta">${item.enabled ? "enabled" : "disabled"}</div>
      <div class="key-actions">
        <button class="button small ghost toggle-key" data-key="${item.api_key}" data-enabled="${item.enabled}">
          ${item.enabled ? "Disable" : "Enable"}
        </button>
        <button class="button small ghost delete-key" data-key="${item.api_key}">Delete</button>
        <button class="button small ghost filter-key" data-key="${item.api_key}">Filter</button>
      </div>
    </div>
  `;
}

function bindKeyActions() {
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

  document.querySelectorAll(".filter-key").forEach((button) => {
    button.addEventListener("click", async () => {
      currentFilter = button.dataset.key;
      await refresh();
    });
  });
}

async function refresh() {
  const keys = await fetchJson("/api/keys");
  const notifications = await fetchJson(
    currentFilter ? `/api/notifications?api_key=${encodeURIComponent(currentFilter)}` : "/api/notifications",
  );
  const audit = await fetchJson("/api/audit");

  keyContainer.innerHTML = keys.keys.map(renderKey).join("");
  bindKeyActions();

  if (keys.unassigned.enabled) {
    keyContainer.innerHTML += `
      <div class="list-item">
        <strong>Unassigned syslog</strong>
        <div class="meta">${keys.unassigned.summary.total_count} total, ${keys.unassigned.summary.new_count} new</div>
      </div>
    `;
  }

  clearFilterButton.textContent = currentFilter ? `Filter: ${currentFilter}` : "Filter: All";

  notificationContainer.innerHTML = notifications.items.map((item) => `
    <div class="list-item ${item.state}">
      <strong>${item.title}</strong>
      <div class="meta">${item.source_type} · ${item.api_key || "unassigned"}</div>
      <p>${item.body}</p>
    </div>
  `).join("");

  auditContainer.innerHTML = audit.items.map((item) => `
    <div class="list-item">
      <strong>${item.summary}</strong>
      <div class="meta">${item.source_type} · ${item.auth_status}</div>
    </div>
  `).join("");
}

document.getElementById("key-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await fetchJson("/api/keys", {
    method: "POST",
    body: "{}",
  });
  await refresh();
});

document.getElementById("clear-all-button")?.addEventListener("click", async () => {
  await fetchJson("/api/notifications", { method: "DELETE" });
  await refresh();
});

document.getElementById("random-button")?.addEventListener("click", async () => {
  await fetchJson("/api/demo/random", { method: "POST" });
  await refresh();
});

clearFilterButton?.addEventListener("click", async () => {
  currentFilter = null;
  await refresh();
});

auditToggleButton?.addEventListener("click", () => {
  setAuditCollapsed(auditPanel?.dataset.collapsed !== "true");
});

const events = new EventSource("/api/events");
events.onmessage = () => refresh();

refresh();
