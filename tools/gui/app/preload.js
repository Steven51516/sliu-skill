// The page's only bridge to the app: dock badge, bringing the window forward, and menu commands.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desk", {
  setBadge: (n) => ipcRenderer.send("badge", n),
  focus: () => ipcRenderer.send("focus"),
  onCommand: (fn) => ipcRenderer.on("cmd", (_e, cmd, arg) => fn(cmd, arg)),
});
