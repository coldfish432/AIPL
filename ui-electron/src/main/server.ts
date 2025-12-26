import { app, dialog } from "electron";
import { spawn } from "child_process";
import fs from "fs";
import path from "path";
import http from "http";
import kill from "tree-kill";
import net from "net";
import { AppConfig, getBaseUrl } from "./config";

let javaProcess: import("child_process").ChildProcess | null = null;

function getResourcesRoot(): string {
  if (app.isPackaged) {
    return process.resourcesPath;
  }
  return path.join(app.getAppPath(), "resources");
}

function getLogPath(): string {
  return path.join(app.getPath("appData"), "AIPL", "logs", "server.log");
}

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
    const req = http.get(`${getBaseUrl()}/health`, (res) => {
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

function isPortInUse(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const tester = net
      .createServer()
      .once("error", (err: NodeJS.ErrnoException) => {
        resolve(err.code === "EADDRINUSE");
      })
      .once("listening", () => {
        tester.close(() => resolve(false));
      })
      .listen(port, AppConfig.javaHost);
  });
}

export class ServerManager {
  private stopping = false;

  async start(): Promise<boolean> {
    const inUse = await isPortInUse(AppConfig.javaPort);
    if (inUse) {
      dialog.showErrorBox(
        "Port in use",
        `Port ${AppConfig.javaPort} is already in use. Please stop it and try again.`
      );
      return false;
    }

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

    javaProcess = spawn(javaExe, ["-jar", jarPath, `--server.port=${AppConfig.javaPort}`, `--app.engineRoot=${engineRoot}`], {
      cwd: resourcesRoot,
      stdio: ["ignore", logFd, logFd],
      windowsHide: true,
    });

    const healthy = await waitForHealth(AppConfig.startupTimeoutMs);
    if (!healthy) {
      dialog.showErrorBox("Server start failed", "Java server did not become healthy within the timeout.");
      await this.stop();
      return false;
    }
    return true;
  }

  async stop(): Promise<void> {
    if (this.stopping) return;
    this.stopping = true;
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
}