import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { lstat, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { parsePhase3WorkOrder, runPhase3, type Phase3WorkOrder } from "../src/phase3.ts";

const digest = (value: string): string => createHash("sha256").update(value).digest("hex");

async function fixture(role: Phase3WorkOrder["role"]): Promise<{ base: string; source: string; order: Phase3WorkOrder }> {
  const base = await mkdtemp(join(tmpdir(), "cse-pi-phase3-"));
  const source = join(base, "source");
  await (await import("node:fs/promises")).mkdir(source);
  await writeFile(join(source, "model.txt"), "before\n");
  await writeFile(join(source, "input.json"), '{"value":1}\n');
  const hashes = { "input.json": digest('{"value":1}\n'), "model.txt": digest("before\n") };
  const order = parsePhase3WorkOrder({
    schema_version: 2,
    task_id: `phase3-${role}`,
    role,
    objective: "bounded phase 3 fixture",
    scientific_question: "does the role retain bounded evidence?",
    workspace: { root: source, expected_identity: digest(`input.json\0${hashes["input.json"]}\nmodel.txt\0${hashes["model.txt"]}`) },
    context_files: [{ path: "input.json", sha256: hashes["input.json"], purpose: "fixture input" }],
    known_context: ["synthetic fixture"],
    constraints: ["bounded"],
    non_goals: ["parent acceptance"],
    access: { read_paths: ["input.json", "model.txt"], write_paths: role === "implement" ? ["model.txt"] : [], write_scopes: role === "implement" ? [{ path: "model.txt", kind: "file" }] : [], forbidden_paths: ["forbidden.txt"] },
    write_policy: role === "implement" ? "candidate" : role === "analyze" ? "analysis" : "none",
    network_policy: "none",
    expected_artifacts: ["retained evidence"],
    acceptance_criteria: ["structured result"],
    validation: ["inspect hashes"],
    scientific_checks: [],
    analysis_checks: role === "analyze" ? [{ id: "json-output", kind: "json", path: "results.json", checker_identity: "fixture-check" }] : [],
    parent_identity: "parent-phase3",
    budget: { wall_timeout_ms: 5000, model_turn_limit: 1, command_timeout_ms: 1000, output_bytes: 65536 },
    specification: { text: "frozen fixture specification", required_changes: ["change model"], forbidden_changes: ["change input"], permitted_paths: role === "implement" ? ["model.txt"] : [] },
    output_paths: role === "analyze" ? ["results.json"] : [],
    review_inputs: [],
  });
  return { base, source, order };
}

function fakeSessionFactory() {
  const seen: Array<{ role: string; model: string; effort: string; tools: string[]; prompt: string }> = [];
  const createSession = async (config: { role: "implement" | "analyze" | "review"; model: { model: string; effort: string }; prompt: string; tools: readonly unknown[] }) => {
    seen.push({ role: config.role, model: config.model.model, effort: config.model.effort, tools: config.tools.map(tool => (tool as { name: string }).name), prompt: config.prompt });
    const names = config.tools.map(tool => (tool as { name: string }).name);
    const session = {
      setActiveToolsByName() {},
      getActiveToolNames: () => names,
      thinkingLevel: config.model.effort,
      async prompt() {},
      async waitForIdle() {},
      async abort() {},
      subscribe() { return () => {}; },
      getSessionStats: () => ({ tokens: { input: 1, output: 1 } }),
      retryAttempt: 0,
      async dispose() {},
    };
    const submit = config.tools.find(tool => (tool as { name: string }).name === "cse_submit_result") as { execute: (id: string, params: unknown) => Promise<unknown> } | undefined;
    const review = config.tools.find(tool => (tool as { name: string }).name === "cse_submit_review") as { execute: (id: string, params: unknown) => Promise<unknown> } | undefined;
    const write = config.tools.find(tool => (tool as { name: string }).name === "cse_write_candidate") as { execute: (id: string, params: { path: string; content: string }) => Promise<unknown> } | undefined;
    const remove = config.tools.find(tool => (tool as { name: string }).name === "cse_delete_candidate") as { execute: (id: string, params: { path: string }) => Promise<unknown> } | undefined;
    const runCommand = config.tools.find(tool => (tool as { name: string }).name === "cse_run_command") as { execute: (id: string, params: { command: string }, signal?: AbortSignal) => Promise<{ isError?: boolean }> } | undefined;
    const originalPrompt = session.prompt;
    session.prompt = async () => {
      if (config.role === "implement") {
        assert.ok(write);
        assert.ok(runCommand);
        assert.equal((await runCommand!.execute("read", { command: "cat /workspace/model.txt" })).isError, false);
        assert.equal((await runCommand!.execute("deny", { command: "touch /workspace/forbidden.txt" })).isError, true);
        await assert.rejects(() => write!.execute("forbidden", { path: "../outside.txt", content: "no" }), /relative|scope|escapes/);
        assert.ok(remove);
        await remove!.execute("delete", { path: "model.txt" });
        await write!.execute("allowed", { path: "model.txt", content: "after\n" });
        await submit!.execute("submit", { outcome: "accepted", facts: ["changed candidate"], assumptions: [], findings: ["candidate changed"], evidence: ["candidate.diff"], limitations: ["parent must inspect"], deviations: [], questions: [], recommended_parent_action: "inspect candidate" });
      } else if (config.role === "analyze") {
        assert.ok(runCommand);
        assert.equal((await runCommand!.execute("write", { command: "printf '{\"value\":2}\\n' > /workspace/analysis/results.json" })).isError, false);
        assert.equal((await runCommand!.execute("read", { command: "cat /workspace/analysis/results.json" })).isError, false);
        await submit!.execute("submit", { outcome: "inconclusive", facts: ["bounded result"], assumptions: [], findings: ["result retained"], evidence: ["analysis/results.json"], limitations: ["synthetic"], deviations: [], questions: [], recommended_parent_action: "inspect result" });
      } else {
        await review!.execute("review", { outcome: "blocked", summary: "blocking fixture finding", findings: [{ id: "R1", severity: "high", blocking: true, category: "verification", file: "model.txt", line: 1, evidence: "fixture evidence", impact: "cannot accept", confidence: "high", recommended_action: "parent inspect" }], limitations: ["synthetic"], recommended_parent_action: "resolve finding" });
      }
      await originalPrompt();
    };
    return session;
  };
  return { createSession, seen };
}

test("phase 3 roles resolve profiles and preflight without inference", async () => {
  for (const role of ["implement", "analyze", "review"] as const) {
    const fixtureData = await fixture(role);
    try {
      const result = await runPhase3(fixtureData.order, join(fixtureData.base, `run-${role}`), true);
      assert.equal(result.status, "preflight");
      const body = JSON.parse(await readFile(result.result_path, "utf8"));
      assert.equal(body.schema_version, 2);
      assert.equal(body.role, role);
      assert.equal(body.requested_model.provider, "openai-codex");
      assert.equal(body.supervisor.source_before_after_equal, true);
    } finally {
      await rm(fixtureData.base, { recursive: true, force: true });
    }
  }
});

test("implement retains scoped candidate diff and denies traversal during execution", async () => {
  const fixtureData = await fixture("implement");
  const fake = fakeSessionFactory();
  try {
    const result = await runPhase3(fixtureData.order, join(fixtureData.base, "run"), false, undefined, { createSession: fake.createSession });
    assert.equal(result.status, "completed");
    assert.equal(await readFile(join(fixtureData.source, "model.txt"), "utf8"), "before\n");
    const body = JSON.parse(await readFile(result.result_path, "utf8"));
    assert.equal(body.role, "implement");
    assert.equal(body.candidate_changes[0].path, "model.txt");
    assert.equal(body.candidate_changes[0].action, "modified");
    assert.equal(body.supervisor.source_before_after_equal, true);
    assert.match(await readFile(join(fixtureData.base, "run", "candidate.diff"), "utf8"), /model.txt/);
    assert.equal(fake.seen[0].model, "gpt-5.6-luna");
    assert.equal(fake.seen[0].effort, "high");
  } finally {
    await rm(fixtureData.base, { recursive: true, force: true });
  }
});

test("implement supports file deletion and nested creation in an explicit directory scope", async () => {
  const base = await mkdtemp(join(tmpdir(), "cse-pi-phase3-directory-"));
  const source = join(base, "source");
  await mkdir(join(source, "out"), { recursive: true });
  await writeFile(join(source, "input.json"), '{"value":1}\n');
  await writeFile(join(source, "out", "keep.txt"), "keep\n");
  const inputHash = digest('{"value":1}\n');
  const keepHash = digest("keep\n");
  const order = parsePhase3WorkOrder({
    schema_version: 2,
    task_id: "phase3-directory",
    role: "implement",
    objective: "exercise directory scope",
    scientific_question: "are nested changes retained?",
    workspace: { root: source, expected_identity: digest("input.json\0" + inputHash + "\nout/keep.txt\0" + keepHash) },
    context_files: [{ path: "input.json", sha256: inputHash, purpose: "fixture input" }],
    known_context: [],
    constraints: ["bounded"],
    non_goals: [],
    access: { read_paths: ["input.json", "out"], write_paths: ["out"], write_scopes: [{ path: "out", kind: "directory" }], forbidden_paths: [] },
    write_policy: "candidate",
    network_policy: "none",
    expected_artifacts: [],
    acceptance_criteria: ["directory changes"],
    validation: [],
    scientific_checks: [],
    parent_identity: "parent-phase3",
    budget: { wall_timeout_ms: 5000, model_turn_limit: 1, command_timeout_ms: 1000, output_bytes: 65536 },
    specification: { text: "directory scope", required_changes: ["delete keep and create new"], forbidden_changes: [], permitted_paths: ["out"] },
    output_paths: [],
    review_inputs: [],
  });
  const createSession = async (config: { model: { effort: string }; tools: readonly unknown[] }) => {
    const names = config.tools.map(tool => (tool as { name: string }).name);
    const session = {
      setActiveToolsByName() {},
      getActiveToolNames: () => names,
      thinkingLevel: config.model.effort,
      async prompt() {},
      async waitForIdle() {},
      async abort() {},
      subscribe() { return () => {}; },
      async dispose() {},
    };
    const find = (name: string) => config.tools.find(tool => (tool as { name: string }).name === name) as { execute: (id: string, params: any) => Promise<unknown> } | undefined;
    const remove = find("cse_delete_candidate");
    const write = find("cse_write_candidate");
    const submit = find("cse_submit_result");
    const prompt = async () => {
      await remove!.execute("delete", { path: "out/keep.txt" });
      await write!.execute("write", { path: "out/new.txt", content: "new\n" });
      await submit!.execute("submit", { outcome: "accepted", facts: ["directory changes"], assumptions: [], findings: ["nested file"], evidence: ["candidate.diff"], limitations: [], deviations: [], questions: [], recommended_parent_action: "inspect" });
    };
    return { ...session, prompt };
  };
  try {
    const result = await runPhase3(order, join(base, "run"), false, undefined, { createSession });
    assert.equal(result.status, "completed");
    assert.equal(await readFile(join(source, "out", "keep.txt"), "utf8"), "keep\n");
    assert.equal(await readFile(join(base, "run", "candidate", "out", "new.txt"), "utf8"), "new\n");
    await assert.rejects(() => lstat(join(base, "run", "candidate", "out", "keep.txt")), /ENOENT/);
    const body = JSON.parse(await readFile(result.result_path, "utf8"));
    assert.deepEqual(body.candidate_changes.map((change: { path: string; action: string }) => [change.path, change.action]), [["out/keep.txt", "deleted"], ["out/new.txt", "created"]]);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test("analyze retains only assigned outputs and review returns structured findings", async () => {
  for (const role of ["analyze", "review"] as const) {
    const fixtureData = await fixture(role);
    const fake = fakeSessionFactory();
    try {
      const result = await runPhase3(fixtureData.order, join(fixtureData.base, "run"), false, undefined, { createSession: fake.createSession });
      assert.equal(result.status, role === "review" ? "blocked" : "completed");
      const body = JSON.parse(await readFile(result.result_path, "utf8"));
      assert.equal(body.role, role);
      assert.deepEqual(body.usage, { input: 1, output: 1 });
      if (role === "analyze") assert.equal(body.analysis_outputs[0].path, "analysis/results.json");
      else assert.equal(body.review_findings[0].blocking, true);
    } finally {
      await rm(fixtureData.base, { recursive: true, force: true });
    }
  }
});

test("analysis checks name exact output files", async () => {
  const fixtureData = await fixture("analyze");
  try {
    const order = { ...fixtureData.order, output_paths: ["results"], analysis_checks: [{ id: "nested", kind: "json", path: "results/data.json", checker_identity: "fixture" }] };
    assert.throws(() => parsePhase3WorkOrder(order), /exact output_paths/);
  } finally {
    await rm(fixtureData.base, { recursive: true, force: true });
  }
});
