// npm run pack: package Research Desk.app, sign it ad hoc (Apple Silicon refuses unsigned code) and install it in
// ~/Applications. Only main.js and preload.js go into the bundle; the page and backend are read from the harness.
const { packager } = require("@electron/packager");
const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

(async () => {
  const [out] = await packager({
    dir: __dirname, out: path.join(__dirname, "dist"), overwrite: true, platform: "darwin", arch: process.arch,
    name: "Research Desk", appBundleId: "dev.sliu.research-desk", appCategoryType: "public.app-category.developer-tools",
    icon: path.join(__dirname, "build", "icon.icns"), asar: true, prune: true,
    ignore: [/^\/dist($|\/)/, /^\/build($|\/)/, /^\/shoot\.js$/, /^\/build\.js$/],
    extendInfo: { NSUserNotificationAlertStyle: "alert", LSApplicationCategoryType: "public.app-category.developer-tools" },
  });
  const built = path.join(out, "Research Desk.app");
  execFileSync("codesign", ["--force", "--deep", "--sign", "-", built], { stdio: "inherit" });
  const dest = path.join(os.homedir(), "Applications", "Research Desk.app");
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.rmSync(dest, { recursive: true, force: true });
  execFileSync("ditto", [built, dest]);
  console.log(`installed ${dest}`);
})().catch((e) => { console.error(e); process.exit(1); });
