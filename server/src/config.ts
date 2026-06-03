import os from "node:os";
import path from "node:path";

function defaultQueueRoot(): string {
  if (process.platform === "win32") {
    const localAppData = process.env.LOCALAPPDATA;
    if (localAppData) {
      return path.join(localAppData, "SketchUpMCPBridge");
    }
  }

  return path.join(os.homedir(), ".sketchup-mcp-bridge");
}

function parseNumber(value: string | undefined, fallback: number): number {
  if (!value) {
    return fallback;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export const config = {
  queueRoot: process.env.SKETCHUP_MCP_QUEUE_ROOT || defaultQueueRoot(),
  timeoutMs: parseNumber(process.env.SKETCHUP_MCP_TIMEOUT_MS, 15_000),
  pollMs: parseNumber(process.env.SKETCHUP_MCP_POLL_MS, 250),
};
