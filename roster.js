/* Hub roster + login + incident via OnCall API (same-origin /oncall-api) */
const ONCALL = "/oncall-api";

function chipColor(name) {
  let h = 0;
  String(name || "").split("").forEach((c) => { h = (h * 33 + c.charCodeAt(0)) % 360; });
  return `hsl(${h} 55% 42%)`;
}

function todayISO() {
  const d = new Date();
  const z = (n) => String(n).padStart(2, "0");
  return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate());
}

async function ocGet(path) {
  const r = await fetch(ONCALL + path, { credentials: "include", cache: "no-store" });
  const ct = r.headers.get("content-type") || "";
  if (!r.ok) throw new Error(path + " " + r.status);
  if (!ct.includes("json")) throw new Error(path + " not-json");
  return r.json();
}

async function refreshHubChrome() {
  const dateEl = document.getElementById("hub-date-chip");
  const rosterEl = document.getElementById("hub-roster");
  const loginBtn = document.getElementById("hub-login-btn");
  const whoEl = document.getElementById("hub-who");
  let grid = {}, data = {}, me = null;
  try { grid = await ocGet("/api/on-grid"); } catch (e) {}
  try { data = await ocGet("/api/data?year=" + todayISO().slice(0, 4) + "&month=" + Number(todayISO().slice(5, 7))); } catch (e) { data = { _err: String(e.message || e) }; }
  try { me = await ocGet("/api/session/me"); } catch (e) { me = null; }

  const on = grid.on_grid === true || grid._on_grid_now === "1" || grid._on_grid_now === 1 || (data.on_grid && (data.on_grid.on_grid === true || data.on_grid._on_grid_now === "1"));
  if (dateEl) {
    dateEl.innerHTML = `<span class="dc-date">${todayISO()}</span><span class="dc-mode">${on ? "робочий час" : "неробочий час"}</span>`;
    dateEl.classList.toggle("offgrid", !on);
  }
  if (me && (me.name || me.username)) {
    if (whoEl) whoEl.textContent = me.name || me.username;
    if (loginBtn) { loginBtn.textContent = "Вийти"; loginBtn.dataset.mode = "out"; }
  } else {
    if (whoEl) whoEl.textContent = "";
    if (loginBtn) { loginBtn.textContent = "Увійти"; loginBtn.dataset.mode = "in"; }
  }
  renderRoster(rosterEl, data, todayISO());
}

function renderRoster(el, data, day) {
  if (!el) return;
  const users = (data.team_members || data.users || []).filter((u) => u && u.show_in_roster !== false && u.show_in_roster !== 0);
  let shifts = data.shifts || {};
  if (Array.isArray(shifts)) {
    const m = {};
    shifts.forEach((s) => { if (s && s.date) m[s.date] = s; });
    shifts = m;
  }
  const todayShift = shifts[day] || {};
  const primary = todayShift.primary_user || todayShift.primary || "";
  const backup = todayShift.backup_user || todayShift.backup || "";
  const abs = data.absences || [];
  const brb = data.brb || {};
  const action = `<button type="button" class="spec-chip action" onclick="openHubIncident()">Звернення</button>`;
  if (!users.length) {
    el.innerHTML = `<p class="muted">${data._err ? "OnCall API: " + data._err + ". " : ""}Немає членів у team_members.</p>` + action;
    return;
  }
  el.innerHTML = users.map((u) => {
    const name = u.name || u.username || "";
    const b = brb[name] || brb[u.username];
    const until = typeof b === "string" ? b : (b && (b.until || b.until_at || b.until_planned)) || "";
    let role = "";
    if (name === primary || u.username === primary) role = "основний";
    else if (name === backup || u.username === backup) role = "дублюючий";
    const st = String((abs.find(Boolean) && "") || "");
    const ab = abs.find((a) => {
      const n = a.user_name || a.name || "";
      const ok = n === name || n === u.username;
      const status = String(a.status || "");
      const approved = !status || status === "Approved" || status === "Затверджено";
      const from = a.start_date || a.start || "";
      const to = a.end_date || a.end || "";
      return ok && approved && from <= day && to >= day;
    });
    const absent = !!ab;
    const sub = [
      role,
      until ? "BRB до " + String(until).replace("T", " ").slice(11, 16) : "",
      ab ? ((ab.type || ab.absence_type || "відсутність") + " " + (ab.start_date || "") + "–" + (ab.end_date || "")) : "",
    ].filter(Boolean).join(" · ");
    const faded = absent || until;
    return `<button type="button" class="spec-chip ${faded ? "dim" : ""}" style="--chip:${chipColor(name)}" title="${sub}">
      <span class="spec-name">${name}${absent ? " (відсутній)" : ""}${until ? " · BRB" : ""}</span>
      ${sub ? `<span class="spec-sub">${sub}</span>` : ""}
    </button>`;
  }).join("") + action;
}

window.openHubIncident = function () {
  const m = document.getElementById("hub-inc-modal");
  if (m) m.style.display = "flex";
};
window.closeHubIncident = function () {
  const m = document.getElementById("hub-inc-modal");
  if (m) m.style.display = "none";
};
window.submitHubIncident = async function () {
  const name = (document.getElementById("hi-name") || {}).value || "";
  const email = (document.getElementById("hi-email") || {}).value || "";
  const desc = (document.getElementById("hi-desc") || {}).value || "";
  const prio = (document.getElementById("hi-prio") || {}).value || "Звичайний";
  const st = document.getElementById("hi-status");
  if (!name || !email || !desc) { if (st) st.textContent = "Імʼя, email і опис обовʼязкові"; return; }
  try {
    const r = await fetch(ONCALL + "/api/incidents", {
      method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reporter_name: name, reporter_email: email, description: desc,
        priority: prio, source: "hub-guest", date: todayISO()
      })
    });
    if (!r.ok) throw new Error(await r.text());
    if (st) st.textContent = "Створено";
    setTimeout(() => closeHubIncident(), 800);
  } catch (e) { if (st) st.textContent = String(e.message || e); }
};

window.hubLoginClick = async function () {
  const btn = document.getElementById("hub-login-btn");
  if (btn && btn.dataset.mode === "out") {
    await fetch(ONCALL + "/api/logout", { method: "POST", credentials: "include" });
    refreshHubChrome();
    return;
  }
  const u = prompt("Логін OnCall");
  if (!u) return;
  const p = prompt("Пароль");
  if (p == null) return;
  const r = await fetch(ONCALL + "/api/login", {
    method: "POST", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: u, password: p })
  });
  if (!r.ok) { alert("Вхід не вдався: " + r.status); return; }
  refreshHubChrome();
};

document.addEventListener("DOMContentLoaded", refreshHubChrome);
