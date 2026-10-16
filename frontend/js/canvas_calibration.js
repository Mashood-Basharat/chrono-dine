/**
 * Interactive In-Browser Table & Seat Calibration Studio
 * Enables drawing table polygons directly on the live camera stream.
 */
class CalibrationStudio {
  constructor() {
    this.canvas = null;
    this.ctx = null;
    this.zones = [];
    this.currentMode = "NONE"; // 'DRAW_ZONE', 'DRAW_TOP', 'EDIT'
    this.activePoints = [];
    this.selectedZoneId = null;
    this.draggedPointIdx = -1;
    this.videoElement = null;
  }

  init() {
    this.canvas = document.getElementById("calib-canvas");
    this.videoElement = document.getElementById("calib-video");
    if (!this.canvas) return;

    this.ctx = this.canvas.getContext("2d");
    this.bindEvents();
    this.resizeCanvas();
    this.loadZones();

    window.addEventListener("resize", () => this.resizeCanvas());
  }

  resizeCanvas() {
    if (!this.canvas || !this.videoElement) return;
    const rect = this.videoElement.getBoundingClientRect();
    this.canvas.width = rect.width;
    this.canvas.height = rect.height;
    this.render();
  }

  bindEvents() {
    this.canvas.addEventListener("click", (e) => this.handleClick(e));
    this.canvas.addEventListener("dblclick", (e) => this.handleDoubleClick(e));
    this.canvas.addEventListener("mousedown", (e) => this.handleMouseDown(e));
    this.canvas.addEventListener("mousemove", (e) => this.handleMouseMove(e));
    this.canvas.addEventListener("mouseup", () => this.handleMouseUp());

    document.getElementById("btn-draw-zone")?.addEventListener("click", () => this.setMode("DRAW_ZONE"));
    document.getElementById("btn-draw-top")?.addEventListener("click", () => this.setMode("DRAW_TOP"));
    document.getElementById("btn-clear-active")?.addEventListener("click", () => this.clearActivePoints());
    document.getElementById("btn-save-zone")?.addEventListener("click", () => this.saveActiveZone());
    document.getElementById("btn-import-seed")?.addEventListener("click", () => this.importSeedZones());
  }

  setMode(mode) {
    this.currentMode = mode;
    this.activePoints = [];
    this.updateInstructionBanner();
    this.render();
  }

  updateInstructionBanner() {
    const banner = document.getElementById("calib-instruction");
    if (!banner) return;
    if (this.currentMode === "DRAW_ZONE") {
      banner.textContent = "Click around the table boundary. Double-click to close the polygon.";
    } else if (this.currentMode === "DRAW_TOP") {
      banner.textContent = "Click around the tabletop surface. Double-click to complete.";
    } else {
      banner.textContent = "Select a tool to begin calibrating dining tables.";
    }
  }

  getCanvasCoords(e) {
    const rect = this.canvas.getBoundingClientRect();
    // Video aspect ratio mapping
    const scaleX = 1280 / this.canvas.width;
    const scaleY = 720 / this.canvas.height;
    return [
      Math.round((e.clientX - rect.left) * scaleX),
      Math.round((e.clientY - rect.top) * scaleY)
    ];
  }

  handleClick(e) {
    if (this.currentMode !== "DRAW_ZONE" && this.currentMode !== "DRAW_TOP") return;
    const [x, y] = this.getCanvasCoords(e);
    this.activePoints.push([x, y]);
    this.render();
  }

  handleDoubleClick(e) {
    if (this.activePoints.length >= 3) {
      this.currentMode = "READY_TO_SAVE";
      this.updateInstructionBanner();
      const nameInput = document.getElementById("zone-name-input");
      if (nameInput && !nameInput.value) {
        nameInput.value = `Table ${this.zones.length + 1}`;
      }
      this.render();
    }
  }

  handleMouseDown(e) {
    // Vertex dragging if in edit mode
  }

  handleMouseMove(e) {
    // Dynamic cursor feedback
  }

  handleMouseUp() {
    this.draggedPointIdx = -1;
  }

  clearActivePoints() {
    this.activePoints = [];
    this.setMode("NONE");
  }

  async loadZones() {
    try {
      const res = await fetch("/api/calibration/zones");
      this.zones = await res.json();
      this.renderZonesList();
      this.render();
    } catch (err) {
      console.error("Failed to load table zones:", err);
    }
  }

  async saveActiveZone() {
    const name = document.getElementById("zone-name-input")?.value?.trim();
    const seats = parseInt(document.getElementById("zone-seats-input")?.value || "4");

    if (!name) {
      alert("Please provide a name for this table (e.g. Table 1)");
      return;
    }
    if (this.activePoints.length < 3) {
      alert("Please draw at least 3 points to create a table boundary polygon.");
      return;
    }

    try {
      const payload = {
        name: name,
        polygon: this.activePoints,
        top: [],
        seats: seats
      };

      const res = await fetch("/api/calibration/zones", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        alert(err.detail || "Failed to save zone");
        return;
      }

      this.clearActivePoints();
      await this.loadZones();
      alert(`Zone '${name}' saved successfully and activated!`);
    } catch (err) {
      console.error("Error saving zone:", err);
      alert("Failed to save zone.");
    }
  }

  async deleteZone(zoneId) {
    if (!confirm("Are you sure you want to delete this table calibration zone?")) return;
    try {
      await fetch(`/api/calibration/zones/${zoneId}`, { method: "DELETE" });
      await this.loadZones();
    } catch (err) {
      console.error("Error deleting zone:", err);
    }
  }

  async importSeedZones() {
    try {
      const res = await fetch("/api/calibration/import-seed", { method: "POST" });
      const data = await res.json();
      alert(data.message);
      await this.loadZones();
    } catch (err) {
      alert("Error importing seed zones.");
    }
  }

  renderZonesList() {
    const container = document.getElementById("calib-zones-list");
    if (!container) return;

    if (this.zones.length === 0) {
      container.innerHTML = `<div style="color: var(--text-muted); font-size: 0.85rem; padding: 1rem 0;">No tables calibrated yet. Use 'Draw Zone' above or 'Import Seed' to start.</div>`;
      return;
    }

    container.innerHTML = this.zones.map(z => `
      <div class="party-card" style="margin-bottom: 0.5rem;">
        <div>
          <div style="font-weight: 700; color: #fff;">${z.name}</div>
          <div style="font-size: 0.75rem; color: var(--text-secondary);">${z.seats} Seats · ${z.polygon?.length || 0} vertices</div>
        </div>
        <button class="btn btn-danger btn-sm" onclick="window.calibrationStudio.deleteZone(${z.id})">Delete</button>
      </div>
    `).join("");
  }

  render() {
    if (!this.ctx || !this.canvas) return;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    const scaleX = this.canvas.width / 1280;
    const scaleY = this.canvas.height / 720;

    // 1. Draw existing zones
    for (const z of this.zones) {
      if (z.polygon && z.polygon.length >= 3) {
        this.ctx.beginPath();
        this.ctx.moveTo(z.polygon[0][0] * scaleX, z.polygon[0][1] * scaleY);
        for (let i = 1; i < z.polygon.length; i++) {
          this.ctx.lineTo(z.polygon[i][0] * scaleX, z.polygon[i][1] * scaleY);
        }
        this.ctx.closePath();
        this.ctx.fillStyle = "rgba(99, 102, 241, 0.15)";
        this.ctx.fill();
        this.ctx.lineWidth = 2;
        this.ctx.strokeStyle = "rgba(99, 102, 241, 0.8)";
        this.ctx.stroke();

        // Label
        const cx = (z.polygon.reduce((acc, p) => acc + p[0], 0) / z.polygon.length) * scaleX;
        const cy = (z.polygon.reduce((acc, p) => acc + p[1], 0) / z.polygon.length) * scaleY;
        this.ctx.font = "bold 12px Plus Jakarta Sans, sans-serif";
        this.ctx.fillStyle = "#fff";
        this.ctx.fillText(`${z.name} (${z.seats}s)`, cx - 25, cy);
      }
    }

    // 2. Draw active in-progress polygon
    if (this.activePoints.length > 0) {
      this.ctx.beginPath();
      this.ctx.moveTo(this.activePoints[0][0] * scaleX, this.activePoints[0][1] * scaleY);
      for (let i = 1; i < this.activePoints.length; i++) {
        this.ctx.lineTo(this.activePoints[i][0] * scaleX, this.activePoints[i][1] * scaleY);
      }

      if (this.currentMode === "READY_TO_SAVE") {
        this.ctx.closePath();
        this.ctx.fillStyle = "rgba(16, 185, 129, 0.25)";
        this.ctx.fill();
        this.ctx.strokeStyle = "var(--accent-emerald)";
      } else {
        this.ctx.strokeStyle = "var(--accent-amber)";
      }

      this.ctx.lineWidth = 2.5;
      this.ctx.setLineDash([4, 4]);
      this.ctx.stroke();
      this.ctx.setLineDash([]);

      // Draw vertices
      for (const pt of this.activePoints) {
        this.ctx.beginPath();
        this.ctx.arc(pt[0] * scaleX, pt[1] * scaleY, 5, 0, Math.PI * 2);
        this.ctx.fillStyle = "#fff";
        this.ctx.fill();
        this.ctx.strokeStyle = "var(--accent-primary)";
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
      }
    }
  }
}

window.calibrationStudio = new CalibrationStudio();
