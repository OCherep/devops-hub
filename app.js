async function loadCatalog() {
  const res = await fetch("tools.json?_=" + Date.now());
  if (!res.ok) throw new Error("tools.json " + res.status);
  return res.json();
}

function badgeClass(status) {
  if (status === "active") return "active";
  if (status === "beta") return "beta";
  return "planned";
}

function card(tool) {
  const tags = (tool.tags || [])
    .map((t) => `<span>${escapeHtml(t)}</span>`)
    .join("");

  const links = [];
  if (tool.live) {
    links.push(`<a class="btn primary" href="${escapeAttr(tool.live)}" target="_blank" rel="noopener">Live</a>`);
  }
  if (tool.repo) {
    links.push(`<a class="btn" href="${escapeAttr(tool.repo)}" target="_blank" rel="noopener">Repo</a>`);
  }
  if (tool.docs) {
    links.push(`<a class="btn" href="${escapeAttr(tool.docs)}" target="_blank" rel="noopener">Docs</a>`);
  }
  if (tool.branch) {
    links.push(`<a class="btn" href="${escapeAttr(tool.branch)}" target="_blank" rel="noopener">Branch</a>`);
  }

  return `
    <article class="card ${tool.status === "planned" ? "planned" : ""}">
      <div class="card-top">
        <h3>${escapeHtml(tool.title)}</h3>
        <span class="badge ${badgeClass(tool.status)}">${escapeHtml(tool.status)}</span>
      </div>
      <p>${escapeHtml(tool.blurb || "")}</p>
      <div class="tags">${tags}</div>
      <div class="links">${links.join("")}</div>
    </article>`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/'/g, "&#39;");
}

(async () => {
  const activeEl = document.getElementById("tools-grid");
  const plannedEl = document.getElementById("planned-grid");
  const metaEl = document.getElementById("catalog-meta");
  try {
    const data = await loadCatalog();
    const tools = data.tools || [];
    const active = tools.filter((t) => t.status === "active" || t.status === "beta");
    const planned = tools.filter((t) => t.status === "planned");
    activeEl.innerHTML = active.map(card).join("") || "<p class=\"loading\">Поки немає активних.</p>";
    plannedEl.innerHTML = planned.map(card).join("") || "<p class=\"loading\">Додай planned-записи в tools.json.</p>";
    metaEl.textContent = `catalog ${data.version || ""} · updated ${data.updated || ""}`;
  } catch (e) {
    activeEl.innerHTML = `<p class="loading">Не вдалося завантажити tools.json: ${escapeHtml(e.message)}</p>`;
  }
})();
