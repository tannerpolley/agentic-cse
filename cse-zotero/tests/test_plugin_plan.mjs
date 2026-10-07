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

test("Pre-save title match pins the master before Zoplicate trashes it, ignoring prior trash", async () => {
  const { readFileSync } = await import("node:fs");
  const vm = await import("node:vm");
  for (const duplicate of [true, false]) {
    const items = new Map();
    const erased = [];
    const collection = { id: 9, key: "TESTCOLL", name: "Test", libraryID: 1 };
    const parent = (id, key) => ({
      id, key, libraryID: 1, deleted: false, collections: [], isRegularItem: () => true,
      getField: field => field === "DOI" ? "" : "  Ｐaper   TITLE ",
      toJSON: () => ({ title: "  Ｐaper   TITLE ", DOI: "" }),
      getAttachments: () => [...items.values()].filter(i => i.parentID === id).map(i => i.id),
      getNotes: () => [], addToCollection(target) { this.collections.push(target); }, save: async () => {},
      erase: async () => { erased.push(key); items.delete(id); }
    });
    const fresh = parent(2, "FRESH");
    const old = parent(1, "EXISTING");
    const priorTrash = parent(4, "TRASH");
    priorTrash.deleted = true;
    items.set(4, priorTrash);
    if (duplicate) items.set(1, old);
    const pdf = { id: 3, key: "PDFKEY", parentID: 2, attachmentContentType: "application/pdf", isRegularItem: () => false, save: async () => {} };
    let session;
    const Zotero = {
      Libraries: { userLibraryID: 1 }, Collections: { getByLibrary: () => [collection] },
      Utilities: { cleanDOI: value => value }, ItemFields: { getID: field => field },
      DB: { queryAsync: async sql => {
          assert.match(sql, /NOT IN \(SELECT itemID FROM deletedItems\)/);
          return [...items.values()].filter(i => i.isRegularItem() && !i.deleted).map(i => ({ itemID: i.id, value: i.getField("title") }));
        },
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
      Server: { Endpoints: {}, Connector: { SessionManager: { get: id => id === "SESSION" && session } } },
      Notifier: { registerObserver: () => 1 }
    };
    const context = vm.createContext({ Zotero, Services: {}, Components: {}, URL });
    for (const name of ["cleanup-plan.js", "organize-plan.js", "public-url.js", "zotero-companion.js"])
      vm.runInContext(readFileSync(new URL(`../zotero-plugin/${name}`, import.meta.url), "utf8"), context);
    vm.runInContext("ZoteroCompanion.start()", context);
    const jobEndpoint = new Zotero.Server.Endpoints["/zotero-companion/acquire-job"]();
    const call = async data => { const [status, , raw] = await jobEndpoint.init({ data }); assert.equal(status, 200, raw); return JSON.parse(raw); };
    await call({ action: "pickup", protocol: 1, compatible: true });
    await call({ action: "submit", job: { id: "JOB", url: "https://publisher.example/paper" } });
    await call({ action: "pickup", protocol: 1, compatible: true });
    const prepared = await call({ action: "prepare", id: "JOB", session_id: "SESSION", metadata: { title: "paper title" } });
    assert.equal(prepared.existing_key, duplicate ? "EXISTING" : null);
    // The new native save now arrives, and Zoplicate keeps it and trashes the old master.
    items.set(2, fresh); items.set(3, pdf); old.deleted = duplicate;
    session = { _items: { fakeID: fresh } };
    await call({ action: "finish", id: "JOB", result: {} });
    assert.equal(session.cseExistingKey, duplicate ? "EXISTING" : null);
    await call({ action: "submit", job: { id: "NEXT", url: "https://publisher.example/next" } });
    const Endpoint = Zotero.Server.Endpoints["/zotero-companion/acquire-connector"];
    const [status, , raw] = await new Endpoint().init({ data: { mode: "apply", session_id: "SESSION", collection: "TESTCOLL" } });
    assert.equal(status, 200, raw);
    const result = JSON.parse(raw);
    assert.equal(result.item_key, duplicate ? "EXISTING" : "FRESH");
    assert.equal(result.attachment_key, "PDFKEY");
    assert.equal(pdf.parentID, duplicate ? 1 : 2);
    assert.equal((duplicate ? old : fresh).deleted, false, "the surviving parent must be active");
    assert.ok((duplicate ? old : fresh).collections.includes(9));
    assert.deepEqual(erased, duplicate ? ["FRESH"] : []);
    assert.equal([...items.values()].filter(i => i.isRegularItem() && !i.deleted).length, 1);
  }
});

let nativeConnector;
async function nativeConnectorSources() {
  if (nativeConnector) return nativeConnector;
  const { mkdtempSync, readFileSync, rmSync } = await import("node:fs");
  const { tmpdir } = await import("node:os");
  const { spawnSync } = await import("node:child_process");
  const output = mkdtempSync(tmpdir() + "/cse-connector-test-");
  try {
    const built = spawnSync("python", ["scripts/build_connector.py", "--source", "tests/fixtures/connector-5.0.217", "--output", output],
      { cwd: new URL("..", import.meta.url), encoding: "utf8" });
    assert.equal(built.status, 0, built.stderr);
    nativeConnector = ["itemSaver_background.js", "botBypass.js"].map(name => readFileSync(output + "/" + name, "utf8"));
    return nativeConnector;
  } finally { rmSync(output, { recursive: true, force: true }); }
}

async function agentJobFixture(response, title = "Paper", navigation = null, bypass = null, extra = {}) {
  const { readFileSync } = await import("node:fs");
  const vm = await import("node:vm");
  let finish, requests = 0, saves = 0, manual = 0, heartbeat, reloads = 0;
  const windows = [], removedWindows = [], iframeCalls = [], monitorCalls = [], requestOptions = [];
  const messageListeners = new Set();
  let tabUpdated, headersReceived, beforeRequest, beforeRedirect, navigationStarted, cleared = false, blankReads = 0;
  const rules = [];
  let clock = Date.now();
  const result = new Promise(resolve => { finish = resolve; });
  const events = { addListener() {}, removeListener() {} };
  const tab = { id: 5, url: "about:blank", title, status: "complete" };
  const storage = (initial = {}) => { const values = { ...initial }; return {
    get: async key => ({ [key]: values[key] }), set: async data => Object.assign(values, data),
    remove: async key => { delete values[key]; }
  }; };
  const job = { id: "JOB", url: "https://publisher.example/paper", deadline: clock + 180000, cooldowns: extra.cooldowns || {} };
  const calls = [];
  let claimed = false;
  const Zotero = {
    version: "5.0.217", initDeferred: { promise: Promise.resolve() },
    HTTP: { _requestFetch: async (_m, url, opts) => {
      requestOptions.push(opts);
      requests++;
      if (extra.expected_revision && url.endsWith("/paper.pdf")) {
        await heartbeat();
        assert.equal(reloads, 0, "an active save must not reload the worker");
      }
      const reply = Array.isArray(response) ? response[Math.min(requestOptions.length - 1, response.length - 1)] : response;
      headersReceived({ tabId: -1, initiator: "chrome-extension://official", url, type: "xmlhttprequest",
        statusCode: reply.status, responseHeaders: Object.entries(reply.headers || {}).map(([name, value]) => ({ name, value })) });
      return { ...reply, responseURL: url, getResponseHeader: name => reply.headers?.[name.toLowerCase()] || null };
    }, StatusError: class extends Error {} },
    ItemSaver: { _fetchAttachment: async (attachment, source) => {
      if (source.id !== tab.id) { manual++; return; }
      return (await Zotero.HTTP.request("GET", attachment.url, { successCodes: false })).response;
    }, _validateResponse: () => null },
    debug() {}, getExtensionURL: path => "chrome-extension://official/" + path,
    Proxies: { getPotentialProxies: url => ({ [url]: null }) },
    Utilities: { deepCopy: obj => JSON.parse(JSON.stringify(obj)), Connector: {
      getContentTypeFromXHR: xhr => ({ contentType: xhr.getResponseHeader("content-type") || "text/html" })
    } },
    BrowserAttachmentMonitor: { _isMonitorPageSender: () => true, waitForAttachment: async (id, url, timeout = 60000) => {
      monitorCalls.push({ id, url, timeout });
      if (id === tab.id && !["hidden", "repeated"].includes(bypass)) throw Error("Needs a human check");
      if (bypass === "timeout" && timeout === 300000) { clock += timeout; throw Error("Attachment monitor timed out"); }
      if (bypass === "throttled") headersReceived({ tabId: id, url, type: "main_frame", statusCode: 429, responseHeaders: [] });
      return "https://pdf.sciencedirectassets.com/captured.pdf";
    } },
    Connector: { callMethod: async () => ({}) },
    Messaging: { sendMessage() {} },
    OffscreenManager: { sendMessage: async () => {} },
    BotBypass: { bypassAmazonCaptcha() { manual++; }, passJSDetectionViaHiddenIframe() { manual++; }, passJSDetectionViaWindowPrompt() { manual++; } },
    Connector_Browser: { getTabInfo: () => ({ translators: [{ itemType: "journalArticle" }] }),
      getAllCookies: async () => [],
      saveWithTranslator: async (source, _index, options) => {
        saves++; assert.equal(options.fallbackOnFailure, false);
        // Another frame resolves first; actual attachment completion arrives later.
        setTimeout(async () => {
          try {
            await Zotero.Connector.callMethod({ method: "saveItems" }, { sessionID: "SESSION", items: [{}] }, source);
            await Zotero.ItemSaver._fetchAttachment({ url: bypass ? "https://www.sciencedirect.com/paper.pdf" : "https://publisher.example/paper.pdf", mimeType: "application/pdf" }, source);
            Zotero.Messaging.sendMessage("progressWindow.done", [true], source);
          } catch (_) { Zotero.Messaging.sendMessage("progressWindow.done", [false], source); }
        }, 10);
      }
    }
  };
  Zotero.HTTP.request = function(method, url, opts) { return Zotero.HTTP._requestFetch(method, url, opts); };
  Zotero.COHTTP = { request: Zotero.HTTP.request };
  const originalHTTP = Zotero.HTTP._requestFetch, originalCOHTTP = Zotero.COHTTP.request;
  const pageHeaders = status => headersReceived({ tabId: tab.id, url: tab.url, type: "main_frame", statusCode: status,
    responseHeaders: status === 403 ? [{ name: "cf-mitigated", value: "challenge" }] : [] });
  const context = vm.createContext({ Zotero, Date: class extends Date { static now() { return clock; } },
    setTimeout: (fn, ms) => setTimeout(() => { clock += ms; fn(); }, 0), setInterval: fn => { heartbeat = fn; }, URL, ArrayBuffer, Uint8Array, TextDecoder, AbortSignal,
    fetch: async (_url, opts) => {
      const call = JSON.parse(opts.body); calls.push(call);
      if (call.action === "finish" && call.id === "OLD") return { ok: false, status: 404 };
      if (call.action === "finish") finish(call.result);
      const data = call.action === "pickup" ? (!claimed ? { job } : { expected_revision: extra.expected_revision }) : {};
      if (call.action === "pickup") claimed = true;
      return { ok: true, json: async () => data };
    },
    chrome: { runtime: { id: "official", getPlatformInfo() {}, reload: () => { reloads++; }, onStartup: events,
      onMessage: { addListener: fn => messageListeners.add(fn), removeListener: fn => messageListeners.delete(fn) } },
      // Chrome restarted: tab ID 99 now belongs to the user, not the old job.
      storage: { local: storage({ cseAgentJob: { id: "OLD", tab: 99, window: 9, session_id: "OLDSESSION" },
        cseAgentReloadRevision: extra.previous_reload || 0 }), session: storage() },
      windows: { create: async options => {
        if (options.state) { assert.equal(options.focused, false); assert.equal(options.state, "minimized"); }
        windows.push(options);
        const target = windows.length === 1 ? tab : { id: 6, url: Zotero.getExtensionURL("browserAttachmentMonitor/browserAttachmentMonitor.html") };
        return { id: windows.length === 1 ? 7 : 8, tabs: Array.isArray(options.url) ? [{ id: 4, url: options.url[0] }, target] : [target] };
      }, update: async (_id, options) => { assert.equal(options.focused, false); assert.equal(options.state, "minimized"); },
        getAll: async () => [{ id: 10, tabs: [{ url: "chrome-extension://official/cse-agent-job.html#ORPHAN" }] },
          { id: 9, tabs: [{ url: "https://user.example/" }] }],
        remove: async id => { removedWindows.push(id); } },
      scripting: { executeScript: async options => {
        iframeCalls.push(options.func.toString());
        if (options.func.toString().includes("document.createElement")) {
          headersReceived({ tabId: tab.id, url: "https://www.sciencedirect.com/paper.pdf", type: "sub_frame", statusCode: 403,
            responseHeaders: [{ name: "cf-mitigated", value: "challenge" }] });
          for (const fn of [...messageListeners]) fn({ type: "attachment-monitor-loaded", success: false }, { tab });
        }
        return [{ result: { width: 1000, height: 800, left: 0, top: 0 } }];
      } },
      tabs: { update: async (_id, update) => {
        if (!update.url) return;
        tab.url = update.url;
        blankReads = 1; // Chrome still reports about:blank right after tabs.update resolves.
        beforeRequest({ tabId: tab.id, url: tab.url, type: "main_frame" });
        for (const signal of extra.signals || []) headersReceived(signal);
        if (extra.redirect) beforeRedirect({ tabId: tab.id, url: tab.url, redirectUrl: extra.redirect, type: "main_frame" });
        if (navigation) {
          navigationStarted = clock;
          tab.title = "Just a moment";
          pageHeaders(403);
          if (navigation.kind === "interactive") await Zotero.OffscreenManager.sendMessage("Translate.setDocument",
            ['<label><input type="checkbox">Verify you are human</label>', tab.url], tab, 0);
          headersReceived({ tabId: tab.id, url: tab.url + "/favicon.ico", type: "image", statusCode: 403,
            responseHeaders: [{ name: "cf-mitigated", value: "challenge" }] });
        }
      }, get: async () => {
        if (blankReads) { blankReads--; return { ...tab, url: "about:blank" }; }
        if (navigation?.clearsAfter && !cleared && clock - navigationStarted >= navigation.clearsAfter) {
          cleared = true; tab.title = "Paper"; pageHeaders(200);
          await Zotero.OffscreenManager.sendMessage("Translate.setDocument", ['<title>Paper</title>', tab.url], tab, 0);
        }
        return tab;
      },
        onUpdated: { addListener: listener => { tabUpdated = listener; } } },
      webRequest: { onHeadersReceived: { addListener: fn => { headersReceived = fn; } },
        onBeforeRequest: { addListener: fn => { beforeRequest = fn; } }, onBeforeRedirect: { addListener: fn => { beforeRedirect = fn; } } },
      declarativeNetRequest: { updateSessionRules: async update => {
        rules.push(update);
        if (update.addRules) tabUpdated(tab.id, {}, tab); // Blank-tab completion before publisher navigation.
      } }
    }
  });
  context.browser = context.chrome;
  if (bypass) {
    for (const source of await nativeConnectorSources()) vm.runInContext(source, context);
  }
  for (const name of ["public-url.js", "connector-agent.js"])
    vm.runInContext(readFileSync(new URL("../zotero-plugin/" + name, import.meta.url), "utf8"), context);
  const outcome = await result;
  if (extra.expected_revision) {
    await new Promise(resolve => setTimeout(resolve, 0)); // Let the native job finish freeing its slot.
    await Promise.all([heartbeat(), heartbeat()]);
    assert.equal(reloads, extra.previous_reload ? 0 : 1, "the older idle worker reloads once, even with concurrent heartbeats");
    await heartbeat();
    assert.equal(reloads, extra.previous_reload ? 0 : 1, "a persisting mismatch must not start a reload loop");
  }
  assert.equal(Zotero.HTTP._requestFetch, originalHTTP);
  assert.equal(Zotero.COHTTP.request, originalCOHTTP);
  assert.ok(removedWindows.includes(10), "startup closes marked windows even without their checkpoint");
  assert.equal(removedWindows.includes(9), false, "recycled user window IDs remain untouched");
  const removedRuleIds = Array.from(rules.at(-1).removeRuleIds);
  for (const rule of rules.find(r => r.addRules).addRules) assert.ok(removedRuleIds.includes(rule.id));
  assert.ok(removedRuleIds.includes(900000000));
  if (bypass) {
    await Zotero.BotBypass.passJSDetectionViaWindowPrompt("https://publisher.example/manual", { id: 99 });
    const manualWindow = windows.at(-1);
    assert.equal(manualWindow.width, 800);
    assert.equal(manualWindow.state, undefined);
    assert.equal(manualWindow.focused, undefined);
    return { outcome, calls, requests, saves, windows: windows.filter(w => w.state), removedWindows, iframeCalls, monitorCalls, requestOptions, rules };
  }
  await Zotero.COHTTP.request("GET", "https://publisher.example/manual", {}, { id: 99 });
  await Zotero.ItemSaver._fetchAttachment({}, { id: 99 });
  Zotero.BotBypass.passJSDetectionViaWindowPrompt("https://publisher.example/manual", { id: 99 });
  assert.equal(manual, 2, "ordinary clicks retain their original attachment and bypass paths");
  return { outcome, calls, requests: requests - 1, saves, elapsed: clock - navigationStarted, rules };
}

test("A newer build reloads the idle worker once, deferring throughout an active save", async () => {
  for (const previous_reload of [0, 100]) await agentJobFixture(
    { status: 200, response: new TextEncoder().encode("%PDF-1.7").buffer },
    "Paper", null, null, { expected_revision: 100, previous_reload });
});

test("Response observations record job and extension background checks without policing native requests", async () => {
  for (const response of [
    { status: 429, response: "quota" },
    { status: 200, response: "blocked", headers: { "cf-mitigated": "challenge" } },
    { status: 403, response: "blocked", headers: { "x-amzn-waf-action": "captcha" } }
  ]) {
    const { outcome, calls, requests } = await agentJobFixture(response);
    assert.equal(outcome.session_id, "SESSION");
    assert.equal(outcome.stop, null);
    assert.equal(outcome.observations[0].host, "publisher.example");
    assert.equal(outcome.observations[0].cooldown, true);
    assert.equal(requests, 1);
    assert.equal(calls.filter(c => c.action === "pickup").length, 1);
    assert.equal(calls.filter(c => c.action === "finish" && c.id === "JOB").length, 1);
  }
});

test("Agent attachments reach the shipped automatic checks and an unfocused human-check monitor", async () => {
  const pdf = { status: 200, response: new TextEncoder().encode("%PDF-1.7").buffer, headers: { "content-type": "application/pdf" } };
  for (const kind of ["hidden", "amazon", "prompt", "timeout", "throttled"]) {
    const challenge = { status: 403, response: new TextEncoder().encode("<title>Just a moment</title>").buffer,
      headers: { "content-type": "text/html", ...(kind === "amazon" ? { "x-amzn-waf-action": "challenge" } : {}) } };
    const result = await agentJobFixture([challenge, pdf], "Paper", null, kind);
    assert.equal(result.windows.length, ["prompt", "timeout", "throttled"].includes(kind) ? 2 : 1, kind);
    const notices = result.calls.filter(c => c.action === "progress" && c.result.check?.kind === "interactive");
    assert.equal(notices.length, ["prompt", "timeout", "throttled"].includes(kind) ? 1 : 0, kind);
    if (kind === "amazon") {
      assert.equal(result.requestOptions[1].headers["Sec-Fetch-Site"], "same-origin");
      assert.equal(result.iframeCalls.some(code => code.includes("document.createElement")), false);
    } else {
      assert.ok(result.monitorCalls.length > 0, "agent attachment must reach the native hidden-iframe check");
      assert.equal(result.monitorCalls[0].timeout, 5000);
      assert.ok(result.iframeCalls.some(code => code.includes("iframe.style.display = 'none'")));
      if (result.windows.length === 2) {
        assert.equal(result.monitorCalls[1].timeout, 300000);
        assert.ok(result.removedWindows.includes(8));
      }
    }
    if (kind === "timeout") {
      assert.equal(result.outcome.stop.cooldown, false);
      assert.equal(result.requests, 1);
    } else {
      assert.equal(result.outcome.stop, null, kind);
      assert.equal(result.outcome.error, null, kind);
      assert.equal(result.requests, 2, kind);
    }
    assert.equal(result.calls.filter(c => c.action === "pickup").length, 1);
  }
});

test("Agent job waits for native completion and refuses a challenge title before saving", async () => {
  const response = { status: 200, response: new TextEncoder().encode("%PDF-1.7").buffer };
  const success = await agentJobFixture(response);
  assert.equal(success.outcome.stop, null);
  assert.equal(success.outcome.error, null);
  assert.equal(success.outcome.session_id, "SESSION");
  assert.equal(success.saves, 1);
  const denied = await agentJobFixture(response, "Just a moment");
  assert.equal(denied.saves, 0);
  assert.equal(denied.requests, 0);
  assert.equal(denied.outcome.stop.cooldown, true);
  assert.equal(denied.outcome.title, "Just a moment");
});

test("Navigation checks clear without replay, or time out with the appropriate cooldown", async () => {
  const response = { status: 200, response: new TextEncoder().encode("%PDF-1.7").buffer };
  for (const kind of ["automatic", "interactive"]) for (const clears of [true, false]) {
    const check = await agentJobFixture(response, "Paper", { kind, clearsAfter: clears ? (kind === "automatic" ? 5000 : 20000) : null });
    assert.equal(check.saves, clears ? 1 : 0);
    assert.equal(check.requests, clears ? 1 : 0);
    const notices = check.calls.filter(c => c.action === "progress" && c.result.check?.kind === "interactive");
    assert.equal(notices.length, kind === "interactive" ? 1 : 0);
    if (clears) assert.equal(check.outcome.stop, null);
    else {
      assert.equal(check.outcome.stop.cooldown, kind === "automatic");
      assert.ok(check.elapsed >= (kind === "automatic" ? 15000 : 300000));
    }
    assert.equal(check.calls.filter(c => c.action === "pickup").length, 1);
  }
});

test("Navigation guards reject non-public redirects and cooled domains cover background requests", async () => {
  const response = { status: 200, response: new TextEncoder().encode("%PDF-1.7").buffer };
  const urls = ["https://127.0.0.1:23119/a", "https://10.0.0.1/a", "https://169.254.1.1/a",
    "https://172.31.1.1/a", "https://192.168.1.1/a", "https://[::1]/a", "https://[fc00::1]/a",
    "https://machine.local/a", "https://machine.internal/a", "https://machine/a", "http://public.example/a"];
  for (const redirect of urls) {
    const result = await agentJobFixture(response, "Paper", null, null, { redirect });
    assert.equal(result.saves, 0);
    assert.equal(result.requests, 0);
    assert.match(result.outcome.stop.reason, /Unsafe/);
    const guards = result.rules.find(r => r.addRules)?.addRules.filter(r => r.condition.regexFilter);
    assert.ok(guards.some(r => new RegExp(r.condition.regexFilter, "i").test(redirect)), redirect);
  }
  const event = (tabId, host, initiator = "chrome-extension://official") =>
    ({ tabId, initiator, url: "https://" + host + "/pdf", type: "xmlhttprequest", statusCode: 429 });
  const result = await agentJobFixture(response, "Paper", null, null, {
    cooldowns: { "cooled.example": Date.now() / 1000 + 1000 },
    signals: [event(5, "tab.example"), event(-1, "background.example"), event(99, "user.example"), event(-1, "other.example", "chrome-extension://other")]
  });
  assert.deepEqual(Array.from(result.outcome.observations, e => e.host).sort(), ["background.example", "tab.example"]);
  assert.equal(result.saves, 1);
  const cooled = result.rules.find(r => r.addRules)?.addRules.find(r => r.id === 900000000);
  assert.deepEqual(Array.from(cooled.condition.tabIds), [5, -1]);
  assert.deepEqual(Array.from(cooled.condition.requestDomains), ["cooled.example"]);
});

test("Plugin jobs require a heartbeat, are claimed once, and retain sessions across timeout", async () => {
  const { readFileSync } = await import("node:fs");
  const vm = await import("node:vm");
  let now = 1000, expected = null;
  const Zotero = { Server: { Endpoints: {} }, Notifier: { registerObserver: () => 1 },
    File: { getContentsAsync: async path => { assert.ok(path.endsWith("/zotero-connector-agent/cse-agent-build.json")); return JSON.stringify({ module_revision: expected }); } } };
  const context = vm.createContext({ Zotero, Services: { dirsvc: { get: () => ({ path: "/home/test" }) } },
    Components: { interfaces: { nsIFile: {} } }, URL, Date: class extends Date { static now() { return now; } } });
  for (const name of ["cleanup-plan.js", "organize-plan.js", "public-url.js", "zotero-companion.js"])
    vm.runInContext(readFileSync(new URL("../zotero-plugin/" + name, import.meta.url), "utf8"), context);
  vm.runInContext("ZoteroCompanion.start()", context);
  const endpoint = new Zotero.Server.Endpoints["/zotero-companion/acquire-job"]();
  const call = async data => { const [status, , raw] = await endpoint.init({ data }); return { status, ...JSON.parse(raw) }; };
  const submit = { action: "submit", job: { id: "ONE", url: "https://doi.org/10.1002/test", cooldowns: {} } };
  assert.equal((await call(submit)).error, "agent_connector_setup_required");
  await call({ action: "pickup", protocol: 1, version: "5.0.217", module_revision: 2, compatible: true });
  assert.equal((await call({ action: "status" })).module_revision, 2);
  assert.equal((await call(submit)).status, 200);
  assert.equal((await call(submit)).error, "connector_job_busy");
  assert.equal((await call({ action: "pickup", protocol: 1, compatible: true })).job.id, "ONE");
  assert.equal((await call({ action: "pickup", protocol: 1, compatible: true })).job, null);
  await call({ action: "progress", id: "ONE", result: { session_id: "SESSION", checkpoint: true } });
  now += 180001;
  assert.equal((await call({ action: "pickup", protocol: 1, compatible: true })).cancelled, true);
  assert.equal((await call(submit)).error, "connector_job_busy");
  assert.equal((await call({ action: "status" })).job.result.session_id, "SESSION");
  await call({ action: "finish", id: "ONE", result: { session_id: "SESSION", error: "timed out" } });
  assert.equal((await call({ action: "status" })).job.state, "done");
  await call({ action: "pickup", protocol: 1, compatible: true });
  await call({ ...submit, job: { ...submit.job, id: "TWO" } });
  const running = (await call({ action: "pickup", protocol: 1, compatible: true })).job;
  const progress = { action: "progress", id: "TWO", result: { check: { kind: "interactive" } } };
  await call({ action: "progress", id: "TWO", result: { checkpoint: true } });
  await call(progress); await call(progress);
  assert.equal((await call({ action: "status" })).job.deadline, running.deadline + 300000);
  now += 180001;
  assert.equal((await call({ action: "status" })).job.state, "running");
  now += 300000;
  assert.equal((await call({ action: "status" })).job.state, "stopping");
  await call({ action: "finish", id: "TWO", result: {} });
  await call({ action: "pickup", protocol: 1, compatible: true });
  for (const url of ["https://127.1/", "https://0x7f000001/", "https://[fe80::1]/", "https://local/", "https://a.internal/", "http://public.example/"]) {
    assert.equal((await call({ ...submit, job: { ...submit.job, url } })).status, 400, url);
  }
  await call({ ...submit, job: { ...submit.job, id: "ORPHAN" } });
  await call({ action: "pickup", protocol: 1, compatible: true });
  now += 180001;
  const orphan = (await call({ action: "status" })).job;
  assert.equal(orphan.state, "done");
  assert.match(orphan.result.error, /without a checkpoint; no replay/);
  await call({ action: "pickup", protocol: 1, compatible: true });
  assert.equal((await call(submit)).status, 200, "expired claim frees the channel");
  expected = 3;
  assert.equal((await call({ action: "pickup", protocol: 1, compatible: true, module_revision: 2 })).job, null);
  const mismatch = await call({ action: "status" });
  assert.equal(mismatch.ready, false);
  assert.equal(mismatch.expected_revision, 3);
  assert.equal(mismatch.revision_mismatch, true);
  assert.match(mismatch.error, /running 2, expected 3/);
  assert.equal((await call({ action: "pickup", protocol: 1, compatible: true, module_revision: 3 })).job.id, "ONE");
  assert.equal((await call({ action: "status" })).revision_mismatch, false);
});
