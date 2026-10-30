// Test helper: drive the page in an offscreen window and save screenshots.
//   electron shoot.js <spec.json>   spec: {port, width, height, steps: [{hash?, js?, wait?, out?}]}
// Each step optionally navigates, runs JS in the page (its result is printed), waits, then captures.
const { app, BrowserWindow, nativeTheme } = require("electron");
const fs = require("fs");

const spec = JSON.parse(fs.readFileSync(process.argv[process.argv.length - 1], "utf8"));
app.dock && app.dock.hide();
app.whenReady().then(async () => {
  if (spec.dark) nativeTheme.themeSource = "dark";
  const win = new BrowserWindow({ width: spec.width || 1440, height: spec.height || 900, show: false,
    webPreferences: { offscreen: true, plugins: true, preload: spec.preload ? require("path").join(__dirname, "preload.js") : undefined, contextIsolation: true } });
  win.webContents.on("console-message", (e, level, msg) => {    // newer Electron passes one event object
    const lv = e && e.level !== undefined ? e.level : level, m = e && e.message !== undefined ? e.message : msg;
    if (lv === "error" || lv === "warning" || lv >= 2) console.log("[page]", m, e && e.sourceId ? `(${e.sourceId}:${e.lineNumber})` : "");
  });
  await win.loadURL(`http://127.0.0.1:${spec.port}/${spec.steps[0]?.hash || ""}`);
  for (const s of spec.steps) {
    if (s.hash) await win.webContents.executeJavaScript(`location.hash = ${JSON.stringify(s.hash)}`);
    if (s.js) {
      try { const r = await win.webContents.executeJavaScript(`(async () => { ${s.js} })()`); if (r !== undefined) console.log("[js]", JSON.stringify(r).slice(0, 2000)); }
      catch (e) { console.log("[js error]", e.message); }
    }
    await new Promise((r) => setTimeout(r, s.wait ?? 1500));
    if (s.out) { const img = await win.webContents.capturePage(); fs.writeFileSync(s.out, img.toPNG()); console.log("saved", s.out); }
  }
  app.quit();
});
