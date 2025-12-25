import { app } from "electron";
import path from "path";

export function getResourcesRoot(): string {
  if (app.isPackaged) {
    return process.resourcesPath;
  }
  return path.join(app.getAppPath(), "resources");
}

export function getLogPath(): string {
  return path.join(app.getPath("appData"), "AIPL", "logs", "server.log");
}
