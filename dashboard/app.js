/* ═══════════════════════════════════════════════════════
   OutreachOS — Frontend (real API mode)
   API base: http://localhost:5000/api
═══════════════════════════════════════════════════════ */

const API = "http://localhost:5000/api";

/* ── State ──────────────────────────────────────────── */
const S = {
  contacts:        [],
  results:         [],
  campaignRunning: false,
};

/* ── Helpers ─────────────────────────────────────────── */
const $  = id => document.getElementById(id);
const ts = () => new Date().toLocaleTimeString();

async function apiFetch(path, opts = {}) {
  try {
    const res = await fetch(API + path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  } catch (e) {
    addLog(`❌ API error (${path}): ${e.message}`, "error");
    throw e;
  }
}

function addLog(msg, type = "info") {
  const feed = $("log-feed");
  const el = document.createElement("div");
  el.className = `log-entry ${type}`;
  el.innerHTML = `<span class="log-ts">${ts()}</span><span class="log-msg">${msg}</span>`;
  feed.appendChild(el);
  feed.scrollTop = feed.scrollHeight;
  while (feed.children.length > 150) feed.removeChild(feed.firstChild);
}

function toast(msg, ok = true) {
  const t = document.createElement("div");
  t.className = "toast " + (ok ? "toast-ok" : "toast-err");
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.classList.add("show"), 10);
  setTimeout(() => { t.classList.remove("show"); setTimeout(() => t.remove(), 300); }, 3000);
}

/* ── Navigation ──────────────────────────────────────── */
document.querySelectorAll(".nav-item").forEach(item => {
  item.addEventListener("click", e => {
    e.preventDefault();
    const view = item.dataset.view;
    document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
    item.classList.add("active");
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    $("view-" + view).classList.add("active");
    $("page-title").textContent = item.querySelector("span:last-child").textContent.trim();
    if (view === "results")  loadResults();
    if (view === "settings") loadSettings();
    if (view === "contacts") renderContactsTable();
  });
});

$("launch-btn").addEventListener("click", () => $("nav-campaign").click());

/* ── Health Check ────────────────────────────────────── */
async function checkHealth() {
  try {
    const h = await apiFetch("/health");
    addLog(`✅ Connected to server. College: ${h.college}. Services: ${h.services_loaded ? "OK" : "Limited"}`, "success");
    setStatus("idle", "Connected");
  } catch {
    addLog("⚠ Server not reachable. Make sure server.py is running on port 5000.", "error");
    setStatus("offline", "Offline");
    toast("⚠ Backend offline. Run: python server.py", false);
  }
}

function setStatus(type, label) {
  $("status-text").textContent = label;
  const pulse = $("status-pill").querySelector(".pulse");
  pulse.className = "pulse" + (type === "running" ? " running" : "");
}

/* ═══════════════════════════════════════════════════════
   CONTACTS
═══════════════════════════════════════════════════════ */
async function fetchContacts() {
  const data = await apiFetch("/contacts");
  S.contacts = data.contacts || [];
  renderContactsTable();
  updateStats();
}

/* Import CSV */
$("import-csv-btn").addEventListener("click", () => $("csv-file-input").click());
$("ql-load-btn").addEventListener("click", async () => {
  try {
    const data = await apiFetch("/contacts/load-sample", { method: "POST" });
    S.contacts = data.contacts || [];
    renderContactsTable();
    updateStats();
    addLog(`✅ Loaded ${data.loaded} sample contacts from data/sample_contacts.csv`, "success");
    toast(`Loaded ${data.loaded} sample contacts`);
    markStep(1, true); markStep(2, true);
    $("nav-contacts").click();
  } catch (err) {
    addLog(`❌ Failed to load sample contacts: ${err.message}`, "error");
    toast("Load sample contacts failed", false);
  }
});

$("csv-file-input").addEventListener("change", async e => {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch(API + "/contacts/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed");
    S.contacts = data.contacts || [];
    renderContactsTable();
    updateStats();
    addLog(`✅ Loaded ${data.loaded} contacts from "${file.name}"`, "success");
    toast(`Loaded ${data.loaded} contacts`);
    markStep(1, true); markStep(2, true);
  } catch (err) {
    addLog(`❌ CSV upload failed: ${err.message}`, "error");
    toast("CSV upload failed: " + err.message, false);
  }
  e.target.value = "";
});

/* Export contacts CSV */
$("export-contacts-btn")?.addEventListener("click", () => window.open(API + "/contacts/export"));

/* Render table */
let _contactFilter = "";
function renderContactsTable(filter = _contactFilter) {
  _contactFilter = filter;
  const tbody = $("contacts-tbody");
  const list  = S.contacts.filter(c => !filter || Object.values(c).some(v => v.toLowerCase().includes(filter.toLowerCase())));

  if (!list.length) {
    tbody.innerHTML = `<tr class="empty-row"><td colspan="7">${S.contacts.length ? "No matches." : "No contacts. Import CSV or add manually."}</td></tr>`;
  } else {
    tbody.innerHTML = list.map((c, i) => {
      const realIdx = S.contacts.indexOf(c);
      return `<tr data-idx="${realIdx}">
        <td><input type="checkbox" class="row-check" data-idx="${realIdx}" /></td>
        <td>${c.name || "—"}</td>
        <td>${c.email || "—"}</td>
        <td>${c.phone || "—"}</td>
        <td>${c.course || "—"}</td>
        <td>${c.city || "—"}</td>
        <td><button class="btn-ghost danger del-row" data-idx="${realIdx}" style="padding:4px 10px;font-size:11px">✕</button></td>
      </tr>`;
    }).join("");

    tbody.querySelectorAll(".del-row").forEach(btn => {
      btn.addEventListener("click", async () => {
        const idx = parseInt(btn.dataset.idx);
        try {
          await apiFetch(`/contacts/${idx}`, { method: "DELETE" });
          S.contacts.splice(idx, 1);
          renderContactsTable();
          updateStats();
          addLog(`🗑 Deleted contact at index ${idx}`, "warning");
        } catch {}
      });
    });
  }
  $("contact-count-label").textContent = `${S.contacts.length} contact${S.contacts.length !== 1 ? "s" : ""}`;
}

$("search-contacts").addEventListener("input", e => renderContactsTable(e.target.value));

$("select-all").addEventListener("change", e => {
  document.querySelectorAll(".row-check").forEach(cb => cb.checked = e.target.checked);
});

$("delete-selected-btn").addEventListener("click", async () => {
  const idxs = [...document.querySelectorAll(".row-check:checked")].map(cb => parseInt(cb.dataset.idx));
  if (!idxs.length) { toast("No contacts selected", false); return; }
  try {
    await apiFetch("/contacts/bulk-delete", { method: "POST", body: JSON.stringify({ indices: idxs }) });
    S.contacts = S.contacts.filter((_, i) => !idxs.includes(i));
    renderContactsTable();
    updateStats();
    addLog(`🗑 Deleted ${idxs.length} contacts`, "warning");
    toast(`Deleted ${idxs.length} contacts`);
  } catch {}
});

/* Add contact modal */
$("add-contact-btn").addEventListener("click", () => $("add-modal").classList.add("open"));
$("close-modal-btn").addEventListener("click", () => $("add-modal").classList.remove("open"));
$("add-modal").addEventListener("click", e => { if (e.target === $("add-modal")) $("add-modal").classList.remove("open"); });

$("save-contact-btn").addEventListener("click", async () => {
  const body = {
    name:   $("m-name").value.trim(),
    email:  $("m-email").value.trim(),
    phone:  $("m-phone").value.trim(),
    course: $("m-course").value.trim(),
    city:   $("m-city").value.trim(),
  };
  if (!body.name) { toast("Name is required", false); return; }
  try {
    const data = await apiFetch("/contacts", { method: "POST", body: JSON.stringify(body) });
    S.contacts.push(data.contact);
    renderContactsTable();
    updateStats();
    ["m-name","m-email","m-phone","m-course","m-city"].forEach(id => $(id).value = "");
    $("add-modal").classList.remove("open");
    addLog(`➕ Added contact: ${body.name}`, "success");
    toast(`Added ${body.name}`);
    markStep(1, true);
  } catch {}
});

/* ═══════════════════════════════════════════════════════
   CAMPAIGN — SSE Streaming
═══════════════════════════════════════════════════════ */
$("run-campaign-btn").addEventListener("click", runCampaign);

async function runCampaign() {
  if (S.campaignRunning) return;
  if (!S.contacts.length) { toast("No contacts. Import CSV first.", false); return; }

  const channels = [];
  if ($("chip-email").querySelector("input").checked)  channels.push("email");
  if ($("chip-sms").querySelector("input").checked)    channels.push("sms");
  if ($("chip-wa").querySelector("input").checked)     channels.push("whatsapp");
  if ($("chip-voice").querySelector("input").checked)  channels.push("voice");
  if (!channels.length) { toast("Select at least one channel.", false); return; }

  const limit = parseInt($("camp-limit").value) || null;
  const delay = parseFloat($("camp-delay").value) || 0.5;

  S.campaignRunning = true;
  S.results = [];
  $("progress-card").style.display = "block";
  $("run-campaign-btn").disabled = true;
  $("run-campaign-btn").textContent = "⏳ Running...";
  setStatus("running", "Running");
  markStep(3, true);

  let sent = 0, skipped = 0, failed = 0;

  const body = JSON.stringify({ channels, limit, delay });
  const evtSrc = new EventSource(API + "/campaign/run?" + new URLSearchParams({ channels: channels.join(","), limit: limit || "", delay }));

  // EventSource doesn't support POST body, so use fetch with ReadableStream
  evtSrc.close();

  try {
    const res = await fetch(API + "/campaign/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        try {
          const msg = JSON.parse(line.slice(5).trim());
          handleSSE(msg, { sent: () => sent, skipped: () => skipped, failed: () => failed,
            setSent: v => sent = v, setSkip: v => skipped = v, setFail: v => failed = v });
        } catch {}
      }
    }
  } catch (err) {
    addLog(`❌ Campaign stream error: ${err.message}`, "error");
    toast("Campaign error: " + err.message, false);
  }

  finishCampaign();
}

function handleSSE(msg, counters) {
  if (msg.type === "ping") return;

  if (msg.type === "start") {
    addLog(`🚀 Campaign started: ${msg.contacts} contacts × ${msg.channels.join(", ")}`, "info");
    $("p-rem").textContent = msg.total;
  }

  if (msg.type === "channel_start") {
    addLog(`▶ Channel: ${msg.channel.toUpperCase()}`, "info");
  }

  if (msg.type === "progress") {
    const r = msg.result || {};
    const isOk = r.status === "sent" || r.status === "dialed";
    if (isOk)           counters.setSent(counters.sent() + 1);
    else if (r.status === "skipped") counters.setSkip(counters.skipped() + 1);
    else                counters.setFail(counters.failed() + 1);

    const icon = isOk ? "✅" : r.status === "skipped" ? "⏭" : "❌";
    addLog(`${icon} [${(r.channel||"").toUpperCase()}] ${r.contact} → ${r.status}${r.reason ? ": " + r.reason : ""}`,
      isOk ? "success" : r.status === "skipped" ? "warning" : "error");

    $("progress-bar").style.width  = msg.pct + "%";
    $("prog-percent").textContent   = msg.pct + "%";
    $("p-sent").textContent         = counters.sent();
    $("p-skip").textContent         = counters.skipped();
    $("p-fail").textContent         = counters.failed();
    $("p-rem").textContent          = msg.total - msg.done;

    S.results.push(r);
    updateStats();
  }

  if (msg.type === "done") {
    addLog(`🎉 Done: ${msg.sent} sent, ${msg.skipped} skipped, ${msg.failed} failed. Log: ${msg.log_file}`, "success");
    toast(`Campaign done! ${msg.sent} sent.`);
    markStep(4, true);
    setTimeout(() => $("nav-results").click(), 1500);
  }

  if (msg.type === "error") {
    addLog(`❌ Error in ${msg.channel}: ${msg.message}`, "error");
  }
}

function finishCampaign() {
  S.campaignRunning = false;
  $("run-campaign-btn").disabled = false;
  $("run-campaign-btn").textContent = "⚡ Run Campaign";
  setStatus("idle", "Done");
}

/* ═══════════════════════════════════════════════════════
   RESULTS
═══════════════════════════════════════════════════════ */
async function loadResults() {
  try {
    const data = await apiFetch("/results");
    S.results = data.results || [];
  } catch {}
  renderResults();
}

function renderResults() {
  const activeFilter = document.querySelector(".filter-chip.active")?.dataset.filter || "all";
  const filtered = S.results.filter(r =>
    activeFilter === "all" ||
    r.status === activeFilter ||
    (activeFilter === "sent" && r.status === "dialed")
  );

  const tbody = $("results-tbody");
  tbody.innerHTML = filtered.length
    ? filtered.map(r => `
      <tr>
        <td>${r.contact || "—"}</td>
        <td>${r.channel || "—"}</td>
        <td><span class="badge ${r.status === "dialed" ? "dialed" : r.status}">${r.status}</span></td>
        <td style="font-size:12px">${r.email || r.phone || "—"}</td>
        <td style="font-size:11px;color:var(--muted);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          ${r.reason || r.message_id || r.message_sid || r.call_sid || "—"}
        </td>
      </tr>`).join("")
    : `<tr class="empty-row"><td colspan="5">No results${activeFilter !== "all" ? " for this filter" : ". Run a campaign first."}.</td></tr>`;

  // Summary ring
  const total   = S.results.length;
  const sent    = S.results.filter(r => ["sent","dialed"].includes(r.status)).length;
  const skipped = S.results.filter(r => r.status === "skipped").length;
  const errored = S.results.filter(r => r.status === "error").length;
  const pct     = total ? Math.round(sent / total * 100) : 0;

  $("ring-rate").textContent  = pct + "%";
  $("rb-sent").textContent    = sent;
  $("rb-skip").textContent    = skipped;
  $("rb-fail").textContent    = errored;
  $("ring-progress").style.strokeDashoffset = 314 - (314 * pct / 100);

  // Channel bars
  const ch = { email: 0, sms: 0, whatsapp: 0, voice: 0 };
  S.results.forEach(r => { if (r.channel in ch && ["sent","dialed"].includes(r.status)) ch[r.channel]++; });
  const maxV = Math.max(...Object.values(ch), 1);
  $("res-email-bar").style.width  = (ch.email    / maxV * 100) + "%"; $("res-email-val").textContent  = ch.email;
  $("res-sms-bar").style.width    = (ch.sms      / maxV * 100) + "%"; $("res-sms-val").textContent    = ch.sms;
  $("res-wa-bar").style.width     = (ch.whatsapp / maxV * 100) + "%"; $("res-wa-val").textContent     = ch.whatsapp;
  $("res-voice-bar").style.width  = (ch.voice    / maxV * 100) + "%"; $("res-voice-val").textContent  = ch.voice;
}

document.querySelectorAll(".filter-chip").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".filter-chip").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    renderResults();
  });
});

$("export-json-btn").addEventListener("click", () => {
  window.location.href = API + "/results/export";
});

/* ═══════════════════════════════════════════════════════
   SETTINGS — reads/writes .env via API
═══════════════════════════════════════════════════════ */
const FIELD_MAP = {
  "s-ejs-sid":     "EMAILJS_SERVICE_ID",
  "s-ejs-tid":     "EMAILJS_TEMPLATE_ID",
  "s-ejs-pub":     "EMAILJS_PUBLIC_KEY",
  "s-ejs-priv":    "EMAILJS_PRIVATE_KEY",
  "s-ejs-from":    "EMAILJS_FROM_NAME",
  "s-ejs-reply":   "EMAILJS_REPLY_TO",
  "s-tw-sid":      "TWILIO_ACCOUNT_SID",
  "s-tw-token":    "TWILIO_AUTH_TOKEN",
  "s-tw-from":     "TWILIO_FROM_NUMBER",
  "s-tw-verified": "VERIFIED_TEST_NUMBERS",
  "s-wa-token":    "WHATSAPP_API_TOKEN",
  "s-wa-pid":      "WHATSAPP_PHONE_NUMBER_ID",
  "s-col-name":    "COLLEGE_NAME",
  "s-col-phone":   "COLLEGE_PHONE",
  "s-col-web":     "COLLEGE_WEBSITE",
  "s-col-year":    "ADMISSION_YEAR",
};

async function loadSettings() {
  try {
    const data = await apiFetch("/settings");
    Object.entries(FIELD_MAP).forEach(([elId, key]) => {
      const el = $(elId);
      if (el && data[key] !== undefined) el.value = data[key];
    });
  } catch {}
}

$("save-settings-btn").addEventListener("click", async () => {
  const payload = {};
  Object.entries(FIELD_MAP).forEach(([elId, key]) => {
    const el = $(elId);
    if (el && el.value) payload[key] = el.value;
  });
  try {
    await apiFetch("/settings/raw", { method: "POST", body: JSON.stringify(payload) });
    addLog("💾 Settings saved to .env", "success");
    toast("Settings saved to .env ✅");
  } catch {}
});

$("reset-settings-btn").addEventListener("click", () => {
  if (!confirm("Reset all settings fields?")) return;
  Object.keys(FIELD_MAP).forEach(id => { const el = $(id); if (el) el.value = ""; });
  addLog("↩ Settings fields cleared", "warning");
});

/* ═══════════════════════════════════════════════════════
   STATS
═══════════════════════════════════════════════════════ */
function updateStats() {
  $("stat-total").textContent = S.contacts.length;
  const sent  = S.results.filter(r => ["sent","dialed"].includes(r.status)).length;
  const total = S.results.length;
  $("stat-sent").textContent = sent;
  $("stat-rate").textContent = total ? Math.round(sent / total * 100) + "%" : "0%";
}

/* ── Channel usage bars (dashboard) ─ */
function updateChannelBars() {
  const emailC = S.results.filter(r => r.channel === "email"    && r.status === "sent").length;
  const smsC   = S.results.filter(r => r.channel === "sms"      && r.status === "sent").length;
  const waC    = S.results.filter(r => r.channel === "whatsapp" && r.status === "sent").length;
  const vcC    = S.results.filter(r => r.channel === "voice"    && r.status === "dialed").length;
  $("email-bar").style.width = Math.min(emailC / 200 * 100, 100) + "%";
  $("sms-bar").style.width   = Math.min(smsC   / 50  * 100, 100) + "%";
  $("wa-bar").style.width    = Math.min(waC    / 50  * 100, 100) + "%";
  $("voice-bar").style.width = Math.min(vcC    / 50  * 100, 100) + "%";
}

/* ── Preview Tabs ────────────────────────────────────── */
document.querySelectorAll(".ptab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".ptab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    document.querySelectorAll(".preview-panel").forEach(p => p.classList.add("hidden"));
    $("preview-" + tab.dataset.tab).classList.remove("hidden");
  });
});

/* ── Quick Steps ─────────────────────────────────────── */
function markStep(n, done) {
  const el = $(`q${n}`);
  if (el) { el.classList.toggle("done", done); el.classList.remove("active"); }
}

/* ── Clear Log ───────────────────────────────────────── */
$("clear-log-btn").addEventListener("click", () => {
  $("log-feed").innerHTML = `<div class="log-entry info"><span class="log-ts">${ts()}</span><span class="log-msg">Log cleared.</span></div>`;
});

/* ── Log history modal ───────────────────────────────── */
async function openLogModal() {
  try {
    const data = await apiFetch("/logs");
    const logs = data || [];
    const list = logs.map(l => `<div class="log-entry info" style="cursor:pointer;user-select:none" onclick="loadLogFile('${l.name}')">
      <span class="log-ts">${(l.modified||"").slice(0,19).replace("T"," ")}</span>
      <span class="log-msg">${l.name} &nbsp;(${(l.size/1024).toFixed(1)} KB)</span>
    </div>`).join("") || "<div class='log-entry'>No saved logs found.</div>";
    $("log-history-body").innerHTML = list;
    $("log-history-modal").classList.add("open");
  } catch {}
}

$("view-logs-btn")?.addEventListener("click", openLogModal);
$("view-logs-btn-s")?.addEventListener("click", openLogModal);
$("close-log-modal-btn")?.addEventListener("click", () => $("log-history-modal").classList.remove("open"));
$("log-history-modal")?.addEventListener("click", e => { if (e.target === $("log-history-modal")) $("log-history-modal").classList.remove("open"); });

window.loadLogFile = async name => {
  try {
    const data = await apiFetch(`/logs/${name}`);
    S.results = Array.isArray(data) ? data : [];
    $("log-history-modal").classList.remove("open");
    $("nav-results").click();
    toast(`Loaded: ${name}`);
  } catch {}
};

/* ═══════════════════════════════════════════════════════
   BOOT
═══════════════════════════════════════════════════════ */
(async () => {
  await checkHealth();
  await fetchContacts();
  renderContactsTable();
  updateStats();
  markStep(1, true);
  addLog("🎓 OutreachOS ready.", "info");
})();
