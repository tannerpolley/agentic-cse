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
  let pendingTranslation = null;
  class Search {
    setSearch(search) { this.search = search; }
    setIdentifier(identifier) { this.identifier = identifier; }
    setTranslator(id) { this.translatorID = id; }
    async translate(options) {
      calls.push({ search: this.search, identifier: this.identifier, translatorID: this.translatorID, options });
      if (pendingTranslation) await pendingTranslation;
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

  let release;
  pendingTranslation = new Promise(resolve => { release = resolve; });
  const running = call({ identifier: "10.1234/example", mode: "apply" });
  const count = calls.length;
  const busy = await call({ identifier: "10.1234/example", mode: "apply" });
  assert.equal(busy.status, 409);
  assert.equal(busy.body.error, "metadata_acquisition_busy");
  assert.equal(calls.length, count);
  release();
  assert.equal((await running).status, 200);
  pendingTranslation = null;
  assert.equal((await call({ identifier: "10.1234/example" })).status, 200);

  let reject;
  pendingTranslation = new Promise((_resolve, fail) => { reject = fail; });
  const failing = call({ identifier: "10.1234/example" });
  assert.equal((await call({ identifier: "10.1234/example" })).status, 409);
  reject(new Error("native translation failure"));
  assert.equal((await failing).status, 500);
  pendingTranslation = null;
  assert.equal((await call({ identifier: "10.1234/example" })).status, 200);
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

test("Connector finalization restores the existing master after automatic duplicate merging", async () => {
  const { readFileSync } = await import("node:fs");
  const vm = await import("node:vm");
  for (const duplicate of [true, false]) {
    const items = new Map();
    const erased = [];
    const collection = { id: 9, key: "TESTCOLL", name: "Test", libraryID: 1 };
    const parent = (id, key) => ({
      id, key, libraryID: 1, deleted: false, collections: [], isRegularItem: () => true,
      getField: field => field === "DOI" ? "10.1016/test" : "Paper",
      toJSON: () => ({ title: "Paper", DOI: "10.1016/test" }),
      getAttachments: () => [...items.values()].filter(i => i.parentID === id).map(i => i.id),
      getNotes: () => [], addToCollection(target) { this.collections.push(target); }, save: async () => {},
      erase: async () => { erased.push(key); items.delete(id); }
    });
    const fresh = parent(2, "FRESH");
    const old = parent(1, "EXISTING");
    // Zoplicate's configured "keep" action has merged the old item into the new one.
    old.deleted = duplicate;
    items.set(2, fresh);
    if (duplicate) items.set(1, old);
    const pdf = { id: 3, key: "PDFKEY", parentID: 2, attachmentContentType: "application/pdf", isRegularItem: () => false, save: async () => {} };
    items.set(3, pdf);
    const Zotero = {
      Libraries: { userLibraryID: 1 }, Collections: { getByLibrary: () => [collection] },
      Utilities: { cleanDOI: value => value }, ItemFields: { getID: field => field },
      DB: { queryAsync: async () => [...items.values()].filter(i => i.isRegularItem()).map(i => ({ itemID: i.id, value: "Paper" })),
        executeTransaction: async fn => fn() },
      Items: { getAsync: async id => Array.isArray(id) ? id.map(i => items.get(i)) : items.get(id),
        getByLibraryAndKey: (_, key) => [...items.values()].find(i => i.key === key),
        merge: async (master, others) => {
          assert.equal(master, old);
          assert.deepEqual(Array.from(others), [fresh]);
          for (const other of others) {
            for (const id of other.getAttachments()) items.get(id).parentID = master.id;
            other.deleted = true;
          }
        } },
      Server: { Endpoints: {}, Connector: { SessionManager: { get: id => id === "SESSION" && { _items: { fakeID: fresh } } } } },
      Notifier: { registerObserver: () => 1 }
    };
    const context = vm.createContext({ Zotero, Services: {}, Components: {} });
    for (const name of ["cleanup-plan.js", "organize-plan.js", "zotero-companion.js"])
      vm.runInContext(readFileSync(new URL(`../zotero-plugin/${name}`, import.meta.url), "utf8"), context);
    vm.runInContext("ZoteroCompanion.start()", context);
    const Endpoint = Zotero.Server.Endpoints["/zotero-companion/acquire-connector"];
    const [status, , raw] = await new Endpoint().init({ data: { mode: "apply", session_id: "SESSION", item_key: duplicate ? old.key : null, collection: "TESTCOLL", doi: "10.1016/test" } });
    assert.equal(status, 200, raw);
    const result = JSON.parse(raw);
    assert.equal(result.item_key, duplicate ? "EXISTING" : "FRESH");
    assert.equal(result.attachment_key, "PDFKEY");
    assert.equal(pdf.parentID, duplicate ? 1 : 2);
    assert.equal((duplicate ? old : fresh).deleted, false, "the surviving parent must be active");
    assert.ok((duplicate ? old : fresh).collections.includes(9));
    assert.deepEqual(erased, duplicate ? ["FRESH"] : []);
    assert.equal([...items.values()].filter(i => i.isRegularItem()).length, 1);
  }
});

test("Connector worker prevents native backoff, challenge bypass and later requests after a hard stop", async () => {
  const { readFileSync } = await import("node:fs");
  const vm = await import("node:vm");
  const source = readFileSync(new URL("../src/zotero_companion/agent_browser.py", import.meta.url), "utf8");
  const setup = source.split('WORKER_SETUP = r"""')[1].split('"""')[0];
  for (const response of [
    { status: 429, response: "quota" },
    { status: 200, response: "<title>Just a moment</title>" },
    { status: 200, response: new TextEncoder().encode("HTML instead of PDF").buffer },
    { status: 200, response: new TextEncoder().encode("%PDF-1.7").buffer },
    { status: 503, response: "Temporary", getResponseHeader: () => "5" }
  ]) {
    let requests = 0;
    const event = { addListener() {}, removeListener() {} };
    const Zotero = {
      version: "5.0.217", initDeferred: { promise: Promise.resolve() },
      Connector: { checkIsOnline: async () => true },
      HTTP: { _requestFetch: async (_m, _u, options) => { requests++; assert.equal(options.maxBackoff, 0); return { ...response, responseURL: "https://cdn.publisher.example/paper.pdf" }; },
        StatusError: class extends Error { constructor(response) { super("HTTP status error"); this.retryAfter = response.getResponseHeader?.("Retry-After"); } } },
      ItemSaver: { saveAttachmentToZotero: async () => {} },
      Messaging: { sendMessage() {} },
      BotBypass: { bypassAmazonCaptcha() { throw Error("Must never run"); }, passJSDetectionViaHiddenIframe() {}, passJSDetectionViaWindowPrompt() {} }
    };
    const context = vm.createContext({ Zotero, URL, ArrayBuffer, Uint8Array, TextDecoder,
      chrome: { runtime: { id: "official-connector" }, tabs: { remove: async () => {}, onUpdated: event }, webRequest: { onHeadersReceived: event, onErrorOccurred: event }, declarativeNetRequest: { updateSessionRules: async () => {} } } });
    await vm.runInContext(setup, context);
    await Zotero.HTTP._requestFetch("GET", "chrome-extension://official-connector/schema.json", { successCodes: false });
    assert.equal(context.cseAcquire.stop, null);
    requests = 0;
    const declaredURL = response.response instanceof ArrayBuffer && new TextDecoder().decode(response.response).startsWith("%PDF") ? "http://publisher.example/paper.pdf" : "https://publisher.example/paper.pdf";
    await Zotero.ItemSaver.saveAttachmentToZotero({ url: declaredURL, mimeType: "application/pdf" });
    const fetch = () => Zotero.HTTP._requestFetch("GET", declaredURL, { successCodes: response.status === 503 ? null : false, maxBackoff: 10 });
    if (response.status === 503) {
      context.cseAcquire.pdfs.clear();
      const error = await fetch().catch(error => error);
      assert.equal(error.retryAfter, undefined);
      assert.equal(context.cseAcquire.stop, null);
      assert.equal(requests, 1);
    } else if (response.response instanceof ArrayBuffer && new TextDecoder().decode(response.response).startsWith("%PDF")) {
      await fetch();
      assert.equal(context.cseAcquire.stop, null);
      assert.throws(() => Zotero.BotBypass.passJSDetectionViaWindowPrompt("https://publisher.example/paper.pdf"));
      assert.equal(context.cseAcquire.stop.cooldown, true);
    } else {
      await assert.rejects(fetch());
      assert.equal(context.cseAcquire.stop.host, "cdn.publisher.example");
      assert.equal(context.cseAcquire.stop.cooldown, response.status === 429 || typeof response.response === "string");
      await assert.rejects(fetch());
      assert.equal(requests, 1);
    }
    await context.cseAcquire.clean();
  }
});

test("Connector attempt waits for native completion after a broadcast returns early", async () => {
  const { readFileSync } = await import("node:fs");
  const vm = await import("node:vm");
  const source = readFileSync(new URL("../src/zotero_companion/agent_browser.py", import.meta.url), "utf8");
  const setup = source.split('WORKER_SETUP = r"""')[1].split('"""')[0];
  const save = source.split('WORKER_SAVE = r"""')[1].split('"""')[0];
  let completed = false;
  let saves = 0;
  const tab = { id: 5, url: "https://publisher.example/paper", status: "complete" };
  const event = { addListener() {}, removeListener() {} };
  const Zotero = {
    version: "5.0.217", initDeferred: { promise: Promise.resolve() },
    Connector: { checkIsOnline: async () => true },
    HTTP: { _requestFetch() {} }, ItemSaver: { saveAttachmentToZotero() {} },
    BotBypass: {}, Messaging: { sendMessage() {} },
    Connector_Browser: {
      getTabInfo: () => ({ translators: [{ itemType: "journalArticle" }] }),
      saveWithTranslator: async () => {
        saves++;
        // A different frame responds first; the actual save finishes later.
        setTimeout(() => { completed = true; Zotero.Messaging.sendMessage("progressWindow.done", [true], tab); }, 20);
      }
    }
  };
  const context = vm.createContext({ Zotero, setTimeout, URL, ArrayBuffer, Uint8Array, TextDecoder,
    chrome: { tabs: { get: async () => tab, remove: async () => {}, onUpdated: event },
      webRequest: { onHeadersReceived: event, onErrorOccurred: event },
      declarativeNetRequest: { updateSessionRules: async () => {} } } });
  await vm.runInContext(setup, context);
  context.cseAcquire.tab = 5;
  await vm.runInContext(save, context);
  assert.equal(completed, true);
  assert.equal(saves, 1);
  assert.equal(context.cseAcquire.done, true);
  await context.cseAcquire.clean();
});
