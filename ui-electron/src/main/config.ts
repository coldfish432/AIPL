export const AppConfig = {
  javaHost: process.env.AIPL_SERVER_HOST || "127.0.0.1",
  javaPort: Number(process.env.AIPL_SERVER_PORT || 18088),
  startupTimeoutMs: Number(process.env.AIPL_SERVER_STARTUP_TIMEOUT || 15000),
};

export function getBaseUrl(): string {
  return `http://${AppConfig.javaHost}:${AppConfig.javaPort}`;
}
