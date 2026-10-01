import assert from "node:assert/strict";
import { DefaultResourceLoader, SessionManager, SettingsManager, createAgentSession } from "@earendil-works/pi-coding-agent";
import test from "node:test";
import { cseSubmitTool, safeCommandTool } from "../src/cse-extension.ts";
test("pinned Pi SDK loads only explicit worker tools", async () => {
  const loader = new DefaultResourceLoader({ cwd: process.cwd(), agentDir: "/tmp/cse-pi-sdk-test", noExtensions: true, noSkills: true, noPromptTemplates: true, noThemes: true, noContextFiles: true }); await loader.reload();
  const command = safeCommandTool(process.cwd(), () => 1000, 1024, { commonGitDir: process.cwd(), dependencies: [] }, new AbortController().signal, async result => result.evidence);
  const { session } = await createAgentSession({ cwd: process.cwd(), agentDir: "/tmp/cse-pi-sdk-test", noTools: "builtin", excludeTools: ["read", "bash", "edit", "write", "grep", "find", "ls"], customTools: [command, cseSubmitTool()], resourceLoader: loader, sessionManager: SessionManager.inMemory(), settingsManager: SettingsManager.inMemory() });
  try { session.setActiveToolsByName(["cse_submit_result", "cse_run_command"]); assert.deepEqual(session.getActiveToolNames().sort(), ["cse_run_command", "cse_submit_result"]); }
  finally { session.dispose(); }
});
