import { readFile } from "node:fs/promises";
import path from "node:path";

import { connection } from "next/server";

import { BenchView } from "@/components/benchmark/bench-view";
import { benchRows } from "@/lib/bench";

export const metadata = { title: "Benchmark · On-call" };

// written by: uv run python -m bench.report bench/results.jsonl --output-dir bench/out
const SUMMARY = path.join(process.cwd(), "..", "bench", "out", "summary.json");

export default async function BenchmarkPage() {
  await connection(); // read the file per request, not once at build
  let raw: string;
  try {
    raw = await readFile(SUMMARY, "utf8");
  } catch {
    return <BenchView rows={null} error={null} />;
  }
  try {
    return <BenchView rows={benchRows(JSON.parse(raw))} error={null} />;
  } catch (e) {
    return <BenchView rows={null} error={`bench/out/summary.json is not valid JSON: ${(e as Error).message}`} />;
  }
}
