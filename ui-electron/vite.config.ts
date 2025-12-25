import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { spawn } from "child_process";

// Electron dev plugin (Windows-safe)
function electronDevPlugin() {
  let started = false;

  return {
    name: "electron-dev",
    configureServer(server: any) {
      server.httpServer?.once("listening", () => {
        if (started) return;
        started = true;

        const devUrl =
          server.resolvedUrls?.local[0] ?? "http://127.0.0.1:5173";

        // 1️⃣ compile electron main (tsc)
        const tsc = spawn(
          "npx",
          ["tsc", "-p", "tsconfig.main.json"],
          {
            stdio: "inherit",
            shell: true, // ⭐ Windows 必须
          }
        );

        tsc.on("exit", (code) => {
          if (code !== 0) {
            console.error("[electron-dev] tsc failed:", code);
            return;
          }

          // 2️⃣ start electron with absolute binary path
          const electronPath = require("electron");

          const electron = spawn(
            electronPath,
            ["."],
            {
              stdio: "inherit",
              shell: true, // ⭐ 关键：避免 spawn EINVAL
              env: {
                ...process.env,
                VITE_DEV_SERVER_URL: devUrl,
              },
            }
          );

          electron.on("close", () => {
            server.close();
            process.exit();
          });
        });
      });
    },
  };
}

export default defineConfig({
  root: path.resolve(__dirname, "src/renderer"),
  base: "./",
  plugins: [
    react(),
    electronDevPlugin(),
  ],
  server: {
    fs: {
      allow: [path.resolve(__dirname)],
    },
    proxy: {
      "/api/": {
        target: "http://127.0.0.1:18088",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: path.resolve(__dirname, "dist/renderer"),
    emptyOutDir: true,
  },
});
