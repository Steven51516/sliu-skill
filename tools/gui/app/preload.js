// The page's only bridge to the app: dock badge, menu-bar attention list, open at login, window focus, show herdr,
// the path of a file dropped on the window, menu commands.
const { contextBridge, ipcRenderer, webUtils } = require("electron");

contextBridge.exposeInMainWorld("desk", {
  setBadge: (n) => ipcRenderer.send("badge", n),
  focus: () => ipcRenderer.send("focus"),
  onCommand: (fn) => ipcRenderer.on("cmd", (_e, cmd, arg) => fn(cmd, arg)),
  attention: (items) => ipcRenderer.send("attention", items),
  loginItem: (on) => ipcRenderer.invoke("login-item", on),
  showHerdr: () => ipcRenderer.send("show-herdr"),
  pathForFile: (file) => { try { return webUtils.getPathForFile(file) || ""; } catch (_) { return ""; } },
});
