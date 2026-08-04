import assert from "node:assert/strict";
import test from "node:test";
import plan from "../plugin/cleanup-plan.js";

test("cleanup plan separates automatic and manual assignments", () => {
  const report = plan.summarizeRows([
    { name: "★", type: 0, count: 2 },
    { name: "Review", type: 0, count: 1 },
    { name: "Machine Learning", type: 0, count: 3 },
    { name: "generated", type: 1, count: 9 },
    { name: "unmapped manual", type: 0, count: 4 }
  ]);

  assert.equal(report.manualAssignments, 10);
  assert.equal(report.automaticAssignments, 9);
  assert.deepEqual(report.mappings, [
    { oldName: "★", newName: "priority:key", assignments: 2 },
    { oldName: "Review", newName: "role:review", assignments: 1 },
    { oldName: "Machine Learning", newName: "method:machine-learning", assignments: 3 }
  ]);
  assert.deepEqual(report.unexpectedManualTags, ["unmapped manual"]);
});

test("configuration exposes explicit confirmation tokens", () => {
  const config = plan.getConfig();
  assert.equal(config.applyToken, "ZOTERO-WIKI-APPLY-v1");
  assert.equal(config.searchToken, "ZOTERO-WIKI-SEARCHES-v1");
  assert.equal(config.workflowSearches.length, 4);
});
