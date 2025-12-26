import { app, BrowserWindow } from "electron";
import path from "path";
import { pathToFileURL } from "url";
import { ServerManager } from "./server";

let mainWindow: BrowserWindow | null = null;
const serverManager = new ServerManager();
let stopping = false;

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800
  });

  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) {
    await mainWindow.loadURL(devUrl);
  } else {
    const indexPath = path.join(app.getAppPath(), "dist/renderer/index.html");
    await mainWindow.loadURL(pathToFileURL(indexPath).toString());
  }
}

app.whenReady().then(async () => {
  const ok = await serverManager.start();
  if (!ok) {
    app.exit(1);
    return;
  }

  await createWindow();
});

app.on("before-quit", async (event) => {
  if (stopping) return;
  stopping = true;
  event.preventDefault();
  await serverManager.stop();
  app.exit();
});

app.on("window-all-closed", () => {
  app.quit();
});
