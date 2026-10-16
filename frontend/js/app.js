/**
 * Main Application Orchestrator for TablePulse Restaurant Analytics
 */
window.appState = {
  activeTab: "floor",
  telemetry: {},
  alerts: [],
  unreadAlertCount: 0,
};

document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  initWebSocket();
  initSubsystems();
  loadInitialData();

  // Periodically refresh alerts & table summary
  setInterval(loadAlerts, 10000);
});

function initNavigation() {
  const links = document.querySelectorAll(".nav-link[data-tab]");
  links.forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const tabId = link.getAttribute("data-tab");
      switchTab(tabId);
    });
  });

  // Handle URL hash navigation
  if (window.location.hash) {
    const hash = window.location.hash.substring(1);
    switchTab(hash);
  }
}

function switchTab(tabId) {
  const targetPane = document.getElementById(`tab-${tabId}`);
  if (!targetPane) return;

  document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));

  targetPane.classList.add("active");
  const activeLink = document.querySelector(`.nav-link[data-tab="${tabId}"]`);
  if (activeLink) activeLink.classList.add("active");

  window.appState.activeTab = tabId;
  window.location.hash = tabId;

  // Trigger resize if switching to calibration
  if (tabId === "calibration") {
    setTimeout(() => window.calibrationStudio?.resizeCanvas(), 50);
  } else if (tabId === "analytics") {
    loadAnalytics();
  } else if (tabId === "waitlist") {
    window.waitlistManager?.loadWaitlist();
  } else if (tabId === "settings") {
    loadSettings();
  }
}

function initWebSocket() {
  window.telemetryWS.connect();

  window.telemetryWS.on("telemetry", (data) => {
    window.appState.telemetry = data;
    updateKPIs(data);
    updateTableCards(data.tables || {});
    if (window.analyticsChart) {
      const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      window.analyticsChart.addPoint(nowStr, data.occupied_tables, data.total_guests);
    }
  });
}

function initSubsystems() {
  window.calibrationStudio.init();
  window.waitlistManager.init();

  if (document.getElementById("occupancy-chart")) {
    window.analyticsChart = new OccupancyChart("occupancy-chart");
  }

  // Alerts modal trigger
  document.getElementById("btn-alert-drawer")?.addEventListener("click", () => switchTab("alerts"));
  document.getElementById("btn-dismiss-all-alerts")?.addEventListener("click", dismissAllAlerts);

  // Settings form
  document.getElementById("settings-form")?.addEventListener("submit", handleSettingsSubmit);
}

function updateKPIs(data) {
  document.getElementById("kpi-occupied").textContent = `${data.occupied_tables || 0}`;
  document.getElementById("kpi-occupied-sub").textContent = `of ${data.total_tables || 0} tables`;

  document.getElementById("kpi-guests").textContent = `${data.total_guests || 0}`;
  document.getElementById("kpi-guests-sub").textContent = `of ${data.total_seats || 0} capacity`;

  document.getElementById("kpi-utilization").textContent = `${data.utilization_pct || 0}%`;
  document.getElementById("kpi-fps").textContent = `${data.fps || 0} FPS`;
}

function updateTableCards(tables) {
  const container = document.getElementById("table-cards-list");
  if (!container) return;

  const entries = Object.entries(tables);
  if (entries.length === 0) {
    container.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 1rem 0;">No active tables monitored. Go to Calibration to define tables.</div>`;
    return;
  }

  container.innerHTML = entries.map(([name, t]) => {
    const isOcc = t.status === "OCCUPIED";
    return `
      <div class="table-item-card ${isOcc ? 'occupied' : 'free'}">
        <div class="table-card-header">
          <span class="table-name">${name}</span>
          <span class="table-badge ${isOcc ? 'occupied' : 'free'}">${t.status}</span>
        </div>
        <div class="table-metrics">
          <span>Seated: <strong style="color: #fff;">${t.guests} / ${t.seats}</strong></span>
          <span>Dwell: <span class="dwell-timer">${t.dwell_formatted}</span></span>
        </div>
        ${!isOcc ? `
          <button class="btn btn-secondary btn-sm" style="margin-top: 0.25rem;" onclick="quickSeatTable('${name}')">
            Seat Party Here
          </button>
        ` : ''}
      </div>
    `;
  }).join("");
}

function quickSeatTable(tableName) {
  switchTab("waitlist");
  window.waitlistManager.openAddModal();
  setTimeout(() => {
    const notesInput = document.getElementById("party-notes-input");
    if (notesInput) notesInput.value = `Seated directly at ${tableName}`;
  }, 100);
}

async function loadInitialData() {
  loadLiveTelemetry();
  loadAlerts();
  loadAnalytics();
}

async function loadLiveTelemetry() {
  try {
    const res = await fetch("/api/live/telemetry");
    if (res.ok) {
      const data = await res.json();
      window.appState.telemetry = data;
      updateKPIs(data);
      updateTableCards(data.tables || {});
    }
  } catch (err) {
    console.debug("Initial telemetry load failed:", err);
  }
}

async function loadAlerts() {
  try {
    const res = await fetch("/api/alerts");
    const alerts = await res.json();
    window.appState.alerts = alerts;

    const unread = alerts.filter(a => !a.is_dismissed);
    const counter = document.getElementById("alert-badge-count");
    if (counter) {
      counter.textContent = unread.length;
      counter.style.display = unread.length > 0 ? "block" : "none";
    }

    renderAlertsList();
  } catch (err) {
    console.error("Failed to fetch alerts:", err);
  }
}

function renderAlertsList() {
  const container = document.getElementById("alerts-full-list");
  if (!container) return;

  if (window.appState.alerts.length === 0) {
    container.innerHTML = `<div style="color: var(--text-muted); font-size: 0.9rem; padding: 2rem 0; text-align: center;">No operational alerts recorded.</div>`;
    return;
  }

  container.innerHTML = window.appState.alerts.map(a => `
    <div class="party-card ${a.severity === 'CRITICAL' ? 'overdue' : ''}" style="margin-bottom: 0.75rem; opacity: ${a.is_dismissed ? 0.6 : 1};">
      <div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <span class="table-badge ${a.severity === 'CRITICAL' || a.severity === 'WARNING' ? 'occupied' : 'free'}">${a.severity}</span>
          <span style="font-weight: 700; color: #fff;">${a.title}</span>
          <span style="font-size: 0.75rem; color: var(--text-muted);">${a.time || ''}</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.35rem;">${a.message}</div>
      </div>
      ${!a.is_dismissed ? `
        <button class="btn btn-secondary btn-sm" onclick="dismissAlert(${a.id})">Dismiss</button>
      ` : `<span style="font-size: 0.75rem; color: var(--text-muted);">Dismissed</span>`}
    </div>
  `).join("");
}

async function dismissAlert(alertId) {
  try {
    await fetch(`/api/alerts/${alertId}/dismiss`, { method: "PUT" });
    await loadAlerts();
  } catch (err) {
    console.error(err);
  }
}

async function dismissAllAlerts() {
  try {
    await fetch("/api/alerts/dismiss-all", { method: "POST" });
    await loadAlerts();
  } catch (err) {
    console.error(err);
  }
}

async function loadAnalytics() {
  try {
    const [summaryRes, visitsRes, tablesRes, historyRes] = await Promise.all([
      fetch("/api/analytics/summary"),
      fetch("/api/analytics/visits?limit=25"),
      fetch("/api/analytics/tables"),
      fetch("/api/analytics/history?minutes=60")
    ]);

    const summary = await summaryRes.json();
    const visits = await visitsRes.json();
    const tableStats = await tablesRes.json();
    const history = await historyRes.json();

    // Fill Analytics KPIs
    document.getElementById("ana-total-visits").textContent = summary.total_visits || "0";
    document.getElementById("ana-avg-duration").textContent = summary.avg_duration_formatted || "–";
    document.getElementById("ana-avg-guests").textContent = summary.avg_guests_per_table || "–";
    document.getElementById("ana-longest-visit").textContent = summary.longest_visit_formatted || "–";

    // Feed Chart
    if (window.analyticsChart) {
      window.analyticsChart.setData(history);
    }

    // Render Table Breakdown
    const tableBody = document.getElementById("analytics-tables-body");
    if (tableBody) {
      tableBody.innerHTML = tableStats.map(t => `
        <tr>
          <td><strong style="color: #fff;">${t.table_name}</strong></td>
          <td>${t.total_visits}</td>
          <td>${t.avg_duration_formatted}</td>
          <td>${t.avg_guests}</td>
          <td>${t.max_duration_formatted}</td>
        </tr>
      `).join("");
    }

    // Render Visits Table
    const visitsBody = document.getElementById("analytics-visits-body");
    if (visitsBody) {
      visitsBody.innerHTML = visits.map(v => `
        <tr>
          <td>#${v.id}</td>
          <td><strong style="color: #fff;">${v.table_name}</strong></td>
          <td>${v.started_at || '–'}</td>
          <td>${v.ended_at || '–'}</td>
          <td><span class="dwell-timer">${v.duration_formatted}</span></td>
          <td>${v.guest_count}</td>
        </tr>
      `).join("");
    }
  } catch (err) {
    console.error("Error loading analytics:", err);
  }
}

async function loadSettings() {
  try {
    const res = await fetch("/api/settings");
    const data = await res.json();

    document.getElementById("cfg-source").value = data.stream_source || "";
    document.getElementById("cfg-conf").value = data.confidence_threshold || 0.25;
    document.getElementById("cfg-pose-conf").value = data.pose_confidence_threshold || 0.3;
    document.getElementById("cfg-idle-alert").value = data.alert_idle_table_minutes || 15;
    document.getElementById("cfg-cap-alert").value = data.alert_capacity_percent || 85;

    document.getElementById("cfg-db-type").textContent = data.database_type || "SQLite";
    document.getElementById("cfg-resolution").textContent = data.stream_resolution || "1280x720";
    document.getElementById("cfg-status").textContent = data.is_stream_connected ? "Connected" : "Reconnecting";

    // Populate video dropdown
    const select = document.getElementById("cfg-quick-video");
    if (select && data.available_videos) {
      select.innerHTML = `<option value="">-- Choose local video or enter RTSP below --</option>` +
        data.available_videos.map(v => `<option value="videos/${v}">videos/${v}</option>`).join("");
    }
  } catch (err) {
    console.error("Error loading settings:", err);
  }
}

async function handleSettingsSubmit(e) {
  e.preventDefault();
  const source = document.getElementById("cfg-source").value.trim();
  const conf = parseFloat(document.getElementById("cfg-conf").value);
  const poseConf = parseFloat(document.getElementById("cfg-pose-conf").value);
  const idleAlert = parseInt(document.getElementById("cfg-idle-alert").value);
  const capAlert = parseInt(document.getElementById("cfg-cap-alert").value);

  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        stream_source: source,
        confidence_threshold: conf,
        pose_confidence_threshold: poseConf,
        alert_idle_table_minutes: idleAlert,
        alert_capacity_percent: capAlert
      })
    });

    if (res.ok) {
      alert("Settings updated successfully!");
      loadSettings();
    } else {
      alert("Failed to update settings.");
    }
  } catch (err) {
    alert("Error updating settings.");
  }
}
