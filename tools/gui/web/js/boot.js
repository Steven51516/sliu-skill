// Startup guard (a classic script, before everything else): if the page's code fails to load or start, for example
// because the backend restarted while the window was loading, say so, log why to the backend, and reload, instead of
// leaving a blank window that looks frozen. main.js sets window.rdReady once the first render is done.
(function () {
  let tries = 0;
  try { tries = +(sessionStorage.getItem("rd.boot") || 0); } catch (_) { /* no storage */ }
  let failed = false;
  function fail(why) {
    if (window.rdReady || failed) return;
    failed = true;
    fetch("/api/token").then((r) => r.json()).then((t) => fetch("/api/client-error", { method: "POST",
      headers: { "Content-Type": "application/json", "X-RG": "1", "X-RG-Token": t.token }, body: JSON.stringify({ error: why, try: tries }) })).catch(() => {});
    const show = () => {
      const box = document.createElement("div");
      box.className = "bootfail";
      box.textContent = tries < 5 ? `Research Desk didn't start (${why}). Retrying…` : `Research Desk didn't start: ${why}. Press ⌘R to try again.`;
      document.body.appendChild(box);
    };
    document.body ? show() : addEventListener("DOMContentLoaded", show);
    if (tries < 5) {
      try { sessionStorage.setItem("rd.boot", tries + 1); } catch (_) { /* no storage */ }
      setTimeout(() => location.reload(), 1500 * (tries + 1));
    }
  }
  addEventListener("error", (e) => {
    const el = e.target;
    if (el && el !== window && !(el.tagName === "SCRIPT" || el.tagName === "LINK")) return;   // a broken image is not a failed start
    fail(e.message || `couldn't load ${el && (el.src || el.href)}`);
  }, true);
  addEventListener("unhandledrejection", (e) => fail(String((e.reason && e.reason.message) || e.reason)));
  setTimeout(() => fail("it didn't finish starting within 20 s"), 20000);
})();
