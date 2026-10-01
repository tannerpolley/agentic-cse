#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { run } from "./worker.js";

const help = "Usage: cse-pi run --task /absolute/work-order.json --result-dir /absolute/new-run-directory [--role build] [--no-inference]\\n\\nSupports schema v3 build-only one-shot workers. --no-inference verifies frozen identity, captures the candidate, runs declared checks in a fresh verification worktree, retains evidence, and removes both worktrees without authentication or model execution.";

function option(args: string[], name: string): string | undefined {
  const index = args.indexOf(name);
  if (index < 0) return undefined;
  if (args.lastIndexOf(name) !== index || !args[index + 1] || args[index + 1].startsWith("--")) throw new Error(help);
  return args[index + 1];
}

function count(args: string[], name: string): number {
  return args.filter(value => value === name).length;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args[0] === "--help" || args[0] === "help") {
    console.log(help);
    return;
  }
  if (args[0] === "--version") {
    console.log("0.1.0");
    return;
  }
  if (args[0] !== "run") throw new Error(help);
  const taskPath = option(args, "--task");
  const resultDir = option(args, "--result-dir");
  const role = option(args, "--role");
  if (role && role !== "build") throw new Error("CSE-Pi only supports --role build");
  const noInference = args.includes("--no-inference");
  const supported = new Set(["run", "--task", "--result-dir", "--role", "--no-inference"]);
  for (let index = 0; index < args.length; index += 1) {
    if (args[index].startsWith("--") && !supported.has(args[index])) throw new Error(help);
  }
  if (count(args, "--task") !== 1 || count(args, "--result-dir") !== 1 || count(args, "--role") > 1 || count(args, "--no-inference") > 1) throw new Error(help);
  if (!taskPath || !resultDir || !taskPath.startsWith("/") || !resultDir.startsWith("/")) {
    throw new Error("--task and --result-dir must be absolute paths");
  }
  const order = JSON.parse(await readFile(resolve(taskPath), "utf8")) as { role?: string };
  if (order.role !== "build") throw new Error("CSE-Pi only supports role=build");
  if (role && order.role !== role) throw new Error("--role does not match work-order role");
  const controller = new AbortController();
  process.once("SIGINT", () => controller.abort());
  process.once("SIGTERM", () => controller.abort());
  const outcome = await run(order, resolve(resultDir), noInference, controller.signal);
  console.log(JSON.stringify(outcome));
  if (outcome.status !== "completed") process.exitCode = 1;
}

main().catch(error => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
