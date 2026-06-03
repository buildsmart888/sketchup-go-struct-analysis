import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { config } from "./config.js";

type Primitive = string | number | boolean | null;
type JsonValue = Primitive | JsonValue[] | { [key: string]: JsonValue };

export interface BridgeSuccess<T = JsonValue> {
  id: string;
  ok: true;
  data: T;
  completedAt: string;
}

export interface BridgeFailure {
  id?: string;
  ok: false;
  error: string;
  completedAt?: string;
}

export type BridgeResult<T = JsonValue> = BridgeSuccess<T> | BridgeFailure;

interface CommandEnvelope {
  id: string;
  tool: string;
  args: Record<string, JsonValue>;
  createdAt: string;
}

export class FileQueueBridge {
  private readonly queueRoot: string;
  private readonly commandsDir: string;
  private readonly resultsDir: string;
  private readonly timeoutMs: number;
  private readonly pollMs: number;

  constructor(options?: {
    queueRoot?: string;
    timeoutMs?: number;
    pollMs?: number;
  }) {
    this.queueRoot = options?.queueRoot ?? config.queueRoot;
    this.commandsDir = path.join(this.queueRoot, "commands");
    this.resultsDir = path.join(this.queueRoot, "results");
    this.timeoutMs = options?.timeoutMs ?? config.timeoutMs;
    this.pollMs = options?.pollMs ?? config.pollMs;
  }

  async call<T = JsonValue>(
    tool: string,
    args: Record<string, JsonValue> = {},
  ): Promise<BridgeResult<T>> {
    await this.ensureDirs();

    const id = crypto.randomUUID();
    const commandPath = path.join(this.commandsDir, `${id}.json`);
    const resultPath = path.join(this.resultsDir, `${id}.json`);

    const payload: CommandEnvelope = {
      id,
      tool,
      args,
      createdAt: new Date().toISOString(),
    };

    await fs.writeFile(commandPath, JSON.stringify(payload, null, 2), "utf8");

    const deadline = Date.now() + this.timeoutMs;
    while (Date.now() < deadline) {
      const maybeResult = await this.tryReadResult<T>(resultPath);
      if (maybeResult) {
        return maybeResult;
      }
      await this.sleep(this.pollMs);
    }

    return {
      id,
      ok: false,
      error: `Timed out waiting for SketchUp to complete '${tool}' after ${this.timeoutMs} ms.`,
    };
  }

  private async ensureDirs(): Promise<void> {
    await Promise.all([
      fs.mkdir(this.queueRoot, { recursive: true }),
      fs.mkdir(this.commandsDir, { recursive: true }),
      fs.mkdir(this.resultsDir, { recursive: true }),
    ]);
  }

  private async tryReadResult<T>(resultPath: string): Promise<BridgeResult<T> | null> {
    try {
      const raw = await fs.readFile(resultPath, "utf8");
      const parsed = JSON.parse(raw) as BridgeResult<T>;
      await fs.unlink(resultPath);
      return parsed;
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code === "ENOENT") {
        return null;
      }
      throw error;
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => {
      setTimeout(resolve, ms);
    });
  }
}
