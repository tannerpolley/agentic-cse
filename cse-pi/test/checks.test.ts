import assert from "node:assert/strict";
import { rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";
import { runCheck, shellQuote } from "../src/checks.ts";
import { digest, fixture } from "./build-fixture.ts";

test("scientific checks reject nonfinite and stale input", async () => {
  const data = await fixture(); const options = { commonGitDir: join(data.source, ".git"), dependencies: [] };
  try {
    const check = { id: "x", kind: "json" as const, path: "x.json", sha256: digest('{"x":1e999}') };
    await writeFile(join(data.source, check.path), '{"x":1e999}');
    assert.match((await runCheck(check, data.source, 3000, 4096, undefined, options, async () => null)).detail, /nonfinite/);
    await writeFile(join(data.source, check.path), '{"x":1}');
    assert.match((await runCheck(check, data.source, 3000, 4096, undefined, options, async () => null)).detail, /stale/);
  } finally { await rm(data.base, { recursive: true, force: true }); }
});
test("scientific-check paths are shell-quoted", async () => {
  const data = await fixture(); const options = { commonGitDir: join(data.source, ".git"), dependencies: [] };
  try {
    const path = "literal-$(exit 1).json"; const body = '{"ok":true}'; await writeFile(join(data.source, path), body);
    assert.equal(shellQuote("a'b"), "'a'\"'\"'b'");
    assert.equal((await runCheck({ id: "quoted", kind: "json", path, sha256: digest(body) }, data.source, 3000, 4096, undefined, options, async () => null)).ok, true);
  } finally { await rm(data.base, { recursive: true, force: true }); }
});
