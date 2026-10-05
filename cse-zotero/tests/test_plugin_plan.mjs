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

test("metadata acquisition previews without writes and applies one attachment-free parent", async () => {
  const { readFileSync } = await import("node:fs");
  const vm = await import("node:vm");
  const collection = { id: 2, key: "COLL0001", name: "Papers", libraryID: 1 };
  const calls = [];
  const saved = [];
  class Search {
    setSearch(search) { this.search = search; }
    setIdentifier(identifier) { this.identifier = identifier; }
    setTranslator(id) { this.translatorID = id; }
    async translate(options) {
      calls.push({ search: this.search, identifier: this.identifier, translatorID: this.translatorID, options });
      return [{ toJSON: () => ({
        itemType: "journalArticle", title: "An Example Paper", DOI: "10.1234/example",
        attachments: [{ title: "publisher PDF" }]
      }) }];
    }
  }
  class Item {
    fromJSON(data) { this.data = { ...data }; }
    toJSON() { return { ...this.data }; }
    isRegularItem() { return this.data.itemType === "journalArticle"; }
    setCollections(ids) { this.collections = ids; }
    async saveTx() { this.key = "NEWITEM1"; saved.push(this); }
  }
  const Zotero = {
    Libraries: { userLibraryID: 1 }, Server: { Endpoints: {} },
    Notifier: { registerObserver: () => "observer", unregisterObserver() {} },
    Collections: { getByLibrary: () => [collection] },
    getActiveZoteroPane: () => ({ getSelectedLibraryIDs: () => [1], getSelectedCollections: () => [collection] }),
    Utilities: {
      extractIdentifiers: text => text === "10.1234/example" ? [{ DOI: "10.1234/example" }] : [],
      cleanDOI: text => text.toLowerCase()
    },
    Translate: { Search }, Item, ItemFields: { getID: field => field === "DOI" ? 1 : 2 },
    DB: { queryAsync: async (sql, params) => {
      assert.ok(Array.isArray(params), "Zotero query parameters must be an array");
      assert.equal(params.length, (sql.match(/\?/g) || []).length);
      return [];
    } },
    Items: { getAsync: async () => false }
  };
  const context = vm.createContext({ Zotero, Services: {}, Components: {} });
  for (const name of ["cleanup-plan.js", "organize-plan.js", "zotero-companion.js"])
    vm.runInContext(readFileSync(new URL(`../zotero-plugin/${name}`, import.meta.url), "utf8"), context);
  vm.runInContext("ZoteroCompanion.start()", context);
  const Endpoint = Zotero.Server.Endpoints["/zotero-companion/acquire-metadata"];
  const call = async data => {
    const [status, , body] = await new Endpoint().init({ data });
    return { status, body: JSON.parse(body) };
  };

  const preview = await call({ identifier: "10.1234/example", collection: "Papers" });
  assert.equal(preview.status, 200);
  assert.equal(preview.body.mode, "dry-run");
  assert.equal(preview.body.existing, false);
  assert.equal(preview.body.metadata.title, "An Example Paper");
  assert.equal(preview.body.metadata.attachments, undefined);
  assert.equal(calls[0].translatorID, "0a61e167-de9a-4f93-a68a-628b48855909");
  assert.equal(calls[0].options.libraryID, false);
  assert.equal(calls[0].options.saveAttachments, false);
  assert.equal(saved.length, 0);

  const applied = await call({ identifier: "10.1234/example", collection: "Papers", mode: "apply" });
  assert.equal(applied.status, 200);
  assert.equal(applied.body.existing, false);
  assert.equal(applied.body.item_key, "NEWITEM1");
  assert.equal(applied.body.collection_key, "COLL0001");
  assert.equal(saved.length, 1);
  assert.equal(saved[0].data.attachments, undefined);
  assert.equal(saved[0].collections.length, 1);
  assert.equal(saved[0].collections[0], 2);
  Zotero.DB.queryAsync = async (_sql, params) => params[1] === 2
    ? [{ itemID: 99, value: " AN EXAMPLE PAPER " }] : [];
  Zotero.Items.getAsync = async () => ({ key: "EXISTING", isRegularItem: () => true });
  const duplicate = await call({ identifier: "10.1234/example", mode: "apply" });
  assert.equal(duplicate.body.item_key, "EXISTING");
  assert.equal(duplicate.body.existing, true);
  assert.equal(saved.length, 1);
});

test("attachment acquisition validates PDF bytes and dry-run does not import", async () => {
  const { readFileSync } = await import("node:fs");
  const vm = await import("node:vm");
  let imported = 0;
  const parent = { id: 5, key: "PARENT01", isRegularItem: () => true };
  const Zotero = {
    Libraries: { userLibraryID: 1 }, Server: { Endpoints: {} },
    Notifier: { registerObserver: () => "observer", unregisterObserver() {} },
    Items: { getByLibraryAndKey: (_libraryID, key) => key === parent.key && parent },
    Attachments: { importFromFile: async () => { imported++; return { key: "ATTACH01" }; } }
  };
  const context = vm.createContext({ Zotero, Services: {}, Components: {}, atob });
  for (const name of ["cleanup-plan.js", "organize-plan.js", "zotero-companion.js"])
    vm.runInContext(readFileSync(new URL(`../zotero-plugin/${name}`, import.meta.url), "utf8"), context);
  vm.runInContext("ZoteroCompanion.start()", context);
  const Endpoint = Zotero.Server.Endpoints["/zotero-companion/acquire-attachment"];
  const call = async data => {
    const [status, , body] = await new Endpoint().init({ data });
    return { status, body: JSON.parse(body) };
  };
  const pdf = Buffer.from("%PDF-1.7\n").toString("base64");

  assert.equal((await call({ item_key: parent.key, pdf_base64: "not-base64" })).status, 422);
  const preview = await call({ item_key: parent.key, pdf_base64: pdf });
  assert.equal(preview.status, 200);
  assert.equal(preview.body.byte_length, 9);
  // A normal multi-megabyte PDF must not overflow a base64-validation regexp.
  const largePDF = Buffer.concat([Buffer.from("%PDF-1.7\n"), Buffer.alloc(4 * 1024 * 1024, 0x80)]);
  const largePreview = await call({ item_key: parent.key, pdf_base64: largePDF.toString("base64") });
  assert.equal(largePreview.status, 200);
  assert.equal(largePreview.body.byte_length, largePDF.length);
  assert.equal(imported, 0);
});

test("manifest has the fields Zotero 10 requires to install an add-on", async () => {
  const { readFileSync } = await import("node:fs");
  const manifest = JSON.parse(readFileSync(new URL("../zotero-plugin/manifest.json", import.meta.url), "utf8"));
  const zotero = manifest.applications.zotero;
  for (const field of ["id", "update_url", "strict_max_version"]) assert.ok(zotero[field], field);
});
