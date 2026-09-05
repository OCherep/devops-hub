/* Shared Hub chrome: menu, session, incident/task/absence, specialist modal, ACL */
(function (w) {
  const BASES = ["/oncall-api", "https://s.ks.tv:85"];
  const SERVICE = document.documentElement.getAttribute("data-hub-service") || "hub";
  function token() { try { return localStorage.getItem("oncall_session") || ""; } catch (e) { return ""; } }
  function setToken(t) { try { t ? localStorage.setItem("oncall_session", t) : localStorage.removeItem("oncall_session"); } catch (e) {} }

  async function ocFetch(path, opts) {
    opts = opts || {};
    const headers = Object.assign({ Accept: "application/json" }, opts.headers || {});
    const tok = token();
    if (tok) headers.Authorization = "Bearer " + tok;
    let last = "offline";
    for (const base of BASES) {
      try {
        const r = await fetch(base + path, Object.assign({}, opts, { headers, credentials: "include" }));
        const ct = r.headers.get("content-type") || "";
        if (r.status === 204) return {};
        if (!ct.includes("json")) { last = path + " not-json"; continue; }
        const body = await r.json();
        if (!r.ok) { last = body.error || (path + " " + r.status); if (r.status === 405) continue; throw new Error(last); }
        return body;
      } catch (e) { last = e.message || String(e); }
    }
    throw new Error(last);
  }

  function todayISO() {
    const d = new Date();
    const z = (n) => String(n).padStart(2, "0");
    return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate());
  }
  function chipColor(name) {
    let h = 0; String(name || "").split("").forEach((c) => { h = (h * 33 + c.charCodeAt(0)) % 360; });
    return "hsl(" + h + " 55% 42%)";
  }
  function can(action) {
    const p = w.HubChrome.profile;
    if (!p) return action === "incident"; // guest
    if (p.role === "admin") return true;
    const acl = p.acl || {};
    if (action === "task") return !!acl.task || p.role === "admin";
    if (action === "absence") return true;
    if (action === "incident") return true;
    if (action === "service:" + SERVICE) return true;
    return !!acl[action];
  }

  function ensureModals() {
    if (document.getElementById("hc-login")) return;
    const wrap = document.createElement("div");
    wrap.innerHTML = `
<div id="hc-login" class="hub-modal"><div class="mc">
  <h3>Вхід OnCall</h3>
  <div class="fg"><label>Логін</label><input id="hc-lu" autocomplete="username"></div>
  <div class="fg"><label>Пароль</label><input id="hc-lp" type="password" autocomplete="current-password"></div>
  <p id="hc-lstatus" class="muted"></p>
  <div class="row"><button class="btn primary" type="button" id="hc-ldo">Увійти</button>
  <button class="btn" type="button" data-close="hc-login">Скасувати</button></div>
</div></div>
<div id="hc-inc" class="hub-modal"><div class="mc">
  <h3>Звернення</h3>
  <div class="fg"><label>Slack * (ID U… або @username)</label>
    <div style="display:flex;gap:6px"><input id="hc-islack" placeholder="@username або U0123">
    <button class="btn" type="button" id="hc-islack-btn">Знайти</button></div>
    <div id="hc-islack-st" style="font-size:12px;opacity:.8"></div></div>
  <div class="fg"><label>Ваше імʼя</label><input id="hc-iname"></div>
  <div class="fg"><label>Email *</label><input id="hc-iemail" type="email"></div>
  <div class="fg"><label>Кому</label><select id="hc-idir"><option value="__team__">До команди (черга)</option></select>
    <div style="font-size:11px;opacity:.75">«До команди» — розподілить диспетчер / чергові за on-grid. Не авто-призначення.</div></div>
  <div class="fg"><label>Тип</label><select id="hc-itype"><option>Звернення</option><option>Інцидент</option><option>Консультація</option></select></div>
  <div class="fg"><label>Пріоритет</label><select id="hc-iprio"><option>Звичайний</option><option>Підвищений</option><option>Високий</option><option>Критичний</option><option>Терміновий</option></select></div>
  <div class="fg"><label>Тривалість (хв)</label><input id="hc-imins" type="number" value="15"></div>
  <div class="fg"><label>Опис *</label><textarea id="hc-idesc" rows="4"></textarea></div>
  <p id="hc-istatus"></p>
  <div class="row"><button class="btn primary" type="button" id="hc-ido">Зафіксувати</button>
  <button class="btn" type="button" data-close="hc-inc">Скасувати</button></div>
</div></div>
<div id="hc-task" class="hub-modal"><div class="mc">
  <h3>Задача з дейлі</h3>
  <div class="fg"><label>Виконавець</label><select id="hc-tuser"></select></div>
  <div class="fg"><label>Дата</label><input type="date" id="hc-td"></div>
  <div class="fg"><label>Due</label><input type="date" id="hc-tdue"></div>
  <div class="fg"><label>План (хв)</label><input type="number" id="hc-tmins" value="30"></div>
  <div class="fg"><label>Пріоритет</label><select id="hc-tprio"><option>Базова</option><option>Надкритична</option><option>Термінова</option><option>Техборг</option><option>У шухляду</option></select></div>
  <div class="fg"><label>Опис</label><textarea id="hc-tdesc" rows="3"></textarea></div>
  <p id="hc-tstatus"></p>
  <div class="row"><button class="btn primary" type="button" id="hc-tdo">Створити</button>
  <button class="btn" type="button" data-close="hc-task">Скасувати</button></div>
</div></div>
<div id="hc-abs" class="hub-modal"><div class="mc">
  <h3>Відсутність</h3>
  <div class="fg"><label>Тип</label><select id="hc-atype"><option>Відпустка</option><option>Лікарняний</option><option>Day-off</option></select></div>
  <div class="fg"><label>З</label><input type="date" id="hc-as"></div>
  <div class="fg"><label>По</label><input type="date" id="hc-ae"></div>
  <p id="hc-astatus"></p>
  <div class="row"><button class="btn primary" type="button" id="hc-ado">Надіслати</button>
  <button class="btn" type="button" data-close="hc-abs">Скасувати</button></div>
</div></div>
<div id="hc-person" class="hub-modal"><div class="mc" id="hc-person-body"></div></div>
<div id="hc-profile" class="hub-modal"><div class="mc" id="hc-profile-body"></div></div>`;
    document.body.appendChild(wrap);
    wrap.querySelectorAll("[data-close]").forEach((b) => b.onclick = () => close(b.getAttribute("data-close")));
    document.getElementById("hc-ldo").onclick = doLogin;
    document.getElementById("hc-islack-btn").onclick = lookupSlack;
    document.getElementById("hc-ido").onclick = submitInc;
    document.getElementById("hc-tdo").onclick = submitTask;
    document.getElementById("hc-ado").onclick = submitAbs;
  }
  function open(id) { ensureModals(); const el = document.getElementById(id); if (el) el.classList.add("open"); }
  function close(id) { const el = document.getElementById(id); if (el) el.classList.remove("open"); }

  async function doLogin() {
    const st = document.getElementById("hc-lstatus");
    try {
      const d = await ocFetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: document.getElementById("hc-lu").value, password: document.getElementById("hc-lp").value }) });
      if (d.session_token) setToken(d.session_token);
      close("hc-login");
      await refresh();
    } catch (e) { st.textContent = e.message; }
  }
  async function lookupSlack() {
    const q = document.getElementById("hc-islack").value;
    const st = document.getElementById("hc-islack-st");
    try {
      const d = await ocFetch("/api/slack/lookup?q=" + encodeURIComponent(q));
      if (d.name) document.getElementById("hc-iname").value = d.name;
      if (d.email) document.getElementById("hc-iemail").value = d.email;
      st.textContent = d.name ? ("Slack: " + d.name) : "не знайдено";
    } catch (e) { st.textContent = e.message; }
  }
  async function submitInc() {
    const members = (w.HubChrome.data && w.HubChrome.data.team_members) || [];
    const dir = document.getElementById("hc-idir").value;
    const payload = {
      reporter_name: document.getElementById("hc-iname").value,
      reporter_email: document.getElementById("hc-iemail").value,
      reporter_slack: document.getElementById("hc-islack").value,
      description: document.getElementById("hc-idesc").value,
      priority: document.getElementById("hc-iprio").value,
      type: document.getElementById("hc-itype").value,
      duration_minutes: Number(document.getElementById("hc-imins").value || 15),
      source: "hub-guest", date: todayISO(),
      directed_to: dir === "__team__" ? "" : dir,
      directed_scope: dir === "__team__" ? "team" : "user"
    };
    const st = document.getElementById("hc-istatus");
    if (!payload.reporter_name || !payload.reporter_email || !payload.description) { st.textContent = "Імʼя, email, опис обовʼязкові"; return; }
    try { await ocFetch("/api/incidents", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); st.textContent = "Створено"; setTimeout(() => close("hc-inc"), 700); }
    catch (e) { st.textContent = e.message; }
  }
  async function submitTask() {
    const st = document.getElementById("hc-tstatus");
    if (!can("task")) { st.textContent = "Немає права створювати задачі"; return; }
    const body = {
      user_name: document.getElementById("hc-tuser").value,
      date: document.getElementById("hc-td").value || todayISO(),
      due_date: document.getElementById("hc-tdue").value || "",
      task_description: document.getElementById("hc-tdesc").value,
      priority: document.getElementById("hc-tprio").value,
      total_minutes: Number(document.getElementById("hc-tmins").value || 0),
      status: "Нерозподілена"
    };
    try { await ocFetch("/api/daily-tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); st.textContent = "Створено"; setTimeout(() => close("hc-task"), 700); }
    catch (e) { st.textContent = e.message; }
  }
  async function submitAbs() {
    const p = w.HubChrome.profile;
    const st = document.getElementById("hc-astatus");
    if (!p) { st.textContent = "Увійдіть"; return; }
    try {
      await ocFetch("/api/request-absence", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_name: p.name, type: document.getElementById("hc-atype").value,
          start_date: document.getElementById("hc-as").value, end_date: document.getElementById("hc-ae").value }) });
      st.textContent = "Надіслано"; setTimeout(() => close("hc-abs"), 700);
    } catch (e) { st.textContent = e.message; }
  }

  function showPerson(name) {
    const data = w.HubChrome.data || {};
    const u = (data.team_members || []).find((x) => x.name === name || x.username === name) || { name };
    const day = todayISO();
    let shifts = data.shifts || {};
    if (Array.isArray(shifts)) { const m = {}; shifts.forEach((s) => { if (s.date) m[s.date] = s; }); shifts = m; }
    const sh = shifts[day] || {};
    const brb = (data.brb || {})[name];
    const abs = (data.absences || []).filter((a) => (a.user_name === name) && (a.start_date || "") <= day && (a.end_date || "") >= day);
    const role = (name === sh.primary_user) ? "основний черговий" : (name === sh.backup_user) ? "дублюючий черговий" : "фахівець";
    document.getElementById("hc-person-body").innerHTML = `
      <h3>${name}</h3>
      <p>${role}${u.team_role ? " · " + u.team_role : ""}${u.role ? " · " + u.role : ""}</p>
      <p>Email: ${u.email || "—"}<br>Slack: ${u.slack_id || "—"}<br>Тел: ${u.phone || "—"}</p>
      <p>On-call: ${u.is_oncall ? "так" : "ні"} · roster: ${u.show_in_roster !== false ? "так" : "ні"}</p>
      <p>BRB: ${brb ? JSON.stringify(brb) : "немає"}</p>
      <p>Відсутності сьогодні: ${abs.length ? abs.map((a) => (a.type || "") + " " + a.start_date + "–" + a.end_date).join("; ") : "немає"}</p>
      <button class="btn" type="button" data-close="hc-person">Закрити</button>`;
    document.getElementById("hc-person-body").querySelector("[data-close]").onclick = () => close("hc-person");
    open("hc-person");
  }

  function fillSelects() {
    const members = (w.HubChrome.data && w.HubChrome.data.team_members) || [];
    const dir = document.getElementById("hc-idir");
    const tu = document.getElementById("hc-tuser");
    if (dir) {
      dir.innerHTML = '<option value="__team__">До команди (черга)</option>' +
        members.map((m) => `<option value="${(m.name || "").replace(/"/g, "&quot;")}">${m.name}</option>`).join("");
    }
    if (tu) tu.innerHTML = members.map((m) => `<option>${m.name}</option>`).join("");
    const td = document.getElementById("hc-td"); if (td && !td.value) td.value = todayISO();
  }

  function renderRoster(el, data, day) {
    if (!el) return;
    const users = (data.team_members || []).filter((u) => u && u.show_in_roster !== false && u.show_in_roster !== 0);
    let shifts = data.shifts || {};
    if (Array.isArray(shifts)) { const m = {}; shifts.forEach((s) => { if (s.date) m[s.date] = s; }); shifts = m; }
    const sh = shifts[day] || {};
    const abs = data.absences || [];
    const brb = data.brb || {};
    el.innerHTML = users.map((u) => {
      const name = u.name || u.username || "";
      const until = typeof brb[name] === "string" ? brb[name] : (brb[name] && (brb[name].until || brb[name].until_at)) || "";
      const role = name === sh.primary_user ? "основний" : name === sh.backup_user ? "дублюючий" : "";
      const ab = abs.find((a) => a.user_name === name && (a.start_date || "") <= day && (a.end_date || "") >= day);
      const sub = [role, until ? "BRB" : "", ab ? ((ab.type || "відсутність") + " " + (ab.start_date || "") + "–" + (ab.end_date || "")) : ""].filter(Boolean).join(" · ");
      return `<button type="button" class="spec-chip ${ab || until ? "dim" : ""}" style="--chip:${chipColor(name)}" data-person="${name}">
        <span class="spec-name">${name}${ab ? " (відсутній)" : ""}</span>
        ${sub ? `<span class="spec-sub">${sub}</span>` : ""}</button>`;
    }).join("") + `<button type="button" class="spec-chip action" id="hc-open-inc">Звернення</button>`;
    el.querySelectorAll("[data-person]").forEach((b) => b.onclick = () => showPerson(b.getAttribute("data-person")));
    const oi = document.getElementById("hc-open-inc"); if (oi) oi.onclick = () => { fillSelects(); open("hc-inc"); };
  }

  async function loadToolsMenu() {
    const menu = document.getElementById("hub-tools-menu");
    if (!menu) return;
    try {
      const r = await fetch("/tools.json");
      const d = await r.json();
      menu.innerHTML = (d.tools || []).filter((t) => t.live && t.id !== SERVICE)
        .map((t) => `<a href="${t.live}">${t.title}</a>`).join("") || "<span>немає</span>";
    } catch (e) {}
  }

  function bindHeader() {
    const login = document.getElementById("hub-login-btn");
    if (login) login.onclick = () => {
      if (login.dataset.mode === "out") { ocFetch("/api/logout", { method: "POST" }).finally(() => { setToken(""); refresh(); }); return; }
      open("hc-login");
    };
    const who = document.getElementById("hub-who");
    if (who) who.onclick = () => {
      const p = w.HubChrome.profile;
      const body = document.getElementById("hc-profile-body");
      if (!p) { open("hc-login"); return; }
      body.innerHTML = `<h3>Профіль</h3><p>${p.name} · ${p.role}</p>
        <p>Сервіси: ${SERVICE} (поточний). Admin бачить усі.</p>
        <div class="row">
          <button class="btn" type="button" id="hc-p-inc">Звернення</button>
          ${can("task") ? '<button class="btn" type="button" id="hc-p-task">Задача</button>' : ""}
          <button class="btn" type="button" id="hc-p-abs">Відсутність</button>
          <button class="btn" type="button" data-close="hc-profile">Закрити</button>
        </div>`;
      const pi = document.getElementById("hc-p-inc"); if (pi) pi.onclick = () => { close("hc-profile"); fillSelects(); open("hc-inc"); };
      const pt = document.getElementById("hc-p-task"); if (pt) pt.onclick = () => { close("hc-profile"); fillSelects(); open("hc-task"); };
      const pa = document.getElementById("hc-p-abs"); if (pa) pa.onclick = () => { close("hc-profile"); open("hc-abs"); };
      body.querySelector("[data-close]").onclick = () => close("hc-profile");
      open("hc-profile");
    };
    const tb = document.querySelector("[onclick*='hub-tools-menu']");
    if (tb) tb.onclick = () => document.getElementById("hub-tools-menu")?.classList.toggle("open");
  }

  async function refresh() {
    ensureModals();
    bindHeader();
    loadToolsMenu();
    let grid = {}, data = {}, me = null;
    try { grid = await ocFetch("/api/on-grid"); } catch (e) {}
    try { data = await ocFetch("/api/data?year=" + todayISO().slice(0, 4) + "&month=" + Number(todayISO().slice(5, 7))); }
    catch (e) { data = { _err: e.message }; }
    try { me = await ocFetch("/api/session/me"); } catch (e) { me = null; }
    w.HubChrome.data = data;
    w.HubChrome.profile = me && (me.name || me.username) ? { name: me.name || me.username, role: me.role || "user", username: me.username, acl: { task: me.role === "admin" } } : null;
    const snap = grid.on_grid !== undefined ? grid : (data.on_grid || {});
    const on = snap.on_grid === true || snap._on_grid_now === "1";
    const dateEl = document.getElementById("hub-date-chip");
    if (dateEl) dateEl.innerHTML = `<span class="dc-date">${todayISO()}</span><span class="dc-mode">${on ? "робочий час" : "неробочий час"}</span>`;
    const loginBtn = document.getElementById("hub-login-btn");
    const whoEl = document.getElementById("hub-who");
    if (w.HubChrome.profile) {
      if (whoEl) whoEl.textContent = w.HubChrome.profile.name;
      if (loginBtn) { loginBtn.textContent = "Вийти"; loginBtn.dataset.mode = "out"; }
    } else {
      if (whoEl) whoEl.textContent = "";
      if (loginBtn) { loginBtn.textContent = "Увійти"; loginBtn.dataset.mode = "in"; }
    }
    renderRoster(document.getElementById("hub-roster"), data, todayISO());
    fillSelects();
  }

  w.HubChrome = { refresh, open, close, can, ocFetch, showPerson, profile: null, data: {} };
  document.addEventListener("DOMContentLoaded", refresh);
})(window);
