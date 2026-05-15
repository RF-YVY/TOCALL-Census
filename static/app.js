const state = {
  packetCount: 0,
  markers: new Map(),
  seenLocatedRaw: new Set(),
  locationCounts: {
    states: new Map(),
    countries: new Map(),
  },
  health: null,
  healthRenderedAt: null,
};

const statusPill = document.querySelector("#statusPill");
const packetCount = document.querySelector("#packetCount");
const uniqueSources = document.querySelector("#uniqueSources");
const registryCount = document.querySelector("#registryCount");
const rfCount = document.querySelector("#rfCount");
const mapCount = document.querySelector("#mapCount");
const topTocalls = document.querySelector("#topTocalls");
const stateList = document.querySelector("#stateList");
const countryList = document.querySelector("#countryList");
const packetList = document.querySelector("#packetList");
const targetLabel = document.querySelector("#targetLabel");
const connectForm = document.querySelector("#connectForm");
const connectButton = document.querySelector("#connectButton");
const aprsFilterInput = document.querySelector("#aprsFilter");
const targetTocallInput = document.querySelector("#targetTocall");
const serverInput = document.querySelector("#server");
const portInput = document.querySelector("#port");
const callsignInput = document.querySelector("#callsign");
const passcodeInput = document.querySelector("#passcode");
const disconnectButton = document.querySelector("#disconnectButton");
const clearButton = document.querySelector("#clearButton");
const refreshRegistryButton = document.querySelector("#refreshRegistryButton");
const saveSettingsButton = document.querySelector("#saveSettingsButton");
const autoConnectInput = document.querySelector("#autoConnect");
const retentionDaysInput = document.querySelector("#retentionDays");
const maxPacketsInput = document.querySelector("#maxPackets");
const registrySearchForm = document.querySelector("#registrySearchForm");
const registrySearchInput = document.querySelector("#registrySearchInput");
const registrySearchResults = document.querySelector("#registrySearchResults");
const registryWebLink = document.querySelector("#registryWebLink");
const registryYamlLink = document.querySelector("#registryYamlLink");
const themeToggle = document.querySelector("#themeToggle");
const mapThemeToggle = document.querySelector("#mapThemeToggle");
const guideButton = document.querySelector("#guideButton");
const guideDialog = document.querySelector("#guideDialog");
const closeGuideButton = document.querySelector("#closeGuideButton");
const currentVersion = document.querySelector("#currentVersion");
const versionMetric = document.querySelector("#versionMetric");
const versionStatus = document.querySelector("#versionStatus");
const aprsUptime = document.querySelector("#aprsUptime");
const lastPacketAt = document.querySelector("#lastPacketAt");
const reconnectCount = document.querySelector("#reconnectCount");
const lastReconnectReason = document.querySelector("#lastReconnectReason");
const browserStatus = document.querySelector("#browserStatus");
const webClientCount = document.querySelector("#webClientCount");

const map = L.map("map", { preferCanvas: true }).setView([39.5, -98.35], 4);
const lightTiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: "&copy; OpenStreetMap contributors",
});
const darkTiles = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  maxZoom: 18,
  attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
});
lightTiles.addTo(map);
let mapTheme = localStorage.getItem("tocall-census-map-theme") || "light";

connectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = collectConnectSettings();
  saveConnectSettings(data);
  await postJson("/api/connect", data);
});

connectForm.addEventListener("input", (event) => {
  if (event.target === passcodeInput) {
    passcodeInput.dataset.masked = "false";
  }
  saveConnectSettings(collectConnectSettings());
});

disconnectButton.addEventListener("click", async () => {
  await postJson("/api/disconnect", {});
});

saveSettingsButton.addEventListener("click", async () => {
  const data = collectConnectSettings();
  saveConnectSettings(data);
  const result = await postJson("/api/settings", data);
  applySnapshot(result);
});

clearButton.addEventListener("click", async () => {
  const confirmed = window.confirm("Clear all collected TOCALL counts, packets, and map points?");
  if (!confirmed) {
    return;
  }
  const data = await postJson("/api/clear", {});
  resetCollectedUi();
  applySnapshot(data);
});

refreshRegistryButton.addEventListener("click", async () => {
  const result = await postJson("/api/registry/refresh", {});
  registryCount.textContent = result.count ?? "0";
});

registrySearchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await searchRegistry();
});

themeToggle.addEventListener("click", () => {
  const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  setTheme(nextTheme);
});

mapThemeToggle.addEventListener("click", () => {
  setMapTheme(mapTheme === "dark" ? "light" : "dark");
});

guideButton.addEventListener("click", () => {
  guideDialog.showModal();
});

closeGuideButton.addEventListener("click", () => {
  guideDialog.close();
});

guideDialog.addEventListener("click", (event) => {
  if (event.target === guideDialog) {
    guideDialog.close();
  }
});

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail);
  }
  return response.json();
}

async function loadSnapshot() {
  const response = await fetch("/api/summary");
  const data = await response.json();
  applySnapshot(data);
}

async function checkVersion() {
  try {
    const response = await fetch("/api/version");
    const data = await response.json();
    currentVersion.textContent = data.current_version || "unknown";
    versionStatus.href = data.release_url || "https://github.com/RF-YVY/TOCALL-Census";
    versionMetric.onclick = null;
    versionMetric.classList.remove("update-available");
    if (data.update_available) {
      versionStatus.textContent = `Update available: ${data.latest_version}`;
      versionStatus.classList.add("update-available");
      versionMetric.classList.add("update-available");
      versionMetric.setAttribute("role", "link");
      versionMetric.setAttribute("tabindex", "0");
      versionMetric.onclick = () => {
        window.open(versionStatus.href, "_blank", "noreferrer");
      };
      versionMetric.onkeydown = (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          window.open(versionStatus.href, "_blank", "noreferrer");
        }
      };
      return;
    }
    versionStatus.classList.remove("update-available");
    versionMetric.removeAttribute("role");
    versionMetric.removeAttribute("tabindex");
    versionMetric.onkeydown = null;
    if (data.latest_version) {
      versionStatus.textContent = `Current: latest is ${data.latest_version}`;
      return;
    }
    versionStatus.textContent = data.message || "No release found";
  } catch (error) {
    versionStatus.textContent = "Version check unavailable";
  }
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("tocall-census-theme", theme);
  themeToggle.textContent = theme === "dark" ? "Light" : "Dark";
  themeToggle.setAttribute("aria-pressed", String(theme === "dark"));
  setTimeout(() => map.invalidateSize(), 120);
}

function setMapTheme(theme) {
  mapTheme = theme;
  localStorage.setItem("tocall-census-map-theme", theme);
  if (theme === "dark") {
    map.removeLayer(lightTiles);
    darkTiles.addTo(map);
  } else {
    map.removeLayer(darkTiles);
    lightTiles.addTo(map);
  }
  mapThemeToggle.textContent = theme === "dark" ? "Light Map" : "Dark Map";
  mapThemeToggle.setAttribute("aria-pressed", String(theme === "dark"));
  setTimeout(() => map.invalidateSize(), 120);
}

function connectSocket() {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${scheme}://${location.host}/ws`);

  socket.addEventListener("open", () => {
    browserStatus.textContent = "Live";
  });

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "snapshot") {
      applySnapshot(message);
    }
    if (message.type === "cleared") {
      applySnapshot(message);
    }
    if (message.type === "status") {
      renderStatus(message.status);
    }
    if (message.type === "health") {
      renderHealth(message.health);
    }
    if (message.type === "summary") {
      renderSummary(message.summary);
    }
    if (message.type === "packet") {
      prependPacket(message.packet);
      addMapPoint(message.packet);
      addLiveLocation(message.packet);
    }
    if (message.type === "registry") {
      registryCount.textContent = message.count;
    }
  });

  socket.addEventListener("close", () => {
    browserStatus.textContent = "Retrying";
    setTimeout(connectSocket, 1500);
  });
}

function collectConnectSettings() {
  const data = Object.fromEntries(new FormData(connectForm).entries());
  data.port = Number(data.port || 14580);
  if (passcodeInput.dataset.masked === "true") {
    data.passcode = "masked";
  }
  data.auto_connect = autoConnectInput.checked;
  data.retention_days = Number(data.retention_days || 0);
  data.max_packets = Number(data.max_packets || 0);
  return data;
}

function initTheme() {
  const saved = localStorage.getItem("tocall-census-theme");
  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  setTheme(saved || (prefersDark ? "dark" : "light"));
}

function restoreConnectSettings() {
  const savedFilter = localStorage.getItem("tocall-census-aprs-filter");
  if (savedFilter !== null) {
    aprsFilterInput.value = savedFilter;
  }
}

function saveConnectSettings(data) {
  localStorage.setItem("tocall-census-aprs-filter", String(data.aprs_filter || ""));
}

function applySnapshot(data) {
  applySettings(data.settings || data.status?.settings || {});
  applyRegistryLinks(data.registry_links || {});
  renderStatus(data.status);
  renderHealth(data.health || data.status?.health);
  renderSummary(data.summary);
  registryCount.textContent = data.registry_count ?? 0;
  targetLabel.textContent = data.target_tocall ? `Tracking ${data.target_tocall}` : "All traffic";
  state.markers.forEach((marker) => marker.remove());
  state.markers.clear();
  mapCount.textContent = "0 mapped";
  state.seenLocatedRaw.clear();
  resetLocationCounts();
  (data.map_points || []).forEach(addMapPoint);
  const recent = data.summary?.recent || [];
  packetList.innerHTML = "";
  recent.reverse().forEach(prependPacket);
}

function applyRegistryLinks(links) {
  if (links.web) {
    registryWebLink.href = links.web;
  }
  if (links.master) {
    registryYamlLink.href = links.master;
  }
}

function applySettings(settings) {
  if (!settings || connectForm.matches(":focus-within")) {
    return;
  }
  if (settings.filter !== undefined) {
    aprsFilterInput.value = settings.filter || "";
  }
  if (settings.target_tocall !== undefined) {
    targetTocallInput.value = settings.target_tocall || "";
  }
  if (settings.server !== undefined) {
    serverInput.value = settings.server || "";
  }
  if (settings.port !== undefined) {
    portInput.value = settings.port || "";
  }
  if (settings.callsign !== undefined) {
    callsignInput.value = settings.callsign || "";
  }
  if (settings.auto_connect !== undefined) {
    autoConnectInput.checked = Boolean(settings.auto_connect);
  }
  if (settings.retention_days !== undefined) {
    retentionDaysInput.value = settings.retention_days || 0;
  }
  if (settings.max_packets !== undefined) {
    maxPacketsInput.value = settings.max_packets || 0;
  }
  if (settings.passcode && settings.passcode !== "masked") {
    passcodeInput.value = settings.passcode;
    passcodeInput.dataset.masked = "false";
  }
  if (settings.passcode === "masked") {
    passcodeInput.dataset.masked = "true";
  }
}

function resetCollectedUi() {
  state.packetCount = 0;
  packetCount.textContent = "0";
  uniqueSources.textContent = "0";
  rfCount.textContent = "0";
  topTocalls.innerHTML = "";
  packetList.innerHTML = "";
  state.markers.forEach((marker) => marker.remove());
  state.markers.clear();
  mapCount.textContent = "0 mapped";
  state.seenLocatedRaw.clear();
  resetLocationCounts();
  renderScoreboardsFromState();
}

function renderStatus(status) {
  const stateText = status?.state || "unknown";
  const message = status?.message || "";
  statusPill.className = `status-pill status-${stateText}`;
  statusPill.textContent = `${statusLabel(stateText)}: ${message}`;
  renderConnectButton(Boolean(status?.running));
  renderHealth(status?.health);
}

function renderHealth(health) {
  if (!health) {
    return;
  }
  state.health = health;
  state.healthRenderedAt = Date.now();
  renderHealthClock();
  reconnectCount.textContent = health.reconnect_count ?? 0;
  lastReconnectReason.textContent = health.last_reconnect_reason || "No reconnects";
  webClientCount.textContent = `${health.web_clients ?? 0} client${health.web_clients === 1 ? "" : "s"}`;
  lastPacketAt.textContent = health.last_packet_at ? `Last packet ${formatDateTime(health.last_packet_at)}` : "No packets yet";
}

function renderHealthClock() {
  if (!state.health) {
    return;
  }
  const elapsedSinceRender = state.healthRenderedAt ? Math.floor((Date.now() - state.healthRenderedAt) / 1000) : 0;
  const connectedSeconds = Number(state.health.aprs_connected_seconds || 0);
  aprsUptime.textContent = formatDuration(connectedSeconds ? connectedSeconds + elapsedSinceRender : 0);
}

function statusLabel(stateText) {
  const labels = {
    stopped: "Disconnected",
    cleared: "Cleared",
    connecting: "Connecting",
    running: "Connected",
    reconnecting: "Reconnecting",
    server: "Server",
    warning: "Warning",
    error: "Connection Error",
    rejected: "Login Rejected",
    reconnecting: "Reconnecting",
  };
  return labels[stateText] || stateText;
}

function renderConnectButton(isConnected) {
  connectButton.textContent = isConnected ? "Connected" : "Connect";
  connectButton.classList.toggle("connected", isConnected);
  connectButton.setAttribute("aria-pressed", String(isConnected));
}

function renderSummary(summary) {
  const rows = summary?.top_tocalls || [];
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  const transport = summary?.transport || {};
  state.packetCount = total;
  packetCount.textContent = total;
  uniqueSources.textContent = summary?.unique_sources ?? 0;
  rfCount.textContent = transport.rf_igate ?? 0;

  topTocalls.innerHTML = rows
    .map(
      (row) => `<tr>
        <td><span class="tag">${escapeHtml(row.tocall)}</span></td>
        <td>${escapeHtml(row.label)}</td>
        <td>${row.count}</td>
        <td>${formatTime(row.last_heard)}</td>
      </tr>`,
    )
    .join("");

  renderLocationSummary(summary?.locations || { states: [], countries: [] });
}

function renderLocationSummary(locations) {
  resetLocationCounts();
  (locations.states || []).forEach((row) => {
    state.locationCounts.states.set(row.name, Number(row.count) || 0);
  });
  (locations.countries || []).forEach((row) => {
    state.locationCounts.countries.set(row.name, Number(row.count) || 0);
  });
  renderScoreboardsFromState();
}

function resetLocationCounts() {
  state.locationCounts.states.clear();
  state.locationCounts.countries.clear();
}

function renderScoreboardsFromState() {
  renderScoreboard(stateList, mapToRows(state.locationCounts.states), "No US states identified");
  renderScoreboard(countryList, mapToRows(state.locationCounts.countries), "No countries identified");
}

function mapToRows(map) {
  return [...map.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

function renderScoreboard(container, rows, emptyText) {
  if (!rows.length || rows.every((row) => !row.count)) {
    container.innerHTML = `<div class="muted">${escapeHtml(emptyText)}</div>`;
    return;
  }
  container.innerHTML = rows
    .map(
      (row) => `<div class="score-row">
        <strong>${escapeHtml(row.name)}</strong>
        <span class="score-count">${row.count}</span>
      </div>`,
    )
    .join("");
}

async function searchRegistry() {
  const query = registrySearchInput.value.trim();
  if (!query) {
    registrySearchResults.innerHTML = '<div class="muted">Enter a TOCALL, wildcard, vendor, or software name.</div>';
    return;
  }
  const response = await fetch(`/api/registry/search?q=${encodeURIComponent(query)}`);
  if (!response.ok) {
    registrySearchResults.innerHTML = '<div class="muted">Registry search unavailable.</div>';
    return;
  }
  const data = await response.json();
  renderRegistryResults(data.results || [], query);
}

function renderRegistryResults(rows, query) {
  if (!rows.length) {
    registrySearchResults.innerHTML = `<div class="muted">No local registry matches for ${escapeHtml(query)}.</div>`;
    return;
  }
  registrySearchResults.innerHTML = rows
    .map(
      (row) => `<div class="registry-result">
        <span class="registry-tocall">${escapeHtml(row.tocall)}</span>
        <strong>${escapeHtml(row.label)}</strong>
        <span class="muted">${escapeHtml(row.match)}</span>
      </div>`,
    )
    .join("");
}

function addLiveLocation(packet) {
  if (typeof packet.lat !== "number" || typeof packet.lon !== "number" || !packet.raw) {
    return;
  }
  if (state.seenLocatedRaw.has(packet.raw)) {
    return;
  }
  state.seenLocatedRaw.add(packet.raw);
  if (packet.us_state) {
    incrementLocationCount(state.locationCounts.states, packet.us_state);
  }
  if (packet.country) {
    incrementLocationCount(state.locationCounts.countries, packet.country);
  }
  renderScoreboardsFromState();
}

function incrementLocationCount(map, name) {
  map.set(name, (map.get(name) || 0) + 1);
}

function prependPacket(packet) {
  const node = document.createElement("tr");
  node.className = "packet";
  node.innerHTML = `
    <td>${formatDateTime(packet.heard_at)}</td>
    <td><strong>${escapeHtml(packet.source)}</strong></td>
    <td><span class="tag">${escapeHtml(packet.tocall)}</span></td>
    <td>${escapeHtml(packet.label)}</td>
    <td>${escapeHtml(packet.transport)}<div class="muted">${escapeHtml(packet.path || "")}</div></td>
    <td><code>${escapeHtml(packet.raw || "")}</code></td>
  `;
  packetList.prepend(node);
  while (packetList.children.length > 80) {
    packetList.lastElementChild.remove();
  }
}

function addMapPoint(packet) {
  if (typeof packet.lat !== "number" || typeof packet.lon !== "number") {
    return;
  }
  const key = `${packet.source}:${packet.tocall}`;
  if (state.markers.has(key)) {
    state.markers.get(key).remove();
  }
  const marker = L.circleMarker([packet.lat, packet.lon], {
    radius: 7,
    color: packet.transport === "rf_igate" ? "#0f766e" : "#475569",
    fillColor: packet.transport === "rf_igate" ? "#14b8a6" : "#94a3b8",
    fillOpacity: 0.8,
    weight: 2,
  })
    .bindPopup(
      `<strong>${escapeHtml(packet.source)}</strong><br>${escapeHtml(packet.tocall)} ${escapeHtml(packet.label)}<br>${formatTime(packet.heard_at)}`,
    )
    .addTo(map);
  state.markers.set(key, marker);
  mapCount.textContent = `${state.markers.size} mapped`;
}

function formatTime(value) {
  if (!value) {
    return "";
  }
  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDateTime(value) {
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDuration(totalSeconds) {
  const seconds = Math.max(0, Number(totalSeconds) || 0);
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days) {
    return `${days}d ${hours}h`;
  }
  if (hours) {
    return `${hours}h ${minutes}m`;
  }
  if (minutes) {
    return `${minutes}m`;
  }
  return `${seconds}s`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

initTheme();
setMapTheme(mapTheme);
restoreConnectSettings();
loadSnapshot();
checkVersion();
connectSocket();
setInterval(renderHealthClock, 1000);
