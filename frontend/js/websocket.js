/**
 * Real-Time WebSocket Client with Automatic Reconnect and Polling Fallback
 */
class TelemetryWebSocket {
  constructor() {
    this.socket = null;
    this.reconnectTimer = null;
    this.pollingTimer = null;
    this.listeners = new Map();
    this.isConnected = false;
  }

  connect() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/live/ws`;

    console.log(`[WebSocket] Connecting to ${wsUrl}...`);
    this.updateStatusPill("Connecting", "amber");

    // Start fallback polling immediately so UI has live data without waiting
    this.startPollingFallback();

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        console.log("[WebSocket] Connection established.");
        this.isConnected = true;
        this.stopPollingFallback();
        this.updateStatusPill("Live Stream", "emerald");
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.emit(data.type || "telemetry", data);
        } catch (e) {
          console.debug("[WebSocket] Non-JSON payload:", event.data);
        }
      };

      this.socket.onclose = () => {
        this.isConnected = false;
        console.warn("[WebSocket] Connection closed. Falling back to HTTP polling...");
        this.startPollingFallback();
        this.updateStatusPill("Live Polling", "emerald");
        this.scheduleReconnect();
      };

      this.socket.onerror = (err) => {
        console.error("[WebSocket] Error occurred:", err);
        this.socket.close();
      };
    } catch (e) {
      console.error("[WebSocket] Connection setup failed:", e);
      this.startPollingFallback();
      this.scheduleReconnect();
    }
  }

  startPollingFallback() {
    if (this.pollingTimer) return;
    this.pollTelemetry();
    this.pollingTimer = setInterval(() => this.pollTelemetry(), 1000);
  }

  stopPollingFallback() {
    if (this.pollingTimer) {
      clearInterval(this.pollingTimer);
      this.pollingTimer = null;
    }
  }

  async pollTelemetry() {
    try {
      const res = await fetch("/api/live/telemetry");
      if (res.ok) {
        const data = await res.json();
        this.emit("telemetry", data);
      }
    } catch (e) {
      console.debug("Telemetry poll error:", e);
    }
  }

  scheduleReconnect() {
    if (!this.reconnectTimer) {
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        this.connect();
      }, 3000);
    }
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  emit(event, data) {
    if (this.listeners.has(event)) {
      for (const cb of this.listeners.get(event)) {
        try {
          cb(data);
        } catch (err) {
          console.error(`[WebSocket] Error in listener for ${event}:`, err);
        }
      }
    }
  }

  updateStatusPill(text, variant) {
    const pill = document.getElementById("connection-status-pill");
    const statusText = document.getElementById("connection-status-text");
    if (!pill || !statusText) return;

    statusText.textContent = text;
    pill.className = `status-pill ${variant}`;
    const dot = pill.querySelector(".pulse-dot");
    if (dot) {
      dot.style.backgroundColor = variant === "emerald" ? "var(--accent-emerald)" : (variant === "amber" ? "var(--accent-amber)" : "var(--accent-crimson)");
      dot.style.boxShadow = `0 0 8px ${dot.style.backgroundColor}`;
    }
  }
}

window.telemetryWS = new TelemetryWebSocket();
