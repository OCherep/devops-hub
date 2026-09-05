const ONCALL_BASES = ["/oncall-api", "https://s.ks.tv:85"];
function ocToken() { try { return localStorage.getItem("oncall_session") || ""; } catch (e) { return ""; } }
function ocSetToken(t) { try { if (t) localStorage.setItem("oncall_session", t); else localStorage.removeItem("oncall_session"); } catch (e) {} }

async function ocFetch(path, opts) {
  opts = opts || {};
  const headers = Object.assign({ "Accept": "application/json" }, opts.headers || {});
  const tok = ocToken();
  if (tok) headers["Authorization"] = "Bearer " + tok;
  let lastErr = "offline";
  for (const base of ONCALL_BASES) {
    try {
      const r = await fetch(base + path, Object.assign({}, opts, { headers, credentials: "include" }));
      const ct = r.headers.get("content-type") || "";
      if (r.status === 204) return { ok: true };
      if (!ct.includes("json") && r.status !== 405) { lastErr = path + " not-json @" + base; continue; }
      const body = ct.includes("json") ? await r.json() : { error: await r.text() };
      if (!r.ok) { lastErr = (body && body.error) || (path + " " + r.status); if (r.status === 405) continue; throw new Error(lastErr); }
      return body;
    } catch (e) { lastErr = e.message || String(e); }
  }
  throw new Error(lastErr);
}

function todayISO() {
  const d = new Date();
  const z = (n) => String(n).padStart(2, "0");
  return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate());
}
function chipColor(name) {
  let h = 0; String(name || "").split("").forEach((c) => { h = (h * 33 + c.charCodeAt(0)) % 360; });
  return `hsl(${h} 55% 42%)`;
}

async function refreshHubChrome() {
  const dateEl = document.getElementById("hub-date-chip");
  const rosterEl = document.getElementById("hub-roster");
  const loginBtn = document.getElementById("hub-login-btn");
  const whoEl = document.getElementById("hub-who");
  let grid = {}, data = {}, me = null;
  try { grid = await ocFetch("/api/on-grid"); } catch (e) {}
  try { data = await ocFetch("/api/data?year=" + todayISO().slice(0, 4) + "&month=" + Number(todayISO().slice(5, 7))); }
  catch (e) { data = { _err: String(e.message || e) }; }
  try { me = await ocFetch("/api/session/me"); } catch (e) { me = null; }
  const snap = grid.on_grid !== undefined ? grid : (data.on_grid || {});
  const on = snap.on_grid === true || snap._on_grid_now === "1" || snap._on_grid_now === 1;
  if (dateEl) {
    dateEl.innerHTML = `<span class="dc-date">${todayISO()}</span><span class="dc-mode">${on ? "робочий час" : "неробочий час"}</span>`;
    dateEl.classList.toggle("offgrid", !on);
  }
  const named = me && (me.name || me.username);
  if (whoEl) whoEl.textContent = named || "";
  if (loginBtn) {
    loginBtn.textContent = named ? "Вийти" : "Увійти";
    loginBtn.dataset.mode = named ? "out" : "in";
  }
  renderRoster(rosterEl, data, todayISO());
}

function renderRoster(el, data, day) {
  if (!el) return;
  const users = (data.team_members || data.users || []).filter((u) => u && u.show_in_roster !== false && u.show_in_roster !== 0);
  let shifts = data.shifts || {};
  if (Array.isArray(shifts)) {
    const m = {}; shifts.forEach((s) => { if (s && s.date) m[s.date] = s; }); shifts = m;
  }
  const sh = shifts[day] || {};
  const primary = sh.primary_user || sh.primary || "";
  const backup = sh.backup_user || sh.backup || "";
  const abs = data.absences || [];
  const brb = data.brb || {};
  const action = `<button type="button" class="spec-chip action" onclick="openHubIncident()">Звернення</button>`;
  if (!users.length) {
    el.innerHTML = `<p class="muted">${data._err ? "OnCall API: " + data._err : "Немає team_members"}</p>` + action;
    return;
  }
  el.innerHTML = users.map((u) => {
    const name = u.name || u.username || "";
    const b = brb[name] || brb[u.username];
    const until = typeof b === "string" ? b : (b && (b.until || b.until_at || b.until_planned)) || "";
    let role = "";
    if (name === primary || u.username === primary) role = "основний";
    else if (name === backup || u.username === backup) role = "дублюючий";
    const ab = abs.find((a) => {
      const n = a.user_name || a.name || "";
      const status = String(a.status || "");
      const approved = !status || status === "Approved" || status === "Затверджено";
      return (n === name || n === u.username) && approved && (a.start_date || "") <= day && (a.end_date || "") >= day;
    });
    const sub = [role, until ? "BRB до " + String(until).replace("T", " ").slice(11, 16) : "",
      ab ? ((ab.type || "відсутність") + " " + (ab.start_date || "") + "–" + (ab.end_date || "")) : ""].filter(Boolean).join(" · ");
    return `<button type="button" class="spec-chip ${ab || until ? "dim" : ""}" style="--chip:${chipColor(name)}" title="${sub}">
      <span class="spec-name">${name}${ab ? " (відсутній)" : ""}${until ? " · BRB" : ""}</span>
      ${sub ? `<span class="spec-sub">${sub}</span>` : ""}</button>`;
  }).join("") + action;
}

window.openHubIncident = function () { const m = document.getElementById("hub-inc-modal"); if (m) m.style.display = "flex"; };
window.closeHubIncident = function () { const m = document.getElementById("hub-inc-modal"); if (m) m.style.display = "none"; };
window.openHubLogin = function () {
  const btn = document.getElementById("hub-login-btn");
  if (btn && btn.dataset.mode === "out") { ocFetch("/api/logout", { method: "POST" }).finally(() => { ocSetToken(""); refreshHubChrome(); }); return; }
  const m = document.getElementById("hub-login-modal"); if (m) m.style.display = "flex";
};
window.closeHubLogin = function () { const m = document.getElementById("hub-login-modal"); if (m) m.style.display = "none"; };
window.submitHubLogin = async function () {
  const u = (document.getElementById("hl-user") || {}).value || "";
  const p = (document.getElementById("hl-pass") || {}).value || "";
  const st = document.getElementById("hl-status");
  try {
    const d = await ocFetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: u, password: p }) });
    if (d.session_token) ocSetToken(d.session_token);
    if (st) st.textContent = "Ок";
    closeHubLogin();
    refreshHubChrome();
  } catch (e) { if (st) st.textContent = e.message || String(e); }
};
window.submitHubIncident = async function () {
  const payload = {
    reporter_name: (document.getElementById("hi-name") || {}).value || "",
    reporter_email: (document.getElementById("hi-email") || {}).value || "",
    reporter_slack: (document.getElementById("hi-slack") || {}).value || "",
    description: (document.getElementById("hi-desc") || {}).value || "",
    priority: (document.getElementById("hi-prio") || {}).value || "Звичайний",
    source: "hub-guest", date: todayISO(), duration_minutes: Number((document.getElementById("hi-mins") || {}).value || 15)
  };
  const st = document.getElementById("hi-status");
  if (!payload.reporter_name || !payload.reporter_email || !payload.description) { if (st) st.textContent = "Імʼя, email і опис обовʼязкові"; return; }
  try { await ocFetch("/api/incidents", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); if (st) st.textContent = "Створено"; setTimeout(closeHubIncident, 700); }
  catch (e) { if (st) st.textContent = e.message || String(e); }
};
window.lookupHubSlack = async function () {
  const slack = (document.getElementById("hi-slack") || {}).value || "";
  const st = document.getElementById("hi-status");
  if (!slack) { if (st) st.textContent = "Вкажіть Slack"; return; }
  try {
    const d = await ocFetch("/api/slack/lookup?q=" + encodeURIComponent(slack));
    if (d.email && document.getElementById("hi-email")) document.getElementById("hi-email").value = d.email;
    if (d.name && document.getElementById("hi-name")) document.getElementById("hi-name").value = d.name;
    if (st) st.textContent = d.name ? ("Slack: " + d.name) : "не знайдено";
  } catch (e) { if (st) st.textContent = e.message || String(e); }
};

document.addEventListener("DOMContentLoaded", () => {
  const b = document.getElementById("hub-login-btn");
  if (b) b.setAttribute("onclick", "openHubLogin()");
  refreshHubChrome();
});
