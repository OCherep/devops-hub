/* Shared Hub/OnCall theme. Keys: ops_theme + oncall_theme (keep in sync). */
(function () {
  var KEYS = ["ops_theme", "oncall_theme"];
  function read() {
    try {
      return localStorage.getItem("ops_theme") || localStorage.getItem("oncall_theme") || "system";
    } catch (e) { return "system"; }
  }
  function resolve(mode) {
    if (mode === "light" || mode === "dark") return mode;
    try {
      return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    } catch (e) { return "dark"; }
  }
  function apply(mode) {
    var resolved = resolve(mode || read());
    document.documentElement.setAttribute("data-theme", resolved);
    document.documentElement.setAttribute("data-theme-mode", mode || read());
    try {
      KEYS.forEach(function (k) { localStorage.setItem(k, mode || read()); });
    } catch (e) {}
    document.querySelectorAll("[data-theme-btn]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-theme-btn") === (mode || read()) ? "true" : "false");
    });
  }
  window.opsSetTheme = function (mode) { apply(mode); };
  window.opsThemeBoot = function () { apply(read()); };
  apply(read());
  try {
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      if (read() === "system") apply("system");
    });
  } catch (e) {}
})();
