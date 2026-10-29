// Research Desk: the macOS app shell. Starts (or reuses) the Python backend on 127.0.0.1 and shows its page in a native
// window with a menu, dock badge and notifications. The page and backend live in the harness (tools/gui), so editing
// them needs no rebuild; only this file and preload.js are packaged.
const { app, BrowserWindow, Menu, Tray, nativeImage, shell, ipcMain, dialog } = require("electron");
const { spawn, execFileSync } = require("child_process");
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");

const PORT = Number(process.env.RD_PORT || 8765);
const URL = `http://127.0.0.1:${PORT}/`;
const LOG_DIR = path.join(os.homedir(), "Library", "Logs", "Research Desk");
const STATE = () => path.join(app.getPath("userData"), "window.json");
let win = null, backend = null, owned = false, restarts = 0, quitting = false, tray = null, attention = [];

function serverPath() {
  const cands = [process.env.RD_SERVER, path.join(os.homedir(), "research-harness", "tools", "gui", "server.py"), path.join(__dirname, "..", "server.py")];
  return cands.find((p) => p && fs.existsSync(p));
}

function loginPath() {
  // apps started from the Dock get a bare PATH; ask the login shell for the user's (herdr, ssh config tools, python)
  const base = ["/opt/homebrew/bin", "/usr/local/bin", path.join(os.homedir(), ".local", "bin"), "/usr/bin", "/bin", "/usr/sbin", "/sbin"];
  try {
    const out = execFileSync("/bin/zsh", ["-ilc", 'printf "__RD__%s__RD__" "$PATH"'], { timeout: 6000, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
    const m = out.match(/__RD__(.*)__RD__/);
    if (m) return [...new Set([...m[1].split(":"), ...base])].join(":");
  } catch (_) { /* fall back */ }
  return base.join(":");
}

function python(env) {
  for (const p of ["/opt/homebrew/bin/python3", "/usr/local/bin/python3", "python3"]) {
    try { execFileSync(p, ["-c", "import tomllib"], { env, timeout: 5000, stdio: "ignore" }); return p; } catch (_) { /* next */ }
  }
  return null;
}

function ping() {
  return new Promise((resolve) => {
    const req = http.get(URL + "api/ping", { timeout: 1500 }, (res) => {
      let body = "";
      res.on("data", (c) => (body += c));
      res.on("end", () => { try { resolve(JSON.parse(body).app === "research-gui"); } catch (_) { resolve(false); } });
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

function herdrJSON(env, args) {
  return JSON.parse(execFileSync("herdr", args, { env, timeout: 10000, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] })).result;
}

function startInHerdr(env, server) {
  // The backend reads project folders under ~/Documents. Started from this app, macOS would ask for Documents access
  // (again after every rebuild of an ad hoc signed app). Started in a herdr pane it inherits the terminal's access,
  // and it keeps running when the app quits.
  try {
    const snap = herdrJSON(env, ["api", "snapshot"]).snapshot;
    let ws = snap.workspaces.find((w) => w.label === "research-desk");
    let pane;
    if (ws) pane = herdrJSON(env, ["tab", "create", "--workspace", ws.workspace_id, "--cwd", os.homedir(), "--label", "backend", "--no-focus"]).root_pane.pane_id;
    else {
      const r = herdrJSON(env, ["workspace", "create", "--cwd", os.homedir(), "--label", "research-desk", "--no-focus"]);
      pane = r.root_pane.pane_id;
      execFileSync("herdr", ["tab", "rename", r.tab.tab_id, "backend"], { env, timeout: 10000, stdio: "ignore" });
    }
    execFileSync("herdr", ["pane", "run", pane, `exec ${JSON.stringify(python(env) || "python3")} ${JSON.stringify(server)} --serve --port ${PORT}`], { env, timeout: 10000, stdio: "ignore" });
    return true;
  } catch (_) { return false; }
}

async function waitPing(n) {
  for (let i = 0; i < n; i++) {
    if (await ping()) return true;
    await new Promise((r) => setTimeout(r, 150));
  }
  return false;
}

async function ensureBackend() {
  if (await ping()) return true;                         // already running (e.g. started with research-gui --serve)
  const server = serverPath();
  if (!server) throw new Error("Can't find research-harness/tools/gui/server.py (expected under ~/research-harness).");
  const env = { ...process.env, PATH: loginPath() };
  if (startInHerdr(env, server) && await waitPing(80)) return true;
  const py = python(env);
  if (!py) throw new Error("No python3 with tomllib (Python 3.11+) found. Install one with Homebrew: brew install python");
  fs.mkdirSync(LOG_DIR, { recursive: true });
  const log = fs.openSync(path.join(LOG_DIR, "backend.log"), "a");
  backend = spawn(py, [server, "--serve", "--port", String(PORT)], { env, cwd: os.homedir(), stdio: ["ignore", log, log] });
  owned = true;
  backend.on("exit", (code) => {
    backend = null;
    if (quitting) return;
    if (restarts++ < 5) setTimeout(() => ensureBackend().then(() => win && win.reload()).catch(() => {}), 1000);
    else dialog.showErrorBox("Research Desk", `The backend keeps stopping (exit ${code}). See ${path.join(LOG_DIR, "backend.log")}.`);
  });
  if (await waitPing(200)) return true;
  throw new Error(`The backend did not start. If macOS asked for access to your Documents folder, allow it and reopen the app. Log: ${path.join(LOG_DIR, "backend.log")}`);
}

function loadBounds() { try { return JSON.parse(fs.readFileSync(STATE(), "utf8")); } catch (_) { return { width: 1440, height: 900 }; } }
function saveBounds() { try { if (win && !win.isMinimized()) fs.writeFileSync(STATE(), JSON.stringify(win.getBounds())); } catch (_) { /* ignore */ } }

function createWindow() {
  win = new BrowserWindow({
    ...loadBounds(), minWidth: 980, minHeight: 620, show: false, title: "Research Desk",
    titleBarStyle: "hiddenInset", trafficLightPosition: { x: 16, y: 16 },
    vibrancy: "sidebar", visualEffectState: "followWindow", backgroundColor: "#00000000",
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, sandbox: true, spellcheck: true },
  });
  win.once("ready-to-show", () => win.show());
  win.on("close", saveBounds);
  win.on("closed", () => { win = null; });
  // the window only ever shows the app page; web links open in the browser, nothing else opens at all
  const external = (url) => /^https?:\/\//i.test(url) && !/^https?:\/\/(127\.0\.0\.1|localhost)(:|\/|$)/i.test(url);
  win.webContents.setWindowOpenHandler(({ url }) => { if (external(url)) shell.openExternal(url); return { action: "deny" }; });
  win.webContents.on("will-navigate", (e, url) => {
    if (url === URL || url.startsWith(URL + "#")) return;
    e.preventDefault();
    if (external(url)) shell.openExternal(url);
  });
  win.webContents.session.setPermissionRequestHandler((_wc, permission, done) => done(permission === "notifications"));
  win.webContents.on("render-process-gone", () => win && win.reload());
  win.loadURL(URL);
}

function errorWindow(msg) {
  const w = new BrowserWindow({ width: 640, height: 300, title: "Research Desk" });
  w.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(`<body style="font:14px -apple-system;padding:30px;color:#333">
    <h2 style="margin-top:0">Research Desk could not start</h2><p>${msg.replace(/</g, "&lt;")}</p></body>`));
}

const send = (cmd, arg) => win && win.webContents.send("cmd", cmd, arg);
function menu() {
  const item = (label, accelerator, cmd, arg) => ({ label, accelerator, click: () => { if (!win) createWindow(); send(cmd, arg); } });
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: app.name, submenu: [{ role: "about" }, { type: "separator" }, item("Settings…", "Cmd+,", "settings"), { type: "separator" },
      { role: "hide" }, { role: "hideOthers" }, { role: "unhide" }, { type: "separator" }, { role: "quit" }] },
    { label: "File", submenu: [item("New Session…", "Cmd+N", "newSession"), { type: "separator" }, { role: "close" }] },
    { role: "editMenu" },
    { label: "View", submenu: [item("Command Palette…", "Cmd+K", "palette"), item("Toggle Chat", "Cmd+J", "chat"), item("Toggle Terminals", "Ctrl+`", "dock"),
      { type: "separator" }, item("Inbox", "Cmd+I", "inbox"), item("GPUs", "Cmd+G", "gpus"), item("Keyboard Shortcuts", "Cmd+/", "shortcuts"),
      { type: "separator" }, item("Refresh Data", "Cmd+Shift+R", "refresh"), { role: "reload" }, { role: "toggleDevTools" },
      { type: "separator" }, { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" }, { type: "separator" }, { role: "togglefullscreen" }] },
    { label: "Go", submenu: [1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => item(`Project ${i}`, `Cmd+${i}`, "project", i - 1)) },
    { role: "windowMenu" },
    { role: "help", submenu: [{ label: "Backend Log", click: () => shell.openPath(path.join(LOG_DIR, "backend.log")) },
      { label: "Projects File", click: () => shell.openPath(path.join(os.homedir(), ".config", "research-gui", "projects.toml")) }] },
  ]));
}

ipcMain.on("badge", (_e, n) => app.dock && app.dock.setBadge(n ? String(n) : ""));
ipcMain.on("attention", (_e, items) => { attention = Array.isArray(items) ? items.slice(0, 12) : []; updateTray(); });
ipcMain.handle("login-item", (_e, on) => {
  if (typeof on === "boolean") app.setLoginItemSettings({ openAtLogin: on });
  return app.getLoginItemSettings().openAtLogin;
});

function show() { if (!win) createWindow(); else { if (win.isMinimized()) win.restore(); win.show(); win.focus(); } }
function updateTray() {
  // the menu-bar icon: how many things wait on you, and a menu that jumps straight to each
  if (!tray) {
    tray = new Tray(nativeImage.createFromPath(path.join(__dirname, "assets", "trayTemplate.png")));
    tray.setToolTip("Research Desk");
  }
  tray.setTitle(attention.length ? ` ${attention.length}` : "");
  tray.setContextMenu(Menu.buildFromTemplate([
    ...(attention.length ? attention.map((a) => ({ label: a.label.slice(0, 70), click: () => { show(); send(a.cmd, a.arg); } })) : [{ label: "Nothing waits on you", enabled: false }]),
    { type: "separator" }, { label: "Open Research Desk", click: show }, { label: "Inbox", click: () => { show(); send("inbox"); } },
    { type: "separator" }, { label: "Quit", click: () => app.quit() },
  ]));
}
ipcMain.on("focus", () => { if (win) { if (win.isMinimized()) win.restore(); win.show(); win.focus(); } });

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on("second-instance", () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
  app.whenReady().then(async () => {
    app.setAboutPanelOptions({ applicationName: "Research Desk", applicationVersion: app.getVersion(), credits: "A desk over the research harness, with herdr as the runtime." });
    menu();
    updateTray();
    try { await ensureBackend(); createWindow(); } catch (e) { errorWindow(e.message); }
    let misses = 0;                                      // watchdog: bring the backend back if it stops answering
    setInterval(async () => {
      if (quitting || backend) return;
      misses = (await ping()) ? 0 : misses + 1;
      if (misses === 2) ensureBackend().then(() => { misses = 0; if (win) win.reload(); }).catch(() => {});
    }, 10000);
  });
  app.on("activate", () => { if (!win && BrowserWindow.getAllWindows().length === 0) createWindow(); });
  app.on("before-quit", () => { quitting = true; saveBounds(); if (owned && backend) backend.kill("SIGTERM"); });
}
