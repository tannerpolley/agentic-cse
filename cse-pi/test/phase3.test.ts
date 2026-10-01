import assert from "node:assert/strict";
import { lstat, mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";
import { parsePhase3WorkOrder, runPhase3, type Phase3Hooks } from "../src/phase3.ts";
import { git } from "../src/worker.ts";
import { digest, fixture } from "./build-fixture.ts";

type Tool = { name: string; execute: (id: string, params: any) => Promise<any> };
const SUBMIT = { outcome: "accepted", facts: ["changed candidate"], assumptions: [], findings: ["candidate changed"], evidence: ["candidate.diff"], limitations: ["parent must inspect"], deviations: [], questions: [], recommended_parent_action: "inspect candidate" };
function fakeSession(agent: (tools: Map<string, Tool>) => Promise<void>): Phase3Hooks["createSession"] {
  return async config => {
    const tools = new Map((config.tools as Tool[]).map(tool => [tool.name, tool]));
    return {
      setActiveToolsByName() {}, getActiveToolNames: () => [...tools.keys()], thinkingLevel: config.model.effort,
      async prompt() { await agent(tools); await tools.get("cse_submit_result")!.execute("submit", SUBMIT); },
      async waitForIdle() {}, async abort() {}, subscribe() { return () => {}; },
      getSessionStats: () => ({ tokens: { input: 1, output: 1 } }), async dispose() {},
    };
  };
}
test("parser rejects retired roles, analysis-only fields, and checks exceeding the wall budget", async () => {
  assert.throws(() => parsePhase3WorkOrder({ schema_version: 1, role: "investigate" }), /schema_version/);
  assert.throws(() => parsePhase3WorkOrder({ schema_version: 3, role: "research" }), /only supports role=build/);
  assert.throws(() => parsePhase3WorkOrder({ schema_version: 3, role: "implement" }), /only supports role=build/);
  assert.throws(() => parsePhase3WorkOrder({ schema_version: 3, role: "build", analysis_checks: [] }), /unknown field/);
  const data = await fixture();
  try {
    const check = { id: "suite", kind: "command", command: "true", timeout_ms: data.order.budget.wall_timeout_ms };
    const parsedCheck = parsePhase3WorkOrder({ ...data.order, scientific_checks: [check] }).scientific_checks[0];
    assert.ok(parsedCheck.kind === "command"); assert.equal(parsedCheck.timeout_ms, check.timeout_ms);
    for (const timeout_ms of [99, check.timeout_ms + 1]) assert.throws(() => parsePhase3WorkOrder({ ...data.order, scientific_checks: [{ ...check, timeout_ms }] }), /check.timeout_ms/);
  } finally { await rm(data.base, { recursive: true, force: true }); }
});
test("non-build runs reject before result creation", async () => {
  const data = await fixture();
  try { await assert.rejects(() => runPhase3({ ...data.order, role: "research" }, join(data.base, "run")), /only supports role=build/); await assert.rejects(() => lstat(join(data.base, "run")), /ENOENT/); }
  finally { await rm(data.base, { recursive: true, force: true }); }
});
test("worktree is removed, candidate is retained, and the source checkout is unchanged", async () => {
  const data = await fixture();
  try {
    // The frozen commit, not the current dirty source, supplies the worker's input.
    await writeFile(join(data.source, "model.txt"), "local source edit\n");
    const before = await git(data.source, ["status", "--porcelain=v1"]);
    const registry = await git(data.source, ["worktree", "list", "--porcelain"]);
    const result = await runPhase3(data.order, join(data.base, "run"), false, undefined, { createSession: fakeSession(async tools => {
      await tools.get("cse_edit")!.execute("edit", { path: "model.txt", edits: [{ oldText: "before", newText: "after" }] });
    }) });
    const body = JSON.parse(await readFile(result.result_path, "utf8"));
    assert.equal(result.status, "completed"); assert.equal(body.worktree_removed, true);
    assert.equal(body.worktree_commit, data.order.workspace.commit); assert.equal(body.workspace_identity, data.order.workspace.expected_identity);
    assert.equal(body.supervisor.source_before_after_equal, true);
    assert.equal(await readFile(join(data.source, "model.txt"), "utf8"), "local source edit\n");
    assert.equal(await readFile(join(data.base, "run", "candidate", "model.txt"), "utf8"), "after\n");
    assert.match(await readFile(join(data.base, "run", "candidate.diff"), "utf8"), /-before\n\+after/);
    assert.deepEqual(await git(data.source, ["status", "--porcelain=v1"]), before);
    assert.deepEqual(await git(data.source, ["worktree", "list", "--porcelain"]), registry);
    await assert.rejects(() => lstat(join(data.base, "run", "worktree")), /ENOENT/);
    assert.ok(body.wall_ms > 0); assert.ok(Date.parse(body.ended_at) >= Date.parse(body.started_at));
  } finally { await rm(data.base, { recursive: true, force: true }); }
});
test("out-of-scope and forbidden changes fail with scope_violation but retain their diff", async () => {
  const data = await fixture(); data.order.access.write_paths = ["out"]; data.order.access.write_scopes = [{ path: "out", kind: "directory" }]; data.order.access.forbidden_paths = ["out/forbidden.txt"]; data.order.specification.permitted_paths = ["out"];
  try {
    const result = await runPhase3(data.order, join(data.base, "run"), false, undefined, { createSession: fakeSession(async tools => {
      const command = await tools.get("cse_run_command")!.execute("change", { command: "printf changed > model.txt; mkdir out .pi; printf stray > .pi/stray; printf secret > out/forbidden.txt; printf new > outside.txt" });
      assert.equal(command.isError, false);
    }) });
    const body = JSON.parse(await readFile(result.result_path, "utf8"));
    assert.equal(result.status, "failed"); assert.equal(body.termination, "scope_violation");
    assert.deepEqual(body.scope_violations, [".pi/stray", "model.txt", "out/forbidden.txt", "outside.txt"]);
    const diff = await readFile(join(data.base, "run", "candidate.diff"), "utf8");
    for (const path of body.scope_violations) assert.ok(diff.includes(path));
    assert.equal(await readFile(join(data.source, "model.txt"), "utf8"), "before\n");
    assert.equal(body.worktree_removed, true);
  } finally { await rm(data.base, { recursive: true, force: true }); }
});
test("cse_edit and cse_write refuse outside scope, dependencies, forbidden paths, and symlink escapes", async () => {
  const data = await fixture(); data.order.access.write_paths = ["out"]; data.order.access.write_scopes = [{ path: "out", kind: "directory" }]; data.order.access.forbidden_paths = ["out/forbidden.txt"]; data.order.specification.permitted_paths = ["out"];
  await writeFile(join(data.base, "outside.txt"), "safe\n");
  await mkdir(join(data.source, "out", "deps"), { recursive: true });
  await writeFile(join(data.source, ".gitignore"), "out/deps/\n");
  await git(data.source, ["add", ".gitignore"]); await git(data.source, ["-c", "user.name=CSE Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "dependencies"]);
  data.order.workspace.commit = (await git(data.source, ["rev-parse", "HEAD"])).toString().trim(); data.order.workspace.dependency_paths = ["out/deps"];
  try {
    const result = await runPhase3(data.order, join(data.base, "run"), false, undefined, { createSession: fakeSession(async tools => {
      const root = join(data.base, "run", "worktree"); await mkdir(join(root, "out"));
      await symlink(join(data.base, "outside.txt"), join(root, "out", "link"));
      await symlink(data.base, join(root, "out", "linked-dir"));
      for (const path of ["input.json", "../outside.txt", ".git", "out/.gitignore", "out/forbidden.txt", "out/deps/installed.txt", "out/link", "out/linked-dir/outside.txt"]) {
        await assert.rejects(() => tools.get("cse_edit")!.execute("edit", { path, edits: [{ oldText: "safe", newText: "unsafe" }] }), /scope|symlink|escapes|forbidden|regular/);
        await assert.rejects(() => tools.get("cse_write")!.execute("write", { path, content: "unsafe" }), /scope|symlink|escapes|forbidden|regular/);
      }
      await tools.get("cse_write")!.execute("create", { path: "out/new/file.txt", content: "new\n" });
      await rm(join(root, "out", "link")); await rm(join(root, "out", "linked-dir"));
    }) });
    assert.equal(result.status, "completed"); assert.equal(await readFile(join(data.base, "outside.txt"), "utf8"), "safe\n");
    assert.equal(await readFile(join(data.base, "run", "candidate", "out", "new", "file.txt"), "utf8"), "new\n");
  } finally { await rm(data.base, { recursive: true, force: true }); }
});
test("command checks run in Bubblewrap during the worker and again on final content, with read-only dependencies", async () => {
  const data = await fixture();
  await writeFile(join(data.source, ".gitignore"), "node_modules/\n");
  await git(data.source, ["add", ".gitignore"]); await git(data.source, ["-c", "user.name=CSE Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "dependencies"]);
  data.order.workspace.commit = (await git(data.source, ["rev-parse", "HEAD"])).toString().trim();
  await mkdir(join(data.source, "node_modules")); await writeFile(join(data.source, "node_modules", "dependency.txt"), "installed\n");
  data.order.workspace.dependency_paths = ["node_modules"];
  data.order.budget.command_timeout_ms = 100;
  data.order.scientific_checks = [{ id: "suite", kind: "command", command: "sleep 0.2; test $(cat node_modules/dependency.txt) = installed && ! touch node_modules/denied && mkdir -p node_modules/.vite-temp/generated && printf cache > node_modules/.vite-temp/generated/config && grep -q after model.txt && git diff --exit-code -- input.json", timeout_ms: 1000 }];
  try {
    const result = await runPhase3(data.order, join(data.base, "run"), false, undefined, { createSession: fakeSession(async tools => {
      assert.equal((await tools.get("cse_run_check")!.execute("before", { id: "suite" })).isError, true);
      await tools.get("cse_edit")!.execute("edit", { path: "model.txt", edits: [{ oldText: "before", newText: "after" }] });
      assert.equal((await tools.get("cse_run_check")!.execute("after", { id: "suite" })).isError, false, await readFile(join(data.base, "run", "command-evidence", "command-1.out"), "utf8"));
    }) });
    const body = JSON.parse(await readFile(result.result_path, "utf8"));
    assert.equal(result.status, "completed", JSON.stringify(body)); assert.equal(body.supervisor.commands.length, 3);
    assert.equal(body.supervisor.checks[0].ok, true); assert.equal(body.supervisor.checks[0].exit_code, 0);
    assert.equal(body.supervisor.checks[0].timeout_ms, 1000);
    assert.equal(body.supervisor.checks[0].evidence.output_path, "command-evidence/command-2.out");
    assert.deepEqual(body.supervisor.commands.map((command: { phase: string }) => command.phase), ["advisory", "advisory", "verification"]);
    assert.equal(body.verification.candidate_applied, true);
    assert.match(await readFile(join(data.base, "run", body.supervisor.checks[0].evidence.output_path), "utf8"), /Read-only file system/);
    assert.equal(await readFile(join(data.source, "node_modules", "dependency.txt"), "utf8"), "installed\n");
    await assert.rejects(() => lstat(join(data.source, "node_modules", "denied")), /ENOENT/);
    await assert.rejects(() => lstat(join(data.source, "node_modules", ".vite-temp")), /ENOENT/);
  } finally { await rm(data.base, { recursive: true, force: true }); }
});
test("a symlinked result parent uses real paths and unregisters both worktrees", async () => {
  const data = await fixture(); const parent = join(data.base, "real-parent"); const alias = join(data.base, "alias");
  await mkdir(parent); await symlink(parent, alias);
  const registry = await git(data.source, ["worktree", "list", "--porcelain"]);
  try {
    const result = await runPhase3(data.order, join(alias, "run"), false, undefined, { createSession: fakeSession(async tools => {
      await tools.get("cse_edit")!.execute("edit", { path: "model.txt", edits: [{ oldText: "before", newText: "edited" }] });
      await tools.get("cse_write")!.execute("write", { path: "model.txt", content: "after\n" });
    }) });
    const body = JSON.parse(await readFile(result.result_path, "utf8"));
    assert.equal(result.status, "completed", JSON.stringify(body)); assert.equal(result.result_path, join(parent, "run", "result.json"));
    assert.equal(body.worktree_removed, true); assert.equal(body.verification_worktree_removed, true);
    assert.deepEqual(await git(data.source, ["worktree", "list", "--porcelain"]), registry);
    assert.equal(await readFile(join(alias, "run", "candidate", "model.txt"), "utf8"), "after\n");
    assert.equal(await readFile(join(data.source, "model.txt"), "utf8"), "before\n");
  } finally { await rm(data.base, { recursive: true, force: true }); }
});
test("nested ignore rules cannot hide candidate files or pollute decisive verification checks", async () => {
  const data = await fixture();
  await writeFile(join(data.source, ".gitignore"), "out/ignored/\n");
  await git(data.source, ["add", ".gitignore"]); await git(data.source, ["-c", "user.name=CSE Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "frozen ignore rules"]);
  data.order.workspace.commit = (await git(data.source, ["rev-parse", "HEAD"])).toString().trim();
  data.order.access.write_paths = ["out"]; data.order.access.write_scopes = [{ path: "out", kind: "directory" }]; data.order.specification.permitted_paths = ["out"];
  data.order.scientific_checks = [{ id: "hidden-config", kind: "command", command: "if test -e out/ignored/vitest.config.ts; then echo polluted; exit 0; else echo clean-verification; exit 7; fi" }];
  try {
    const result = await runPhase3(data.order, join(data.base, "run"), false, undefined, { createSession: fakeSession(async tools => {
      assert.equal((await tools.get("cse_run_command")!.execute("hide", { command: "mkdir -p out/ignored; printf '*' > out/.gitignore; printf '*' > out/ignored/.gitignore; printf hidden > out/hidden.ts; printf skip-tests > out/ignored/vitest.config.ts" })).isError, false);
      assert.equal((await tools.get("cse_run_check")!.execute("advisory", { id: "hidden-config" })).isError, false);
    }) });
    const body = JSON.parse(await readFile(result.result_path, "utf8"));
    assert.equal(result.status, "failed"); assert.equal(body.termination, "scope_violation");
    assert.deepEqual(body.scope_violations, ["out/.gitignore", "out/ignored/.gitignore"]);
    assert.deepEqual(body.excluded_ignored_output, ["out/ignored/.gitignore", "out/ignored/vitest.config.ts"]);
    const diff = await readFile(join(data.base, "run", "candidate.diff"), "utf8");
    assert.match(diff, /out\/hidden\.ts/); assert.match(diff, /out\/\.gitignore/); assert.doesNotMatch(diff, /out\/ignored/);
    assert.equal(body.verification.candidate_applied, true);
    assert.equal(body.supervisor.checks[0].phase, "verification"); assert.equal(body.supervisor.checks[0].exit_code, 7); assert.equal(body.supervisor.checks[0].ok, false);
    assert.match(await readFile(join(data.base, "run", body.supervisor.checks[0].evidence.output_path), "utf8"), /clean-verification/);
    assert.equal(body.supervisor.commands[1].phase, "advisory");
    assert.equal(body.worktree_removed, true); assert.equal(body.verification_worktree_removed, true);
  } finally { await rm(data.base, { recursive: true, force: true }); }
});
test("unwritable working and verification directories are cleaned without capturing verification writes", async () => {
  const data = await fixture(); const registry = await git(data.source, ["worktree", "list", "--porcelain"]);
  data.order.access.write_paths = ["locked"]; data.order.access.write_scopes = [{ path: "locked", kind: "directory" }]; data.order.specification.permitted_paths = ["locked"];
  data.order.scientific_checks = [{ id: "writes-snapshot", kind: "command", command: "mkdir locked-check; printf snapshot > locked-check/result; chmod 555 locked-check" }];
  try {
    const result = await runPhase3(data.order, join(data.base, "run"), false, undefined, { createSession: fakeSession(async tools => {
      assert.equal((await tools.get("cse_run_command")!.execute("lock", { command: "mkdir locked; printf content > locked/child; chmod 555 locked" })).isError, false);
    }) });
    const body = JSON.parse(await readFile(result.result_path, "utf8"));
    assert.equal(result.status, "completed", JSON.stringify(body));
    assert.deepEqual(body.candidate_changes.map((change: { path: string }) => change.path), ["locked/child"]);
    assert.equal(body.supervisor.checks[0].ok, true); assert.equal(body.supervisor.checks[0].phase, "verification");
    assert.equal(body.worktree_removed, true); assert.equal(body.verification_worktree_removed, true);
    assert.deepEqual(await git(data.source, ["worktree", "list", "--porcelain"]), registry);
    await assert.rejects(() => lstat(join(data.base, "run", "worktree")), /ENOENT/);
    await assert.rejects(() => lstat(join(data.base, "run", "verification-worktree")), /ENOENT/);
    assert.doesNotMatch(await readFile(join(data.base, "run", "candidate.diff"), "utf8"), /locked-check/);
  } finally { await rm(data.base, { recursive: true, force: true }); }
});
test("deleted files are retained in the candidate and applied in verification only", async () => {
  const data = await fixture(); data.order.scientific_checks = [{ id: "deleted", kind: "command", command: "test ! -e model.txt" }];
  try {
    const result = await runPhase3(data.order, join(data.base, "run"), false, undefined, { createSession: fakeSession(async tools => {
      assert.equal((await tools.get("cse_run_command")!.execute("delete", { command: "rm -- model.txt" })).isError, false);
    }) });
    const body = JSON.parse(await readFile(result.result_path, "utf8"));
    assert.equal(result.status, "completed", JSON.stringify(body));
    assert.deepEqual(body.candidate_changes, [{ path: "model.txt", action: "deleted", before_sha256: digest("before\n"), after_sha256: null }]);
    assert.match(await readFile(join(data.base, "run", "candidate.diff"), "utf8"), /deleted file mode/);
    assert.equal(body.verification.candidate_applied, true); assert.equal(body.supervisor.checks[0].ok, true);
    assert.equal(await readFile(join(data.source, "model.txt"), "utf8"), "before\n");
  } finally { await rm(data.base, { recursive: true, force: true }); }
});
test("final-integrity failures override a completed build and still remove its worktree", async () => {
  const data = await fixture();
  try {
    const result = await runPhase3(data.order, join(data.base, "run"), false, undefined, { createSession: fakeSession(async () => {}), beforeFinalIntegrity: async () => rm(join(data.source, "input.json")) });
    assert.equal(result.status, "failed");
    const body = JSON.parse(await readFile(result.result_path, "utf8")); assert.equal(body.termination, "integrity_check_failed"); assert.equal(body.worktree_removed, true);
  } finally { await rm(data.base, { recursive: true, force: true }); }
});
