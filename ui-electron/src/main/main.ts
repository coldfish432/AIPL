import { app, BrowserWindow, dialog, ipcMain } from "electron";
import fs from "fs";
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
    ,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  const devUrl = process.env.VITE_DEV_SERVER_URL;
  if (devUrl) {
    await mainWindow.loadURL(devUrl);
  } else {
    const indexPath = path.join(app.getAppPath(), "dist/renderer/index.html");
    await mainWindow.loadURL(pathToFileURL(indexPath).toString());
  }
}

ipcMain.handle("aipl-pick-workspace", async () => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, { properties: ["openDirectory"] });
  if (result.canceled || !result.filePaths.length) {
    return null;
  }
  return result.filePaths[0];
});

ipcMain.handle("aipl-save-json", async (_event, payload: { suggestedName?: string; data?: string }) => {
  if (!mainWindow) return null;
  const result = await dialog.showSaveDialog(mainWindow, {
    defaultPath: payload.suggestedName || "export.json",
    filters: [{ name: "JSON", extensions: ["json"] }]
  });
  if (result.canceled || !result.filePath) return null;
  const content = payload.data ?? "";
  fs.writeFileSync(result.filePath, content, "utf-8");
  return result.filePath;
});

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
