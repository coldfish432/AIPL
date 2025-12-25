import { app, dialog } from "electron";
import { spawn } from "child_process";
import fs from "fs";
import path from "path";
import http from "http";
import kill from "tree-kill";
import { getLogPath, getResourcesRoot } from "./paths";

let javaProcess: import("child_process").ChildProcess | null = null;

function resolveJavaExecutable(resourcesRoot: string): string {
  const bundled = path.join(resourcesRoot, "jre", "bin", "java.exe");
  if (fs.existsSync(bundled)) {
    return bundled;
  }
  return "java";
}

function resolveEngineRoot(resourcesRoot: string): string {
  if (app.isPackaged) {
    return resourcesRoot;
  }
  return path.resolve(app.getAppPath(), "..");
}

function checkHealth(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get("http://127.0.0.1:18088/health", (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForHealth(timeoutMs: number): Promise<boolean> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const ok = await checkHealth();
    if (ok) return true;
    await new Promise((r) => setTimeout(r, 1000));
  }
  return false;
}

export async function startJavaServer(): Promise<boolean> {
  const resourcesRoot = getResourcesRoot();
  const jarPath = path.join(resourcesRoot, "server.jar");
  if (!fs.existsSync(jarPath)) {
    dialog.showErrorBox("Missing server.jar", "Expected server.jar at: " + jarPath);
    return false;
  }

  const javaExe = resolveJavaExecutable(resourcesRoot);
  const engineRoot = resolveEngineRoot(resourcesRoot);
  const logPath = getLogPath();
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  const logFd = fs.openSync(logPath, "a");

  javaProcess = spawn(javaExe, ["-jar", jarPath, "--server.port=18088", `--app.engineRoot=${engineRoot}`], {
    cwd: resourcesRoot,
    stdio: ["ignore", logFd, logFd],
    windowsHide: true
  });

  const healthy = await waitForHealth(30000);
  if (!healthy) {
    dialog.showErrorBox("Server start failed", "Java server did not become healthy within 30 seconds.");
    await stopJavaServer();
    return false;
  }
  return true;
}

export async function stopJavaServer(): Promise<void> {
  if (!javaProcess || !javaProcess.pid) {
    javaProcess = null;
    return;
  }
  const pid = javaProcess.pid;
  javaProcess = null;
  await new Promise<void>((resolve) => {
    kill(pid, "SIGTERM", () => resolve());
  });
}
