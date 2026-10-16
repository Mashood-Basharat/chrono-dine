/**
 * Waitlist & Hostess Management Module
 */
class WaitlistManager {
  constructor() {
    this.parties = [];
    this.selectedPartyForSeating = null;
  }

  init() {
    this.bindEvents();
    this.loadWaitlist();
  }

  bindEvents() {
    document.getElementById("btn-add-party-modal")?.addEventListener("click", () => this.openAddModal());
    document.getElementById("btn-submit-party")?.addEventListener("click", () => this.submitNewParty());
    document.getElementById("btn-cancel-party")?.addEventListener("click", () => this.closeAddModal());

    document.getElementById("btn-confirm-seat")?.addEventListener("click", () => this.confirmSeating());
    document.getElementById("btn-cancel-seat")?.addEventListener("click", () => this.closeSeatModal());
  }

  openAddModal() {
    document.getElementById("modal-add-party")?.classList.add("active");
  }

  closeAddModal() {
    document.getElementById("modal-add-party")?.classList.remove("active");
  }

  openSeatModal(partyId) {
    this.selectedPartyForSeating = partyId;
    const modal = document.getElementById("modal-seat-party");
    const select = document.getElementById("seat-table-select");
    if (!modal || !select) return;

    // Populate available tables from live telemetry or zones
    const telemetry = window.appState?.telemetry?.tables || {};
    let optionsHtml = "";
    for (const [name, state] of Object.entries(telemetry)) {
      const isFree = state.status === "FREE";
      optionsHtml += `<option value="${name}">${name} (${state.seats} Seats) – ${isFree ? 'AVAILABLE' : 'OCCUPIED'}</option>`;
    }
    select.innerHTML = optionsHtml || `<option value="Table 1">Table 1</option>`;

    modal.classList.add("active");
  }

  closeSeatModal() {
    this.selectedPartyForSeating = null;
    document.getElementById("modal-seat-party")?.classList.remove("active");
  }

  async loadWaitlist() {
    try {
      const res = await fetch("/api/waitlist");
      this.parties = await res.json();
      this.render();
    } catch (err) {
      console.error("Failed to load waitlist:", err);
    }
  }

  async submitNewParty() {
    const name = document.getElementById("party-name-input")?.value?.trim();
    const size = parseInt(document.getElementById("party-size-input")?.value || "2");
    const phone = document.getElementById("party-phone-input")?.value?.trim();
    const quoted = parseInt(document.getElementById("party-quote-input")?.value || "15");
    const notes = document.getElementById("party-notes-input")?.value?.trim();

    if (!name) {
      alert("Please enter customer name.");
      return;
    }

    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customer_name: name,
          party_size: size,
          phone: phone,
          quoted_minutes: quoted,
          notes: notes
        })
      });

      if (!res.ok) throw new Error("Failed to add party");

      this.closeAddModal();
      document.getElementById("party-name-input").value = "";
      document.getElementById("party-phone-input").value = "";
      document.getElementById("party-notes-input").value = "";

      await this.loadWaitlist();
    } catch (err) {
      alert("Failed to add party to waitlist.");
    }
  }

  async confirmSeating() {
    if (!this.selectedPartyForSeating) return;
    const table = document.getElementById("seat-table-select")?.value;
    if (!table) return;

    try {
      await fetch(`/api/waitlist/${this.selectedPartyForSeating}/seat?table_name=${encodeURIComponent(table)}`, {
        method: "PUT"
      });
      this.closeSeatModal();
      await this.loadWaitlist();
    } catch (err) {
      alert("Error assigning table.");
    }
  }

  async cancelParty(partyId) {
    if (!confirm("Cancel this party's waitlist ticket?")) return;
    try {
      await fetch(`/api/waitlist/${partyId}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "CANCELLED" })
      });
      await this.loadWaitlist();
    } catch (err) {
      console.error(err);
    }
  }

  render() {
    const waitingContainer = document.getElementById("waiting-parties-list");
    const seatedContainer = document.getElementById("seated-parties-list");

    if (!waitingContainer || !seatedContainer) return;

    const waiting = this.parties.filter(p => p.status === "WAITING");
    const seated = this.parties.filter(p => p.status === "SEATED");

    // Render Waiting
    if (waiting.length === 0) {
      waitingContainer.innerHTML = `<div style="color: var(--text-muted); font-size: 0.9rem; padding: 1.5rem 0;">No parties currently in the queue. Click '+ New Party' to add one.</div>`;
    } else {
      waitingContainer.innerHTML = waiting.map(p => `
        <div class="party-card ${p.is_overdue ? 'overdue' : ''}">
          <div>
            <div style="display: flex; align-items: baseline; gap: 0.5rem;">
              <span style="font-weight: 700; font-size: 1.05rem; color: #fff;">${p.customer_name}</span>
              <span class="status-pill" style="font-size: 0.7rem;">Party of ${p.party_size}</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.2rem;">
              Waited <strong>${p.wait_minutes}m</strong> (Quoted: ${p.quoted_minutes}m) ${p.phone ? '· ' + p.phone : ''}
            </div>
            ${p.notes ? `<div style="font-size: 0.75rem; color: var(--text-muted); font-style: italic;">"${p.notes}"</div>` : ''}
          </div>
          <div style="display: flex; gap: 0.5rem;">
            <button class="btn btn-primary btn-sm" onclick="window.waitlistManager.openSeatModal(${p.id})">Seat</button>
            <button class="btn btn-secondary btn-sm" onclick="window.waitlistManager.cancelParty(${p.id})">×</button>
          </div>
        </div>
      `).join("");
    }

    // Render Seated
    if (seated.length === 0) {
      seatedContainer.innerHTML = `<div style="color: var(--text-muted); font-size: 0.9rem; padding: 1.5rem 0;">No parties currently seated through the hostess queue.</div>`;
    } else {
      seatedContainer.innerHTML = seated.slice(0, 10).map(p => `
        <div class="party-card" style="opacity: 0.85;">
          <div>
            <div style="font-weight: 600; color: #fff;">${p.customer_name} (Party of ${p.party_size})</div>
            <div style="font-size: 0.8rem; color: var(--text-secondary);">Seated at <strong style="color: var(--accent-emerald);">${p.assigned_table || 'Assigned'}</strong> at ${p.seated_at || ''}</div>
          </div>
          <span class="table-badge free">Seated</span>
        </div>
      `).join("");
    }
  }
}

window.waitlistManager = new WaitlistManager();
