const API = "/__admin";

// ---------------------------------------------------------------------
// Pulse strip: a logic-analyzer style waveform that spikes on each PDU
// ---------------------------------------------------------------------
const pulseCanvas = document.getElementById("pulseStrip");
const pulseCtx = pulseCanvas.getContext("2d");
let pulseEnergy = new Array(220).fill(0);

function resizePulse() {
  const rect = pulseCanvas.getBoundingClientRect();
  pulseCanvas.width = Math.max(200, rect.width) * devicePixelRatio;
  pulseCanvas.height = 40 * devicePixelRatio;
}
window.addEventListener("resize", resizePulse);
resizePulse();

function spike(intensity) {
  pulseEnergy[pulseEnergy.length - 1] = Math.min(1, pulseEnergy[pulseEnergy.length - 1] + intensity);
}

function drawPulse() {
  const w = pulseCanvas.width, h = pulseCanvas.height;
  pulseCtx.clearRect(0, 0, w, h);

  // baseline
  pulseCtx.strokeStyle = "#212b30";
  pulseCtx.lineWidth = 1;
  pulseCtx.beginPath();
  pulseCtx.moveTo(0, h / 2);
  pulseCtx.lineTo(w, h / 2);
  pulseCtx.stroke();

  const n = pulseEnergy.length;
  const step = w / (n - 1);
  pulseCtx.strokeStyle = "#4fd9c4";
  pulseCtx.lineWidth = 1.6 * devicePixelRatio;
  pulseCtx.beginPath();
  for (let i = 0; i < n; i++) {
    const e = pulseEnergy[i];
    const jitter = e > 0.02 ? Math.sin(i * 1.8 + performance.now() / 90) * e : 0;
    const y = h / 2 - (e * (h * 0.42)) - jitter * (h * 0.12) * e;
    const x = i * step;
    if (i === 0) pulseCtx.moveTo(x, y); else pulseCtx.lineTo(x, y);
  }
  pulseCtx.stroke();

  pulseCtx.shadowColor = "#4fd9c4";
  pulseCtx.shadowBlur = 6 * devicePixelRatio;
  pulseCtx.stroke();
  pulseCtx.shadowBlur = 0;

  // decay + scroll
  pulseEnergy.shift();
  pulseEnergy.push(Math.max(0, pulseEnergy[pulseEnergy.length - 1] * 0));
  for (let i = 0; i < n; i++) pulseEnergy[i] *= 0.965;

  requestAnimationFrame(drawPulse);
}
requestAnimationFrame(drawPulse);

// ---------------------------------------------------------------------
// State
// ---------------------------------------------------------------------
let lastRequestCount = 0;
let sessionsCache = [];

// ---------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------
function fmtTime(ts) {
  const d = new Date(ts * 1000);
  return d.toTimeString().slice(0, 8) + "." + String(d.getMilliseconds()).padStart(3, "0");
}

function statusClass(entry) {
  const cs = entry.pdu && entry.pdu.command_status;
  if (entry.commandName && entry.commandName.endsWith("_resp")) {
    if (cs === 0) return "ok";
    if (cs === undefined) return "pending";
    return "err";
  }
  return "pending";
}

function summarize(entry) {
  const p = entry.pdu || {};
  if (entry.commandName === "submit_sm" || entry.commandName === "deliver_sm") {
    const sm = p.short_message || "";
    return `${p.source_addr || "?"} \u2192 ${p.destination_addr || "?"}  "${String(sm).slice(0, 40)}"`;
  }
  if (entry.commandName && entry.commandName.endsWith("_resp")) {
    if ("message_id" in p) return `message_id=${p.message_id || "(empty)"} status=${p.command_status ?? 0}`;
    return `status=${p.command_status ?? 0}`;
  }
  if (entry.commandName && entry.commandName.startsWith("bind")) {
    return `system_id=${p.system_id || "?"}`;
  }
  return "";
}

async function api(path, opts) {
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || res.statusText);
  }
  return res.json();
}

// ---------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------
function renderSessions(sessions) {
  sessionsCache = sessions;
  // Count only currently bound sessions for the headline stat
  const boundCount = sessions.filter(s => s.bound).length;
  document.getElementById("statSessions").textContent = boundCount;

  const list = document.getElementById("sessionList");
  if (sessions.length === 0) {
    list.innerHTML = `<div class="empty-state">No ESME connected yet. Point a client at the SocketMock port.</div>`;
  } else {
    // Sort bound sessions first, then recent unbound sessions by lastSeen desc
    sessions.sort((a,b) => {
      if (a.bound === b.bound) return (b.lastSeen||0) - (a.lastSeen||0);
      return a.bound ? -1 : 1;
    });
    list.innerHTML = sessions.map(s => `
      <div class="session-card ${s.bound ? 'bound' : 'unbound'}">
        <div class="meta">
          <span class="sid">${s.sessionId}</span>
          <span class="badge">${(s.bindType || "").replace("bind_", "").replace("transceiver","trx").replace("transmitter","tx").replace("receiver","rx")}</span>
        </div>
        <div class="meta">
          <span>${s.systemId || "\u2014"}</span>
          <span>${s.peer || ""}</span>
        </div>
        <div class="meta small">
          <span>${s.bound ? 'online' : `last seen ${s.lastSeen ? new Date(s.lastSeen*1000).toLocaleTimeString() : 'unknown'}`}</span>
        </div>
      </div>
    `).join("");
  }

  const select = document.getElementById("dSession");
  const prev = select.value;
  select.innerHTML = sessions.map(s => `<option value="${s.sessionId}">${s.sessionId} (${s.systemId || "?"})</option>`).join("")
    || `<option value="">no sessions bound</option>`;
  if (sessions.some(s => s.sessionId === prev)) select.value = prev;
}

// ---------------------------------------------------------------------
// Trace feed
// ---------------------------------------------------------------------
function appendTraceRow(entry) {
  const feed = document.getElementById("traceFeed");
  const emptyState = feed.querySelector(".empty-state");
  if (emptyState) emptyState.remove();

  const row = document.createElement("div");
  row.className = "trace-row";
  const cls = statusClass(entry);
  row.innerHTML = `
    <span class="trace-time">${fmtTime(entry.timestamp)}</span>
    <span class="trace-dir ${entry.direction}">${entry.direction === "in" ? "\u2192" : "\u2190"}</span>
    <span class="trace-cmd">
      <span class="name">${entry.commandName}</span>
      <span class="detail">${summarize(entry)}</span>
    </span>
    <span class="trace-status ${cls}">${entry.matchedStubId ? "stub" : (entry.commandName || "").endsWith("_resp") ? "auto" : ""}</span>
  `;
  row.addEventListener("click", () => openPduModal(entry));
  feed.appendChild(row);

  if (document.getElementById("autoScroll").checked) {
    feed.scrollTop = feed.scrollHeight;
  }

  const intensity = entry.commandName === "submit_sm" || entry.commandName === "deliver_sm" ? 1 : 0.5;
  spike(intensity);
}

function openPduModal(entry) {
  document.getElementById("pduDetail").textContent = JSON.stringify(entry, null, 2);
  document.getElementById("pduModal").classList.remove("hidden");
}

// ---------------------------------------------------------------------
// Stub mappings
// ---------------------------------------------------------------------
function renderStubs(stubs) {
  document.getElementById("statMappings").textContent = stubs.length;
  const list = document.getElementById("stubList");
  if (stubs.length === 0) {
    list.innerHTML = `<div class="empty-state">No stubs yet. Unmatched traffic still gets a default OK.</div>`;
    return;
  }
  list.innerHTML = stubs.map(s => {
    const req = s.request || {};
    const resp = s.response || {};
    let rule = req.commandName || "any";
    if (req.shortMessage) {
      const m = req.shortMessage;
      const key = Object.keys(m)[0];
      rule += ` &middot; shortMessage ${key} "${m[key]}"`;
    }
    if (req.destinationAddr) {
      const m = req.destinationAddr;
      const key = Object.keys(m)[0];
      rule += ` &middot; destAddr ${key} "${m[key]}"`;
    }
    const chips = [`status ${resp.commandStatus ?? 0}`];
    if (resp.delayMs) chips.push(`+${resp.delayMs}ms`);
    if (resp.deliveryReceipt && resp.deliveryReceipt.enabled) {
      chips.push(`receipt \u2192 ${resp.deliveryReceipt.finalStatus || "DELIVRD"}`);
    }
    return `
      <div class="stub-card" data-id="${s.id}">
        <div class="stub-head">
          <span class="stub-rule">${rule}</span>
          <button class="stub-delete" title="Delete stub">&times;</button>
        </div>
        <div class="stub-response">${chips.map(c => `<span class="chip">${c}</span>`).join("")}</div>
      </div>
    `;
  }).join("");

  list.querySelectorAll(".stub-delete").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      const id = e.target.closest(".stub-card").dataset.id;
      await api(`/mappings/${id}`, { method: "DELETE" });
      poll();
    });
  });
}

// ---------------------------------------------------------------------
// Polling loop
// ---------------------------------------------------------------------
async function poll() {
  try {
    const [sessionsRes, stubsRes, reqRes] = await Promise.all([
      api("/sessions"), api("/mappings"), api("/requests"),
    ]);
    document.getElementById("healthDot").classList.add("live");

    renderSessions(sessionsRes.sessions);
    renderStubs(stubsRes.mappings);

    const requests = reqRes.requests;
    document.getElementById("statRequests").textContent = requests.length;
    if (requests.length > lastRequestCount) {
      requests.slice(lastRequestCount).forEach(appendTraceRow);
    } else if (requests.length < lastRequestCount) {
      // journal was reset elsewhere
      document.getElementById("traceFeed").innerHTML = `<div class="empty-state">Waiting for traffic&hellip;</div>`;
    }
    lastRequestCount = requests.length;
  } catch (err) {
    document.getElementById("healthDot").classList.remove("live");
  }
}
setInterval(poll, 1200);
poll();

// ---------------------------------------------------------------------
// Deliver form
// ---------------------------------------------------------------------
document.getElementById("deliverForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = document.getElementById("deliverStatus");
  status.textContent = "Sending\u2026";
  status.className = "form-status";
  try {
    const body = {
      sessionId: document.getElementById("dSession").value,
      sourceAddr: document.getElementById("dSource").value,
      destinationAddr: document.getElementById("dDest").value,
      shortMessage: document.getElementById("dText").value,
    };
    const res = await api("/deliver", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    status.textContent = `Sent (seq ${res.sequenceNumber})`;
    status.className = "form-status ok";
  } catch (err) {
    status.textContent = err.message;
    status.className = "form-status err";
  }
});

// ---------------------------------------------------------------------
// Stub modal
// ---------------------------------------------------------------------
const stubModal = document.getElementById("stubModal");
document.getElementById("newStubBtn").addEventListener("click", () => stubModal.classList.remove("hidden"));
document.getElementById("closeModal").addEventListener("click", () => stubModal.classList.add("hidden"));
document.getElementById("cancelStub").addEventListener("click", () => stubModal.classList.add("hidden"));
stubModal.addEventListener("click", (e) => { if (e.target === stubModal) stubModal.classList.add("hidden"); });

document.getElementById("sReceiptEnabled").addEventListener("change", (e) => {
  document.getElementById("receiptFields").classList.toggle("hidden", !e.target.checked);
});

document.getElementById("stubForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const request = {};
  const cmd = document.getElementById("sCommand").value;
  if (cmd) request.commandName = cmd;
  const matchValue = document.getElementById("sMatchValue").value;
  if (matchValue) {
    request.shortMessage = { [document.getElementById("sMatchType").value]: matchValue };
  }

  const response = {
    commandStatus: parseInt(document.getElementById("sStatus").value, 10),
    messageId: "sim-{{randomId}}",
    delayMs: parseInt(document.getElementById("sDelay").value, 10) || 0,
  };
  if (document.getElementById("sReceiptEnabled").checked) {
    response.deliveryReceipt = {
      enabled: true,
      delayMs: parseInt(document.getElementById("sReceiptDelay").value, 10) || 1500,
      finalStatus: document.getElementById("sFinalStatus").value,
    };
  }

  await api("/mappings", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      priority: parseInt(document.getElementById("sPriority").value, 10) || 5,
      request, response,
    }),
  });

  stubModal.classList.add("hidden");
  document.getElementById("stubForm").reset();
  document.getElementById("receiptFields").classList.add("hidden");
  poll();
});

// ---------------------------------------------------------------------
// PDU detail modal + clear journal
// ---------------------------------------------------------------------
const pduModal = document.getElementById("pduModal");
document.getElementById("closePduModal").addEventListener("click", () => pduModal.classList.add("hidden"));
pduModal.addEventListener("click", (e) => { if (e.target === pduModal) pduModal.classList.add("hidden"); });

document.getElementById("clearJournal").addEventListener("click", async () => {
  await api("/requests", { method: "DELETE" });
  lastRequestCount = 0;
  document.getElementById("traceFeed").innerHTML = `<div class="empty-state">Waiting for traffic&hellip;</div>`;
});
