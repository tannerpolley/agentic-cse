import assert from "node:assert/strict";
import test from "node:test";
import plan from "../zotero-plugin/cleanup-plan.js";

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
  assert.equal(config.applyToken, "ZOTERO-COMPANION-APPLY-v1");
  assert.equal(config.searchToken, "ZOTERO-COMPANION-SEARCHES-v1");
  assert.equal(config.workflowSearches.length, 4);
});

test("project organize steps stay inside the registered project tree", async () => {
  const { resolvePlan } = (await import("../zotero-plugin/organize-plan.js")).default;
  const registry = {
    root_collection: "ROOT0001",
    projects: { mea: { collection: "PROJ0001" }, li: { collection: "PROJ0002" } }
  };
  const collections = [
    { key: "ROOT0001", name: "Project Libraries", parent: "" },
    { key: "PROJ0001", name: "MEA", parent: "ROOT0001" },
    { key: "DATA0001", name: "Data", parent: "PROJ0001" },
    { key: "PROJ0002", name: "Lithium", parent: "ROOT0001" }
  ];
  const ok = resolvePlan({ project: "mea", operations: [
    { op: "create", id: "vle", name: "VLE", parent: "DATA0001" },
    { op: "add", collection: "@vle", items: ["ITEM0001"] },
    { op: "move", collection: "@vle", parent: "PROJ0001" }
  ] }, registry, collections);
  assert.deepEqual(ok.errors, []);
  assert.deepEqual(ok.steps.map(step => step.path), ["MEA / Data / VLE", "MEA / Data / VLE", "MEA / VLE"]);

  const outside = [
    { project: "mea", operations: [{ op: "add", collection: "PROJ0002", items: ["ITEM0001"] }] },
    { project: "mea", operations: [{ op: "move", collection: "DATA0001", parent: "ROOT0001" }] },
    { project: "mea", operations: [{ op: "move", collection: "PROJ0001", parent: "DATA0001" }] },
    { project: "nope", operations: [{ op: "rename", collection: "PROJ0001", name: "x" }] },
    { operations: [{ op: "rename", collection: "PROJ0001", name: "x" }] },
    { operations: [{ op: "create", name: "New", parent: "PROJ0001" }] }
  ];
  for (const request of outside) {
    assert.notDeepEqual(resolvePlan(request, registry, collections).errors, [], JSON.stringify(request));
  }
  assert.deepEqual(resolvePlan({ operations: [{ op: "create", name: "New project" }] }, registry, collections).errors, []);
});

test("project-organize endpoint previews by default and writes only with the token", async () => {
  const { readFileSync } = await import("node:fs");
  const vm = await import("node:vm");
  const files = {};
  // No Zotero.Collection and no collection write methods: any write attempt throws.
  const Zotero = {
    Libraries: { userLibraryID: 1 },
    Server: { Endpoints: {} },
    Notifier: { registerObserver: () => "observer", unregisterObserver() {} },
    File: { getContentsAsync: async path => { if (!(path in files)) throw new Error("absent"); return files[path]; } },
    Collections: { getByLibrary: () => [
      { key: "ROOT0001", name: "Root", parentKey: false },
      { key: "PROJ0001", name: "MEA", parentKey: "ROOT0001" }
    ] },
    Items: { getByLibraryAndKey: (_library, key) => key === "ITEM0001" && { id: 1, isRegularItem: () => true } }
  };
  const context = vm.createContext({ Zotero, Services: { env: { get: () => "/cfg" } }, Components: {} });
  for (const name of ["cleanup-plan.js", "organize-plan.js", "zotero-companion.js"]) {
    vm.runInContext(readFileSync(new URL(`../zotero-plugin/${name}`, import.meta.url), "utf8"), context);
  }
  vm.runInContext("ZoteroCompanion.start()", context);
  const Endpoint = Zotero.Server.Endpoints["/zotero-companion/project-organize"];
  const call = async data => {
    const [status, , body] = await new Endpoint().init({ data });
    return { status, body: JSON.parse(body) };
  };
  const plan = { project: "mea", operations: [{ op: "add", collection: "PROJ0001", items: ["ITEM0001"] }] };

  assert.equal((await call(plan)).status, 409);
  files["/cfg/zotero-companion/projects.json"] = JSON.stringify({
    root_collection: "ROOT0001", projects: { mea: { collection: "PROJ0001" } }
  });
  const preview = await call(plan);
  assert.equal(preview.status, 200);
  assert.equal(preview.body.mode, "dry-run");
  assert.equal((await call({ ...plan, mode: "apply" })).status, 428);
  const badItem = { project: "mea", operations: [{ op: "add", collection: "PROJ0001", items: ["NOTANITM"] }] };
  assert.equal((await call(badItem)).status, 422);
});
