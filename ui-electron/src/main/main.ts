import { app, BrowserWindow, dialog } from "electron";
import path from "path";
import { pathToFileURL } from "url";
import { startJavaServer, stopJavaServer } from "./backend";
import { isPortInUse } from "./ports";

let mainWindow: BrowserWindow | null = null;
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
  const inUse = await isPortInUse(18088);
  if (inUse) {
    dialog.showErrorBox("Port in use", "Port 18088 is already in use. Please stop it and try again.");
    app.exit(1);
    return;
  }

  const ok = await startJavaServer();
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
  await stopJavaServer();
  app.exit();
});

app.on("window-all-closed", () => {
  app.quit();
});
