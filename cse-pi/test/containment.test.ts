import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, rm, stat, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { runSandbox } from "../src/sandbox.ts";
import { safeRegularFile } from "../src/contracts.ts";
import { safeCommandTool } from "../src/cse-extension.ts";

test("Bubblewrap denies source writes, host home, and network", async () => { const base = await mkdtemp(join(tmpdir(), "cse-pi-bwrap-")); const source = join(base, "source"); const scratch = join(base, "scratch"); await mkdir(source); await mkdir(scratch); await writeFile(join(source, "readonly"), "safe"); try { const result = await runSandbox("test ! -e /home/user; touch /workspace/readonly; python3 -c 'import socket; socket.create_connection((\"1.1.1.1\",53),.2)'", source, scratch, 5000, 4096); assert.notEqual(result.evidence.exit_code, 0); assert.match(result.output, /Network is unreachable/); assert.equal(await readFile(join(source, "readonly"), "utf8"), "safe"); } finally { await rm(base, { recursive: true, force: true }); } });
test("Bubblewrap kills timeout and output floods", async () => { const base = await mkdtemp(join(tmpdir(), "cse-pi-limit-")); const source = join(base, "source"); const scratch = join(base, "scratch"); await mkdir(source); await mkdir(scratch); try { assert.equal((await runSandbox("sleep 10", source, scratch, 50, 1024)).evidence.timed_out, true); assert.equal((await runSandbox("yes", source, scratch, 5000, 64)).evidence.output_limited, true); } finally { await rm(base, { recursive: true, force: true }); } });
test("Bubblewrap cancellation kills the process group", async () => { const base = await mkdtemp(join(tmpdir(), "cse-pi-cancel-")); const source = join(base, "source"); await mkdir(source); const controller = new AbortController(); setTimeout(() => controller.abort(), 30); try { const result = await runSandbox("sleep 10 & wait", source, join(base, "scratch"), 5000, 1024, controller.signal); assert.notEqual(result.evidence.exit_code, 0); } finally { await rm(base, { recursive: true, force: true }); } });
test("Bubblewrap scrubs supervisor secrets from environment and proc", async () => { const base = await mkdtemp(join(tmpdir(), "cse-pi-env-")); const source = join(base, "source"); await mkdir(source); const prior = process.env.CSE_PI_SYNTHETIC_SECRET; process.env.CSE_PI_SYNTHETIC_SECRET = "do-not-leak"; try { const result = await runSandbox("test -z \"$CSE_PI_SYNTHETIC_SECRET\"; ! grep -a -q CSE_PI_SYNTHETIC_SECRET /proc/1/environ; test ! -e /home/user/.ssh", source, join(base, "scratch"), 3000, 1024); assert.equal(result.evidence.exit_code, 0); } finally { if (prior === undefined) delete process.env.CSE_PI_SYNTHETIC_SECRET; else process.env.CSE_PI_SYNTHETIC_SECRET = prior; await rm(base, { recursive: true, force: true }); } });
test("workspace file checks reject symlinked ancestor components", async () => { const base = await mkdtemp(join(tmpdir(), "cse-pi-link-")); const root = join(base, "root"); const outside = join(base, "outside"); await mkdir(root); await mkdir(outside); await writeFile(join(outside, "input"), "x"); await symlink(outside, join(root, "linked")); try { await assert.rejects(() => safeRegularFile(root, "linked/input"), /symlink path component/); } finally { await rm(base, { recursive: true, force: true }); } });
test("run-local scratch persists across sandbox invocations", async () => { const base = await mkdtemp(join(tmpdir(), "cse-pi-scratch-")); const source = join(base, "source"); const scratch = join(base, "scratch"); await mkdir(source); try { assert.equal((await runSandbox("printf data > /scratch/result.txt", source, scratch, 3000, 1024)).evidence.exit_code, 0); const result = await runSandbox("cat /scratch/result.txt", source, scratch, 3000, 1024); assert.equal(result.output, "data"); assert.equal(result.evidence.exit_code, 0); } finally { await rm(base, { recursive: true, force: true }); } });
test("run-local scratch writes remain bounded", async () => { const base = await mkdtemp(join(tmpdir(), "cse-pi-scratch-limit-")); const source = join(base, "source"); const scratch = join(base, "scratch"); await mkdir(source); try { const result = await runSandbox("dd if=/dev/zero of=/scratch/too-big bs=1048576 count=2", source, scratch, 3000, 1024); assert.notEqual(result.evidence.exit_code, 0); assert.match(result.output, /No space left on device/); } finally { await rm(base, { recursive: true, force: true }); } });
test("run-local scratch aggregate capacity stops multi-file overflow", async () => { const base = await mkdtemp(join(tmpdir(), "cse-pi-scratch-aggregate-")); const source = join(base, "source"); const scratch = join(base, "scratch"); await mkdir(source); try { const result = await runSandbox("dd if=/dev/zero of=/scratch/a bs=524288 count=1 status=none; dd if=/dev/zero of=/scratch/b bs=524288 count=1 status=none; dd if=/dev/zero of=/scratch/c bs=524288 count=1 status=none", source, scratch, 3000, 1024); assert.notEqual(result.evidence.exit_code, 0); assert.equal(result.evidence.scratch_limited, true); const sizes = await Promise.all(["a", "b", "c"].map(async name => { try { return (await stat(join(scratch, name))).size; } catch { return 0; } })); const total = sizes.reduce((sum, size) => sum + size, 0); assert.ok(total <= 1024 * 1024); assert.equal(result.evidence.scratch_bytes, total); } finally { await rm(base, { recursive: true, force: true }); } });
test("retained command evidence is byte-exact", async () => { const base = await mkdtemp(join(tmpdir(), "cse-pi-bytes-")); const source = join(base, "source"); const scratch = join(base, "scratch"); const evidenceDir = join(base, "command-evidence"); await mkdir(source); try { const evidence: unknown[] = []; const tool = safeCommandTool(source, scratch, 3000, 1024, evidence, evidenceDir); await tool.execute("binary", { command: "printf '\\377'" }, undefined); const bytes = await readFile(join(evidenceDir, "command-0.out")); assert.deepEqual(bytes, Buffer.from([0xff])); const item = evidence[0] as { output_bytes: number; output_sha256: string; output_path: string }; assert.equal(item.output_bytes, 1); assert.equal(item.output_sha256, createHash("sha256").update(bytes).digest("hex")); assert.equal(item.output_path, "command-evidence/command-0.out"); } finally { await rm(base, { recursive: true, force: true }); } });
test("trusted command evidence cannot be overwritten from candidate scratch", async () => { const base = await mkdtemp(join(tmpdir(), "cse-pi-evidence-")); const source = join(base, "source"); const scratch = join(base, "scratch"); const evidenceDir = join(base, "command-evidence"); await mkdir(source); try { const evidence: unknown[] = []; const tool = safeCommandTool(source, scratch, 3000, 1024, evidence, evidenceDir); await tool.execute("first", { command: "printf original" }, undefined); const retained = join(evidenceDir, "command-0.out"); await tool.execute("second", { command: "printf altered > /scratch/command-0.out; rm -f /scratch/command-0.out" }, undefined); const bytes = await readFile(retained); assert.equal(bytes.toString(), "original"); assert.equal((evidence[0] as { output_sha256: string }).output_sha256, createHash("sha256").update(bytes).digest("hex")); await assert.rejects(() => readFile(join(scratch, "command-0.out")), /ENOENT/); } finally { await rm(base, { recursive: true, force: true }); } });
test("scoped workspace mounts allow only assigned files", async () => { const base = await mkdtemp(join(tmpdir(), "cse-pi-workspace-scope-")); const source = join(base, "source"); await mkdir(source); await writeFile(join(source, "allowed.txt"), "before"); await writeFile(join(source, "forbidden.txt"), "safe"); try { const result = await runSandbox("printf changed > /workspace/allowed.txt; printf denied > /workspace/forbidden.txt", source, join(base, "scratch"), 3000, 4096, undefined, { writablePaths: ["allowed.txt"], workspaceBytes: 4096 }); assert.notEqual(result.evidence.exit_code, 0); assert.equal(await readFile(join(source, "allowed.txt"), "utf8"), "changed"); assert.equal(await readFile(join(source, "forbidden.txt"), "utf8"), "safe"); assert.equal(result.evidence.workspace_limited, false); } finally { await rm(base, { recursive: true, force: true }); } });
test("scoped workspace mounts enforce aggregate capacity", async () => { const base = await mkdtemp(join(tmpdir(), "cse-pi-workspace-limit-")); const source = join(base, "source"); await mkdir(join(source, "out"), { recursive: true }); try { const result = await runSandbox("dd if=/dev/zero of=/workspace/out/a bs=512 count=1 status=none; dd if=/dev/zero of=/workspace/out/b bs=512 count=1 status=none; dd if=/dev/zero of=/workspace/out/c bs=512 count=1 status=none", source, join(base, "scratch"), 3000, 4096, undefined, { writablePaths: ["out"], workspaceBytes: 1024 }); assert.notEqual(result.evidence.exit_code, 0); assert.ok((result.evidence.workspace_bytes ?? 0) <= 1024); } finally { await rm(base, { recursive: true, force: true }); } });

test("scoped workspace mounts deny unassigned creates at execution", async () => {
  const base = await mkdtemp(join(tmpdir(), "cse-pi-workspace-exact-"));
  const source = join(base, "source");
  await mkdir(join(source, "parent"), { recursive: true });
  await mkdir(join(source, "out"), { recursive: true });
  await writeFile(join(source, "parent", "allowed.txt"), "before");
  try {
    const exact = await runSandbox("printf outside > /workspace/not-permitted; cat /workspace/not-permitted", source, join(base, "scratch-exact"), 3000, 4096, undefined, { writablePaths: ["parent/allowed.txt"], workspaceBytes: 4096 });
    assert.notEqual(exact.evidence.exit_code, 0);
    assert.doesNotMatch(exact.output, /outside/);
    const sibling = await runSandbox("printf sibling > /workspace/parent/sibling.txt", source, join(base, "scratch-sibling"), 3000, 4096, undefined, { writablePaths: ["parent/allowed.txt"], workspaceBytes: 4096 });
    assert.notEqual(sibling.evidence.exit_code, 0);
    const directory = await runSandbox("printf child > /workspace/out/child.txt; printf sibling > /workspace/sibling.txt", source, join(base, "scratch-directory"), 3000, 4096, undefined, { writablePaths: ["out"], workspaceBytes: 4096 });
    assert.notEqual(directory.evidence.exit_code, 0);
    assert.equal(await readFile(join(source, "out", "child.txt"), "utf8"), "child");
    await assert.rejects(() => readFile(join(source, "sibling.txt"), "utf8"), /ENOENT/);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});

test("scoped file mounts enforce their aggregate quota", async () => {
  const base = await mkdtemp(join(tmpdir(), "cse-pi-workspace-file-limit-"));
  const source = join(base, "source");
  await mkdir(source);
  await writeFile(join(source, "allowed.txt"), "");
  try {
    const result = await runSandbox("dd if=/dev/zero of=/workspace/allowed.txt bs=2048 count=1 status=none", source, join(base, "scratch"), 3000, 4096, undefined, { writablePaths: ["allowed.txt"], workspaceBytes: 1024 });
    assert.notEqual(result.evidence.exit_code, 0);
    assert.equal(result.evidence.workspace_limited, true);
    assert.ok((result.evidence.workspace_bytes ?? 0) <= 1024);
  } finally {
    await rm(base, { recursive: true, force: true });
  }
});
