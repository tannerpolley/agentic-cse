import { createHash } from "node:crypto";
import { git } from "../src/worker.ts";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { parsePhase3WorkOrder, type Phase3WorkOrder } from "../src/phase3.ts";

export const digest = (value: string): string => createHash("sha256").update(value).digest("hex");

export async function fixture(): Promise<{ base: string; source: string; order: Phase3WorkOrder }> {
  const base = await mkdtemp(join(tmpdir(), "cse-pi-phase3-"));
  const source = join(base, "source");
  await mkdir(source);
  await writeFile(join(source, "model.txt"), "before\n");
  await writeFile(join(source, "input.json"), '{"value":1}\n');
  await git(source, ["init", "--quiet"]);
  await git(source, ["add", "--", "model.txt", "input.json"]);
  await git(source, ["-c", "user.name=CSE Test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "fixture"]);
  const commit = (await git(source, ["rev-parse", "HEAD"])).toString().trim();
  const hashes = { "input.json": digest('{"value":1}\n'), "model.txt": digest("before\n") };
  const order = parsePhase3WorkOrder({
    schema_version: 3,
    task_id: "phase3-build",
    role: "build",
    objective: "bounded build fixture",
    scientific_question: "does the build retain bounded evidence?",
    workspace: { root: source, commit, expected_identity: digest("input.json\0" + hashes["input.json"] + "\nmodel.txt\0" + hashes["model.txt"]) },
    context_files: [{ path: "input.json", sha256: hashes["input.json"], purpose: "fixture input" }],
    known_context: ["synthetic fixture"],
    constraints: ["bounded"],
    non_goals: ["parent acceptance"],
    access: { read_paths: ["input.json", "model.txt"], write_paths: ["model.txt"], write_scopes: [{ path: "model.txt", kind: "file" }], forbidden_paths: ["forbidden.txt"] },
    write_policy: "candidate",
    network_policy: "none",
    expected_artifacts: ["retained evidence"],
    acceptance_criteria: ["structured result"],
    validation: ["inspect hashes"],
    scientific_checks: [],
    parent_identity: "parent-phase3",
    budget: { wall_timeout_ms: 5000, model_turn_limit: 1, command_timeout_ms: 1000, output_bytes: 65536 },
    specification: { text: "frozen fixture specification", required_changes: ["change model"], forbidden_changes: ["change input"], permitted_paths: ["model.txt"] },
  });
  return { base, source, order };
}
