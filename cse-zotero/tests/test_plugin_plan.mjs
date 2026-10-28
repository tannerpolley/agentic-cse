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
  let noResults = false;
  class Search {
    setSearch(search) { this.search = search; }
    setIdentifier(identifier) { this.identifier = identifier; }
    setTranslator(id) { this.translatorID = id; }
    async translate(options) {
      calls.push({ search: this.search, identifier: this.identifier, translatorID: this.translatorID, options });
      if (pendingTranslation) await pendingTranslation;
      if (noResults) return [];
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
      extractIdentifiers: text => /^10\./.test(text) ? [{ DOI: text }] : [],
      cleanDOI: text => text.toLowerCase()
    },
    Translate: { Search }, Item, ItemFields: { getID: field => field === "DOI" ? 1 : 2 },
    DB: { queryAsync: async (sql, params) => {
      assert.ok(Array.isArray(params), "Zotero query parameters must be an array");
      assert.equal(params.length, (sql.match(/\?/g) || []).length);
      return [];
    } },
    Items: { getAsync: async () => false },
    File: { getContentsAsync: async path => {
      if (path.endsWith("elsevier-api-key")) return "test-secret-value\n";
      if (path.endsWith("wiley-tdm-token")) return "synthetic+secret/123\n";
      throw new Error("unconfigured");
    } }
  };
  const context = vm.createContext({ Zotero, Services: { dirsvc: { get: () => ({ path: "/home/test" }) } }, Components: { interfaces: {} } });
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

  const plus = await call({ identifier: "10.1021/je960141+" });
  assert.equal(plus.status, 200);
  // Reproduce Crossref REST's query construction: a literal + becomes a space.
  const query = new URLSearchParams("filter=doi:" + calls.at(-1).search.DOI);
  assert.equal(query.get("filter"), "doi:10.1021/je960141+");
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
  reject(new Error("native translation failure: test-secret-value api_key=unknown-secret Bearer bearer-secret\n" +
    "Authorization: Token token-secret\nAuthorization: Basic dXNlcjpwYXNz\n" +
    "https://example.test/?token=synthetic%2Bsecret%2F123"));
  const failure = await failing;
  assert.equal(failure.status, 500);
  assert.match(failure.body.message, /native translation failure/);
  assert.equal((failure.body.message.match(/Authorization: \[redacted\]/g) || []).length, 2);
  for (const secret of ["test-secret-value", "unknown-secret", "bearer-secret",
    "Token", "token-secret", "Basic", "dXNlcjpwYXNz", "synthetic%2Bsecret%2F123"])
    assert.ok(!JSON.stringify(failure.body).includes(secret));
  pendingTranslation = null;
  assert.equal((await call({ identifier: "10.1234/example" })).status, 200);
  assert.equal(saved.length, 1);

  noResults = true;
  const nonCrossref = await call({ identifier: "10.22034/ijche.2024.450400.1526" });
  assert.equal(nonCrossref.status, 500);
  assert.match(nonCrossref.body.message, /No metadata returned by translator/);
  assert.match(nonCrossref.body.message, /Hand off the DOI landing page to web translators/);
  assert.match(nonCrossref.body.message, /10\.22034\/ijche/);
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

import { readFileSync } from "node:fs";
import vm from "node:vm";
const load = (context, name) => vm.runInContext(readFileSync(new URL(`../zotero-plugin/${name}`, import.meta.url), "utf8"), context);
function desktopFixture() {
  let clock = 0;
  const calls = [], collection = { id: 2, key: "COLL", libraryID: 1 };
  class Item {
    constructor(key = "FRESH") { this.id = key === "OLD" ? 1 : 2; this.key = key; this.libraryID = 1; this.children = key === "OLD" ? [] : [3]; }
    isRegularItem() { return true; }
    toJSON() { return { itemType: "journalArticle", DOI: "10.1234/test", title: "Paper" }; }
    getField() { return "10.1234/test"; }
    fromJSON() {}
    setCollections() {}
    addToCollection(id) { calls.push(["collection", this.key, id]); }
    getAttachments() { return this.children; }
    _saveData(env) { return env.notifierData; }
    async saveTx() { this._saveData({ isNew: true, notifierData: {} }); }
    async eraseTx() { calls.push(["erase", this.key]); }
  }
  const fresh = new Item(), old = new Item("OLD"), pdf = { key: "PDF", attachmentContentType: "application/pdf" };
  const hooks = { onNotify: (...args) => calls.push(["linter", ...args]) };
  const actionManager = { dispatchActionByEvent: (...args) => calls.push(["actions", ...args]) };
  class Menu { queueAddedItems(ids) { calls.push(["attanger", ...ids]); } }
  const menu = new Menu();
  const Zotero = {
    Libraries: { userLibraryID: 1 }, Server: { Endpoints: {}, Connector: { SessionManager: { get: () => ({ _items: { fresh } }) } } },
    Notifier: { registerObserver: () => 1, unregisterObserver() {} }, Item,
    Collections: { getByLibrary: () => [collection] },
    getActiveZoteroPane: () => ({ getSelectedLibraryIDs: () => [1], getSelectedCollections: () => [collection] }),
    Utilities: { cleanDOI: s => s, extractIdentifiers: () => [{ DOI: "10.1234/test" }] },
    Translate: { Search: class { setSearch() {} setTranslator() {} async translate() { return [fresh]; } } },
    ItemFields: { getID: () => 1 }, DB: { queryAsync: async () => [] },
    Items: { getByLibraryAndKey: (_, key) => key === "OLD" ? old : null, getAsync: async () => [pdf],
      merge: async (parent, items) => { calls.push(["merge", parent.key, items[0].key]); parent.children.push(...items[0].children); } },
    Linter: { hooks }, ActionsTags: { api: { actionManager } }, ZoteroAttanger: { data: { menu } },
    File: { getContentsAsync: async () => '{"module_revision":19}' },
    ProgressWindow: function() { this.show = () => { calls.push(["popup"]); return true; }; this.close = () => calls.push(["close"]); }
  };
  const context = vm.createContext({ Zotero, Services: { dirsvc: { get: () => ({ path: "/home/test" }) } }, Components: { interfaces: {} },
    Date: class extends Date { static now() { return clock; } }, atob });
  for (const name of ["cleanup-plan.js", "organize-plan.js", "zotero-companion.js"]) load(context, name);
  context.ZoteroCompanion.start();
  const call = async (path, data) => JSON.parse((await new Zotero.Server.Endpoints["/zotero-companion/" + path]().init({ data }))[2]);
  const heartbeat = () => call("acquire-job", { action: "pickup", protocol: 1, compatible: true, version: "5.0.217", module_revision: 19 });
  return { call, heartbeat, calls, Zotero, fresh, old, context, now: () => clock, advance: ms => { clock += ms; } };
}
async function browserFixture(mode = "success") {
  const desktop = desktopFixture(), created = [], closed = [], native = [];
  await desktop.heartbeat();
  await desktop.call("acquire-job", { action: "submit", job: { id: "JOB", url: "https://paper.example/article" } });
  let headers, reads = 0, finish;
  const finished = new Promise(resolve => { finish = resolve; });
  const tab = { id: 2, url: "https://paper.example/article", status: "complete", title: "Paper" };
  const chrome = {
    windows: { getAll: async () => [], create: async options => { created.push(options); return { id: 10, tabs: [{ id: 1 }, tab] }; },
      remove: async id => { closed.push(id); } },
    tabs: { update: async (id, options) => { assert.equal(id, 2); assert.deepEqual({ ...options }, { active: true }); }, get: async () => {
      reads++;
      if (reads === 1) return { ...tab, url: "about:blank" };
      if (reads === 2 || mode === "429loading") {
        if (mode === "429loading") headers({ tabId: 2, type: "main_frame", statusCode: 429, responseHeaders: [] });
        return { ...tab, status: "loading" };
      }
      const challenge = mode === "persist" || mode === "clear" && desktop.now() < 5000;
      headers({ tabId: 2, type: "main_frame", statusCode: challenge ? 403 : 200,
        responseHeaders: challenge ? [{ name: "cf-mitigated", value: "challenge" }] : [] });
      return { ...tab, title: challenge ? "Just a moment" : "Paper" };
    } },
    webRequest: { onHeadersReceived: { addListener: fn => { headers = fn; } } },
    runtime: { onStartup: { addListener: fn => { assert.equal(typeof fn, "function"); } },
      getPlatformInfo: async () => ({}), reload: () => assert.fail("unexpected reload") },
    storage: { local: { get: async () => ({}), set: async () => {} } }
  };
  const Zotero = {
    version: "5.0.217", getExtensionURL: path => "chrome-extension://test/" + path, initDeferred: { promise: Promise.resolve() },
    logError: error => assert.fail(String(error)), Messaging: { sendMessage: async () => native.push("done") },
    Connector: { callMethod: async () => { native.push("saveItems"); return "native-result"; },
      saveSingleFile: async () => { native.push("snapshot"); return "native-snapshot"; } },
    BotBypass: { passJSDetectionViaWindowPrompt: async () => { native.push("prompt"); return "native-popup"; } },
    API: { authorize: async () => { native.push("authorize"); return "native-auth"; } },
    Connector_Browser: { openWindow: async () => { native.push("window"); return "native-window"; },
      getTabInfo: () => ({ translators: mode === "none" ? [] : [{ itemType: mode === "multiple" ? "multiple" : "journalArticle" }] }),
      saveWithTranslator: async (t, index, ...options) => {
        assert.equal(index, 0); assert.equal(options.length, 0);
        assert.equal(await Zotero.Connector.callMethod("saveItems", { sessionID: "SESSION" }, t), "native-result");
        if (mode === "prompt") await Zotero.BotBypass.passJSDetectionViaWindowPrompt("https://pdf.example/check", t);
        else if (mode === "window") await Zotero.Connector_Browser.openWindow("https://pdf.example/check", {}, t);
        // Same shape as messaging.js: a postReceive hook replaces the usual tab and frame arguments.
        else if (mode === "snapshot") assert.equal(await Zotero.Connector.saveSingleFile(
          ...await context.MESSAGES.Connector.saveSingleFile.background.postReceive([{ method: "saveSingleFile" }, {}], t, 0)), null);
        else if (mode === "auth") return Zotero.API.authorize().catch(() => Zotero.Messaging.sendMessage("progressWindow.done", [false], t));
        await Zotero.Messaging.sendMessage("progressWindow.done", [true], t);
      } }
  };
  const MESSAGES = { Connector: { saveSingleFile: { background: { postReceive: async args => args } } } };
  const context = vm.createContext({ Zotero, chrome, AbortSignal, MESSAGES, Date: class extends Date { static now() { return desktop.now(); } },
    setInterval() {}, setTimeout: (fn, ms) => { if (ms === 500) { desktop.advance(ms); queueMicrotask(fn); } },
    fetch: async (_, request) => {
      const data = JSON.parse(request.body), result = await desktop.call("acquire-job", data);
      if (data.action === "finish") finish(data.result);
      return { ok: true, json: async () => result };
    } });
  load(context, "connector-agent.js");
  return { outcome: await finished, desktop, created, closed, native, Zotero };
}

test("native save finishes with its session, closes the window and merges into the alive parent", async () => {
  const r = await browserFixture();
  assert.equal(r.outcome.ok, true); assert.equal(r.outcome.session_id, "SESSION");
  assert.deepEqual(r.native, ["saveItems", "done"]); assert.deepEqual(r.closed, [10]);
  assert.equal(r.created[0].state, "normal"); assert.equal(r.created[0].focused, false);
  assert.equal(r.created[0].url[1], "https://paper.example/article");
  const final = await r.desktop.call("acquire-connector", { mode: "apply", session_id: "SESSION", existing_key: "OLD", doi: "10.1234/test", collection: "COLL" });
  assert.equal(final.item_key, "OLD"); assert.equal(final.attachment_key, "PDF");
  assert.ok(r.desktop.calls.some(c => c.join() === "merge,OLD,FRESH"));
  assert.ok(r.desktop.calls.some(c => c.join() === "erase,FRESH"));
});

test("a page check waits until the job deadline; cleared checks continue the native save", async () => {
  const stopped = await browserFixture("persist"), cleared = await browserFixture("clear");
  assert.match(stopped.outcome.stop.reason, /job deadline/); assert.ok(stopped.desktop.now() >= 180000);
  assert.deepEqual(stopped.native, []); assert.deepEqual(stopped.closed, [10]);
  assert.equal(cleared.outcome.ok, true); assert.equal(cleared.outcome.stop, null);
});

test("a main-frame 429 stops at once, even while the page is still loading", async () => {
  const r = await browserFixture("429loading");
  assert.equal(r.outcome.stop.reason, "Publisher HTTP 429"); assert.ok(r.desktop.now() < 5000);
  assert.deepEqual(r.native, []); assert.deepEqual(r.closed, [10]);
});

test("an overdue job keeps running 15 seconds so the worker can report its own result", async () => {
  const r = desktopFixture();
  await r.heartbeat(); await r.call("acquire-job", { action: "submit", job: { id: "JOB" } }); await r.heartbeat();
  r.advance(180000 + 14000);
  assert.equal((await r.call("acquire-job", { action: "status" })).job.state, "running");
  r.advance(2000);
  assert.match((await r.call("acquire-job", { action: "status" })).job.result.error, /timed out/);
});

test("unsupported and multiple-item pages hand off without saving", async () => {
  for (const mode of ["none", "multiple"]) {
    const r = await browserFixture(mode);
    assert.match(r.outcome.handoff, mode === "none" ? /no Zotero translator for this page/ : /Multiple-item/);
    assert.deepEqual(r.native, []); assert.equal(r.outcome.stop, null);
  }
});

test("agent saves open the native check pop-up and skip the page snapshot", async () => {
  for (const [mode, call] of [["prompt", "prompt"], ["window", "window"]]) {
    const r = await browserFixture(mode);
    assert.equal(r.outcome.ok, true); assert.equal(r.outcome.stop, null);
    assert.deepEqual(r.native, ["saveItems", call, "done"]);
  }
  const r = await browserFixture("snapshot");
  assert.equal(r.outcome.ok, true); assert.deepEqual(r.native, ["saveItems", "done"]);
  assert.equal(await r.Zotero.Connector.saveSingleFile({}, {}, { id: 99 }), "native-snapshot");
});

test("no Zotero progress pop-up ever shows while the add-on runs; shutdown restores it", async () => {
  const r = desktopFixture();
  const popup = new r.Zotero.ProgressWindow({ closeOnClick: true });
  assert.equal(popup.show(), false); popup.close(); assert.deepEqual(r.calls, []);
  r.context.ZoteroCompanion.stop();
  assert.equal(new r.Zotero.ProgressWindow().show(), true); assert.deepEqual(r.calls, [["popup"]]);
});

test("the quiet window skips add-on hooks, expires and restores the native methods on shutdown", async () => {
  const r = desktopFixture(), z = r.Zotero;
  const dispatch = () => { z.Linter.hooks.onNotify("add", "item", [2]);
    z.ActionsTags.api.actionManager.dispatchActionByEvent(2, {}); z.ZoteroAttanger.data.menu.queueAddedItems([2]); };
  await r.heartbeat();
  await r.call("acquire-job", { action: "submit", job: { id: "JOB" } }); await r.heartbeat();
  dispatch(); assert.deepEqual(r.calls, []);
  assert.equal(r.fresh._saveData({ isNew: true, notifierData: {} }).skipSelect, true);
  r.advance(210001); dispatch(); assert.equal(r.calls.length, 3);
  assert.equal(r.fresh._saveData({ isNew: true, notifierData: {} }).skipSelect, undefined);
  await r.call("acquire-metadata", { identifier: "10.1234/test", mode: "apply" });
  dispatch(); assert.equal(r.calls.length, 3);
  r.advance(30001); dispatch(); assert.equal(r.calls.length, 6);
  r.context.ZoteroCompanion.stop(); dispatch(); assert.equal(r.calls.length, 9);
});

test("Zotero sign-in fallback during a job hands off without a window; outside a job it stays native", async () => {
  const r = await browserFixture("auth");
  assert.equal(r.outcome.ok, false); assert.match(r.outcome.handoff, /Zotero desktop was unreachable/);
  assert.ok(!r.native.includes("authorize")); assert.equal(r.created.length, 1);
  assert.equal(await r.Zotero.API.authorize(), "native-auth");
});
