/* Hub roster + login + incident via OnCall API (same-origin /oncall-api) */
const ONCALL = "/oncall-api";

function chipColor(name) {
  let h = 0;
  String(name || "").split("").forEach((c) => { h = (h * 33 + c.charCodeAt(0)) % 360; });
  return `hsl(${h} 42% 38%)`;
}

function todayISO() {
  const d = new Date();
  const z = (n) => String(n).padStart(2, "0");
  return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate());
}

async function ocGet(path) {
  const r = await fetch(ONCALL + path, { credentials: "include", cache: "no-store" });
  if (!r.ok) throw new Error(path + " " + r.status);
  return r.json();
}

async function refreshHubChrome() {
  const dateEl = document.getElementById("hub-date-chip");
  const rosterEl = document.getElementById("hub-roster");
  const loginBtn = document.getElementById("hub-login-btn");
  const whoEl = document.getElementById("hub-who");
  try {
    const [grid, data, me] = await Promise.all([
      ocGet("/api/on-grid").catch(() => ({})),
      ocGet("/api/data?year=" + todayISO().slice(0, 4) + "&month=" + Number(todayISO().slice(5, 7))).catch(() => ({})),
      ocGet("/api/session/me").catch(() => null),
    ]);
    const on = grid.on_grid === true || grid._on_grid_now === "1" || grid._on_grid_now === 1;
    if (dateEl) {
      dateEl.innerHTML = `<b>${todayISO()}</b><small>${on ? "робочий час" : "неробочий час"}</small>`;
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
  } catch (e) {
    if (rosterEl) rosterEl.innerHTML = `<p class="muted">OnCall недоступний (${e.message})</p>`;
  }
}

function renderRoster(el, data, day) {
  if (!el) return;
  const users = (data.users || []).filter((u) => u.show_in_roster !== false && u.show_in_roster !== 0);
  const shifts = data.shifts || {};
  const abs = data.absences || [];
  const brb = data.brb || {};
  const todayShift = shifts[day] || {};
  const primary = todayShift.primary || todayShift.user1 || "";
  const backup = todayShift.backup || todayShift.user2 || "";
  if (!users.length) {
    el.innerHTML = `<p class="muted">Немає членів команди в roster.</p>`;
    return;
  }
  el.innerHTML = users.map((u) => {
    const name = u.name || u.username || "";
    const b = brb[name] || brb[u.username];
    const until = typeof b === "string" ? b : (b && (b.until || b.until_at)) || "";
    let role = "";
    if (name === primary || u.username === primary) role = "основний";
    else if (name === backup || u.username === backup) role = "дублюючий";
    const ab = abs.find((a) => (a.user_name === name || a.user_name === u.username) && a.status === "Approved" && a.start_date <= day && a.end_date >= day);
    const absent = !!ab;
    const sub = [
      role,
      until ? "BRB до " + String(until).slice(11, 16) : "",
      ab ? ((ab.type || "відсутність") + " " + (ab.start_date || "") + "–" + (ab.end_date || "")) : "",
    ].filter(Boolean).join(" · ");
    const faded = absent || until;
    return `<button type="button" class="spec-chip ${faded ? "dim" : ""}" style="--chip:${chipColor(name)}" title="${sub}">
      <span class="spec-name">${name}${absent ? " (відсутній)" : ""}${until ? " · BRB" : ""}</span>
      ${sub ? `<span class="spec-sub">${sub}</span>` : ""}
    </button>`;
  }).join("") + `<button type="button" class="spec-chip action" onclick="openHubIncident()">Звернення</button>`;
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
