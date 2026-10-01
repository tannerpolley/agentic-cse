import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";
import { runSandbox } from "../src/sandbox.ts";
import { safeRegularFile } from "../src/contracts.ts";
import { safeCommandTool } from "../src/cse-extension.ts";
import { git } from "../src/worker.ts";
import { fixture } from "./build-fixture.ts";

async function sandboxFixture() {
  const data = await fixture();
  const options = { commonGitDir: join(data.source, ".git"), dependencies: [] };
  const root = join(data.base, "worktree"); await git(data.source, ["worktree", "add", "--detach", root, data.order.workspace.commit]);
  return { ...data, root, options, cleanup: async () => { await git(data.source, ["worktree", "remove", "--force", root]); await rm(data.base, { recursive: true, force: true }); } };
}
test("Bubblewrap denies host home and network", async () => {
  const data = await sandboxFixture();
  try {
    const result = await runSandbox("test ! -e /home/user && python3 -c 'import socket; socket.create_connection((\"1.1.1.1\",53),.2)'", data.root, 5000, 4096, undefined, data.options);
    assert.notEqual(result.evidence.exit_code, 0); assert.match(result.output, /Network is unreachable/);
  } finally { await data.cleanup(); }
});
test("Bubblewrap kills timeout and output floods", async () => {
  const data = await sandboxFixture();
  try {
    assert.equal((await runSandbox("sleep 10", data.root, 50, 1024, undefined, data.options)).evidence.timed_out, true);
    assert.equal((await runSandbox("yes", data.root, 5000, 64, undefined, data.options)).evidence.output_limited, true);
  } finally { await data.cleanup(); }
});
test("Bubblewrap cancellation kills the process group", async () => {
  const data = await sandboxFixture(); const controller = new AbortController(); setTimeout(() => controller.abort(), 30);
  try { const result = await runSandbox("sleep 10 & wait", data.root, 5000, 1024, controller.signal, data.options); assert.notEqual(result.evidence.exit_code, 0); }
  finally { await data.cleanup(); }
});
test("Bubblewrap scrubs supervisor secrets from environment and proc", async () => {
  const data = await sandboxFixture(); const prior = process.env.CSE_PI_SYNTHETIC_SECRET; process.env.CSE_PI_SYNTHETIC_SECRET = "do-not-leak";
  try { const result = await runSandbox("test -z \"$CSE_PI_SYNTHETIC_SECRET\" && ! grep -a -q CSE_PI_SYNTHETIC_SECRET /proc/1/environ && test ! -e /home/user/.ssh", data.root, 3000, 1024, undefined, data.options); assert.equal(result.evidence.exit_code, 0); }
  finally { if (prior === undefined) delete process.env.CSE_PI_SYNTHETIC_SECRET; else process.env.CSE_PI_SYNTHETIC_SECRET = prior; await data.cleanup(); }
});
test("workspace file checks reject symlinked ancestor components", async () => {
  const data = await sandboxFixture(); await mkdir(join(data.base, "outside")); await writeFile(join(data.base, "outside", "input"), "x"); await symlink(join(data.base, "outside"), join(data.root, "linked"));
  try { await assert.rejects(() => safeRegularFile(data.root, "linked/input"), /symlink path component/); }
  finally { await data.cleanup(); }
});
test("retained command evidence is byte-exact and outside the writable worktree", async () => {
  const data = await sandboxFixture();
  const evidenceDir = join(data.base, "command-evidence"); await mkdir(evidenceDir); const evidence: unknown[] = [];
  const tool = safeCommandTool(data.root, () => 3000, 1024, data.options, new AbortController().signal, async result => {
    const output = join(evidenceDir, "command-" + evidence.length + ".out"); await writeFile(output, result.raw_output); evidence.push(result.evidence); return result.evidence;
  });
  try {
    await tool.execute("binary", { command: "printf '\\377'" }, undefined, undefined, undefined as never);
    const bytes = await readFile(join(evidenceDir, "command-0.out")); assert.deepEqual(bytes, Buffer.from([0xff]));
    assert.equal((evidence[0] as { output_sha256: string }).output_sha256, createHash("sha256").update(bytes).digest("hex"));
    const attempt = await runSandbox("test ! -e " + evidenceDir, data.root, 3000, 1024, undefined, data.options); assert.equal(attempt.evidence.exit_code, 0);
  } finally { await data.cleanup(); }
});
