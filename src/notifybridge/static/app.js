const root = document.documentElement;
const keyContainer = document.getElementById("keys");
const notificationContainer = document.getElementById("notifications");
const auditContainer = document.getElementById("audit");

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

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  return response.json();
}

async function refresh() {
  const keys = await fetchJson("/api/keys");
  const notifications = await fetchJson("/api/notifications");
  const audit = await fetchJson("/api/audit");

  keyContainer.innerHTML = keys.keys.map((item) => `
    <div class="list-item">
      <strong>${item.api_key}</strong>
      <div class="meta">${item.total_count} total, ${item.new_count} new, ${item.read_count} read</div>
    </div>
  `).join("");

  if (keys.unassigned.enabled) {
    keyContainer.innerHTML += `
      <div class="list-item">
        <strong>Unassigned syslog</strong>
        <div class="meta">${keys.unassigned.summary.total_count} total, ${keys.unassigned.summary.new_count} new</div>
      </div>
    `;
  }

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
  const form = new FormData(event.target);
  const apiKey = String(form.get("api_key") || "").trim();
  if (!apiKey) return;
  await fetchJson("/api/keys", {
    method: "POST",
    body: JSON.stringify({ api_key: apiKey }),
  });
  event.target.reset();
  await refresh();
});

const events = new EventSource("/api/events");
events.onmessage = () => refresh();

refresh();
