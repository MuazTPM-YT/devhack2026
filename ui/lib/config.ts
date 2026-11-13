import { readFile } from "node:fs/promises";
import path from "node:path";

import { type Policy, parsePolicy, parseServices, type ServiceInfo } from "./overview.ts";

// repo config next to ui/; read on the server per request, the browser never sees the files
const CONFIG = path.join(process.cwd(), "..", "config");

const EMPTY: Policy = { errThreshold: null, latencyMultiplier: null, latencyFloorMs: null, maxAgeS: null };

export async function readPolicy(): Promise<Policy> {
  try {
    return parsePolicy(await readFile(path.join(CONFIG, "policy.yaml"), "utf8"));
  } catch {
    return EMPTY;
  }
}

export async function readServices(): Promise<Record<string, ServiceInfo>> {
  try {
    return parseServices(await readFile(path.join(CONFIG, "services.yaml"), "utf8"));
  } catch {
    return {};
  }
}
