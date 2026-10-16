/**
 * High-Performance HTML5 Canvas Rolling Occupancy Chart
 */
class OccupancyChart {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas ? this.canvas.getContext("2d") : null;
    this.dataPoints = [];
    this.maxPoints = 60;
  }

  setData(points) {
    this.dataPoints = points || [];
    this.render();
  }

  addPoint(timeStr, occupied, guests) {
    this.dataPoints.push({ time: timeStr, occupied_tables: occupied, total_guests: guests });
    if (this.dataPoints.length > this.maxPoints) {
      this.dataPoints.shift();
    }
    this.render();
  }

  render() {
    if (!this.canvas || !this.ctx) return;
    const w = this.canvas.width = this.canvas.clientWidth;
    const h = this.canvas.height = this.canvas.clientHeight;

    this.ctx.clearRect(0, 0, w, h);

    if (this.dataPoints.length < 2) {
      this.ctx.fillStyle = "rgba(255, 255, 255, 0.2)";
      this.ctx.font = "12px Plus Jakarta Sans, sans-serif";
      this.ctx.textAlign = "center";
      this.ctx.fillText("Gathering time-series snapshots...", w / 2, h / 2);
      return;
    }

    const padLeft = 40;
    const padBottom = 25;
    const chartW = w - padLeft - 15;
    const chartH = h - padBottom - 15;

    // Determine max values
    const maxGuests = Math.max(10, ...this.dataPoints.map(p => p.total_guests || 0));
    const stepX = chartW / (this.dataPoints.length - 1);

    // Draw horizontal grid lines
    this.ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
    this.ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = 15 + (chartH / 4) * i;
      this.ctx.beginPath();
      this.ctx.moveTo(padLeft, y);
      this.ctx.lineTo(w - 15, y);
      this.ctx.stroke();

      // Y-axis label
      const val = Math.round(maxGuests - (maxGuests / 4) * i);
      this.ctx.fillStyle = "rgba(255, 255, 255, 0.3)";
      this.ctx.font = "10px JetBrains Mono, monospace";
      this.ctx.textAlign = "right";
      this.ctx.fillText(val, padLeft - 8, y + 3);
    }

    // Gradient fill for guest line
    const gradient = this.ctx.createLinearGradient(0, 15, 0, 15 + chartH);
    gradient.addColorStop(0, "rgba(99, 102, 241, 0.4)");
    gradient.addColorStop(1, "rgba(99, 102, 241, 0.0)");

    // Draw Guests Area
    this.ctx.beginPath();
    this.ctx.moveTo(padLeft, 15 + chartH);
    for (let i = 0; i < this.dataPoints.length; i++) {
      const x = padLeft + i * stepX;
      const y = 15 + chartH - ((this.dataPoints[i].total_guests || 0) / maxGuests) * chartH;
      this.ctx.lineTo(x, y);
    }
    this.ctx.lineTo(padLeft + (this.dataPoints.length - 1) * stepX, 15 + chartH);
    this.ctx.closePath();
    this.ctx.fillStyle = gradient;
    this.ctx.fill();

    // Draw Guests Stroke Line
    this.ctx.beginPath();
    for (let i = 0; i < this.dataPoints.length; i++) {
      const x = padLeft + i * stepX;
      const y = 15 + chartH - ((this.dataPoints[i].total_guests || 0) / maxGuests) * chartH;
      if (i === 0) this.ctx.moveTo(x, y);
      else this.ctx.lineTo(x, y);
    }
    this.ctx.strokeStyle = "#818cf8";
    this.ctx.lineWidth = 2.5;
    this.ctx.stroke();

    // Draw Occupied Tables Line (Emerald)
    const maxTables = 10;
    this.ctx.beginPath();
    for (let i = 0; i < this.dataPoints.length; i++) {
      const x = padLeft + i * stepX;
      const y = 15 + chartH - ((this.dataPoints[i].occupied_tables || 0) / maxTables) * chartH;
      if (i === 0) this.ctx.moveTo(x, y);
      else this.ctx.lineTo(x, y);
    }
    this.ctx.strokeStyle = "#10b981";
    this.ctx.lineWidth = 2;
    this.ctx.setLineDash([3, 3]);
    this.ctx.stroke();
    this.ctx.setLineDash([]);
  }
}

window.OccupancyChart = OccupancyChart;
