/* global Components, Zotero, ZoteroCompanionPlan, ZoteroCompanionOrganize, Services */

var ZoteroCompanion = (function (zotero, plan, organize, services) {
  "use strict";

  const VERSION = "1.0.0";
  const STATUS_PATH = "/zotero-companion/status";
  const TAG_CLEANUP_PATH = "/zotero-companion/tag-cleanup";
  const SEARCHES_PATH = "/zotero-companion/saved-searches";
  const ORGANIZE_PATH = "/zotero-companion/project-organize";
  const ACQUIRE_METADATA_PATH = "/zotero-companion/acquire-metadata";
  const ACQUIRE_ATTACHMENT_PATH = "/zotero-companion/acquire-attachment";
  const CROSSREF_TRANSLATOR = "0a61e167-de9a-4f93-a68a-628b48855909";
  const registeredPaths = [STATUS_PATH, TAG_CLEANUP_PATH, SEARCHES_PATH, ORGANIZE_PATH,
    ACQUIRE_METADATA_PATH, ACQUIRE_ATTACHMENT_PATH];
  const SYNC_DELAY_MS = 3000;
  let observerID = null;
  let metadataInFlight = false;
  let lastSync = null;

  function response(status, payload) {
    return [status, "application/json", JSON.stringify(payload)];
  }

  function requestData(request) {
    if (!request || request.data === null || typeof request.data === "undefined") {
      return {};
    }
    if (typeof request.data === "string") {
      try {
        return JSON.parse(request.data);
      } catch (error) {
        return null;
      }
    }
    return request.data;
  }

  function libraryID() {
    return zotero.Libraries.userLibraryID;
  }

  async function tagRows() {
    return zotero.DB.queryAsync(
      "SELECT tags.name AS name, itemTags.type AS type, COUNT(*) AS count " +
      "FROM itemTags JOIN items USING (itemID) JOIN tags USING (tagID) " +
      "WHERE items.libraryID=? AND items.itemID NOT IN (SELECT itemID FROM deletedItems) " +
      "GROUP BY tags.name, itemTags.type",
      libraryID()
    );
  }

  async function tagReport() {
    const rows = await tagRows();
    return {
      libraryID: libraryID(),
      ...plan.summarizeRows(rows)
    };
  }

  async function applyTagCleanup(data) {
    if (!data || data.confirm !== plan.APPLY_TOKEN) {
      return response(428, {
        error: "explicit_confirmation_required",
        requiredConfirmation: plan.APPLY_TOKEN,
        hint: "Send mode=apply and the exact confirmation token to mutate Zotero."
      });
    }

    const before = await tagReport();
    // Automatic tags are removed before renaming manual tags because Zotero's
    // rename() intentionally converts all matching assignments to manual.
    zotero.Prefs.set("automaticTags", false);
    await zotero.Tags.removeAutomaticFromLibrary(libraryID());
    const renamed = [];
    for (const mapping of before.mappings) {
      await zotero.Tags.rename(libraryID(), mapping.oldName, mapping.newName);
      renamed.push(mapping);
    }
    for (const workflowTag of plan.WORKFLOW_TAGS) {
      await zotero.Tags.setColor(
        libraryID(), workflowTag.name, workflowTag.color, workflowTag.position
      );
    }
    const after = await tagReport();
    return response(200, {
      mode: "apply",
      automaticTagsDisabled: true,
      renamed,
      coloredTags: plan.WORKFLOW_TAGS,
      before,
      after
    });
  }

  async function createWorkflowSearches(data) {
    if (!data || data.confirm !== plan.SEARCH_TOKEN) {
      return response(428, {
        error: "explicit_confirmation_required",
        requiredConfirmation: plan.SEARCH_TOKEN,
        hint: "Send mode=apply and the exact confirmation token to create saved searches."
      });
    }

    const existing = await zotero.Searches.getAll(libraryID());
    const existingNames = new Set(existing.map(search => search.name));
    const created = [];
    const skipped = [];
    for (const [name, tag] of plan.WORKFLOW_SEARCHES) {
      if (existingNames.has(name)) {
        skipped.push({ name, tag, reason: "already_exists" });
        continue;
      }
      const search = new zotero.Search({ libraryID: libraryID() });
      search.name = name;
      search.addCondition("tag", "is", tag, true);
      search.addCondition("noChildren", "true", "", true);
      await search.saveTx();
      created.push({ name, tag });
    }
    return response(200, {
      mode: "apply",
      created,
      skipped
    });
  }

  // The Companion's projects.json is the only source of write scope and of the
  // sync command; requests never supply either.
  async function readRegistry() {
    const configHome = services.env.get("XDG_CONFIG_HOME") ||
      services.dirsvc.get("Home", Components.interfaces.nsIFile).path + "/.config";
    const path = configHome + "/zotero-companion/projects.json";
    try {
      return JSON.parse(await zotero.File.getContentsAsync(path));
    } catch (error) {
      return null;
    }
  }

  function collectionRows() {
    return zotero.Collections.getByLibrary(libraryID(), true)
      .map(c => ({ key: c.key, name: c.name, parent: c.parentKey || "" }));
  }

  // Steps run in order; `done` records what already changed Zotero if one fails.
  async function runOrganize(steps, done) {
    const created = {};
    const resolve = key => (key && key.startsWith("@") ? created[key] : key);
    const collection = key => {
      const found = zotero.Collections.getByLibraryAndKey(libraryID(), resolve(key));
      if (!found) throw new Error(`collection ${key} no longer exists`);
      return found;
    };
    for (const step of steps) {
      if (step.op === "create") {
        const target = new zotero.Collection({ libraryID: libraryID(), name: step.name, parentKey: resolve(step.parent) });
        await target.saveTx();
        created[step.ref] = target.key;
        done.push({ ...step, key: target.key });
        continue;
      }
      const target = collection(step.collection);
      if (step.op === "rename") {
        target.name = step.name;
        await target.saveTx();
      } else if (step.op === "move") {
        target.parentKey = resolve(step.parent);
        await target.saveTx();
      } else {
        const ids = step.items.map(key => zotero.Items.getByLibraryAndKey(libraryID(), key).id);
        await zotero.DB.executeTransaction(async () => {
          if (step.op === "add") await target.addItems(ids);
          else await target.removeItems(ids);
        });
      }
      done.push({ ...step, key: target.key });
    }
  }

  async function projectOrganize(data) {
    const registry = await readRegistry();
    if (!registry) return response(409, { error: "project_registry_unavailable" });
    const { errors, steps, scope } = organize.resolvePlan(data, registry, collectionRows());
    // Check item keys here too, so a bad key fails the preview, not a half-applied plan.
    for (const step of steps) {
      for (const key of step.items || []) {
        const item = zotero.Items.getByLibraryAndKey(libraryID(), key);
        if (!item || !item.isRegularItem()) errors.push(`item ${key} is not a top-level Zotero item`);
      }
    }
    if (errors.length) return response(422, { error: "invalid_plan", errors });
    if (data.mode !== "apply") {
      return response(200, { mode: "dry-run", scope, steps, applyToken: organize.ORGANIZE_TOKEN });
    }
    if (data.confirm !== organize.ORGANIZE_TOKEN) {
      return response(428, {
        error: "explicit_confirmation_required",
        requiredConfirmation: organize.ORGANIZE_TOKEN
      });
    }
    const applied = [];
    try {
      await runOrganize(steps, applied);
      return response(200, { mode: "apply", scope, applied });
    } catch (error) {
      return response(500, { error: "apply_failed", message: String(error), applied });
    }
  }

  function acquisitionCollection(requested) {
    const available = zotero.Collections.getByLibrary(libraryID(), true);
    if (requested) {
      if (typeof requested !== "string") return { error: "invalid_collection" };
      const byKey = available.find(collection => collection.key === requested);
      if (byKey) return { collection: byKey };
      const byName = available.filter(collection => collection.name === requested);
      if (byName.length === 1) return { collection: byName[0] };
      if (byName.length > 1) return { error: "collection_ambiguous" };
      return { error: "collection_not_found" };
    }
    const pane = zotero.getActiveZoteroPane && zotero.getActiveZoteroPane();
    const selectedLibrary = pane && pane.getSelectedLibraryIDs && pane.getSelectedLibraryIDs()[0];
    const selectedRows = pane && pane.getSelectedCollections && pane.getSelectedCollections();
    if (selectedRows && selectedRows.length > 1) return { error: "collection_ambiguous" };
    const selected = selectedRows ? selectedRows[0] :
      pane && pane.getSelectedCollection && pane.getSelectedCollection();
    if ((selectedLibrary && selectedLibrary !== libraryID()) ||
        (selected && selected.libraryID !== libraryID())) {
      return { error: "group_library_unsupported", collection_key: selected && selected.key || null };
    }
    return { collection: selected && selected.id ? selected : null };
  }

  function normalizedTitle(title) {
    return String(title || "").normalize("NFKC").toLowerCase().replace(/\s+/g, " ").trim();
  }

  async function existingItem(metadata) {
    const doi = zotero.Utilities.cleanDOI(metadata.DOI || "");
    const fields = zotero.ItemFields;
    const queries = doi ? [{
      sql: "SELECT items.itemID FROM items JOIN itemData USING (itemID) " +
        "JOIN itemDataValues USING (valueID) " +
        "WHERE items.libraryID=? AND itemData.fieldID=? AND lower(itemDataValues.value)=lower(?) " +
        "AND items.itemID NOT IN (SELECT itemID FROM deletedItems)",
      fieldID: fields.getID("DOI"), value: doi, title: false
    }] : [];
    const title = normalizedTitle(metadata.title);
    if (title) queries.push({
      sql: "SELECT items.itemID, itemDataValues.value AS value FROM items " +
        "JOIN itemData USING (itemID) JOIN itemDataValues USING (valueID) " +
        "WHERE items.libraryID=? AND itemData.fieldID=? " +
        "AND items.itemID NOT IN (SELECT itemID FROM deletedItems)",
      fieldID: fields.getID("title"), title: true
    });
    for (const query of queries) {
      const rows = query.title
        ? await zotero.DB.queryAsync(query.sql, [libraryID(), query.fieldID])
        : await zotero.DB.queryAsync(query.sql, [libraryID(), query.fieldID, query.value]);
      for (const row of rows) {
        if (query.title && normalizedTitle(row.value) !== title) continue;
        const item = await zotero.Items.getAsync(row.itemID, { noCache: true });
        if (item && item.isRegularItem()) return item;
      }
    }
    return null;
  }

  function metadataJSON(item) {
    const json = item && item.toJSON ? item.toJSON() : { ...item };
    for (const field of ["attachments", "notes", "collections", "relations", "key", "version", "itemID"])
      delete json[field];
    return json;
  }

  async function acquireMetadata(data) {
    if (!data || typeof data.identifier !== "string" || !data.identifier.trim())
      return response(400, { error: "identifier_required" });
    if (data.mode && !["apply", "dry-run"].includes(data.mode))
      return response(400, { error: "invalid_mode" });
    const target = acquisitionCollection(data.collection);
    if (target.error) return response(422, { error: target.error, collection_key: target.collection_key || null });
    const identifiers = zotero.Utilities.extractIdentifiers(data.identifier);
    const identifier = identifiers && identifiers[0];
    if (!identifier) return response(422, { error: "unsupported_identifier" });
    const translate = new zotero.Translate.Search();
    if (identifier.DOI) {
      translate.setSearch({ itemType: "journalArticle", DOI: identifier.DOI });
      translate.setTranslator(CROSSREF_TRANSLATOR);
    } else {
      translate.setIdentifier(identifier);
      const translators = await translate.getTranslators();
      translate.setTranslator(translators);
    }
    const translated = await translate.translate({ libraryID: false, saveAttachments: false });
    if (!translated || !translated.length) return response(404, { error: "metadata_not_found" });
    const source = translated[0];
    const metadata = metadataJSON(source);
    const existing = await existingItem(metadata);
    if (existing) return response(200, {
      mode: data.mode === "apply" ? "apply" : "dry-run",
      metadata,
      existing: true,
      item_key: existing.key,
      collection_key: target.collection && target.collection.key || null
    });
    if (data.mode !== "apply") return response(200, {
      mode: "dry-run", existing: false, metadata,
      collection_key: target.collection && target.collection.key || null
    });
    const item = new zotero.Item();
    item.fromJSON(metadata);
    if (!item.isRegularItem()) return response(422, { error: "metadata_not_regular_item" });
    item.libraryID = libraryID();
    if (target.collection) item.setCollections([target.collection.id]);
    await item.saveTx();
    return response(200, {
      mode: "apply", existing: false, metadata: metadataJSON(item), item_key: item.key,
      collection_key: target.collection && target.collection.key || null
    });
  }

  function pdfBytes(value) {
    if (typeof value !== "string" || !value.length || value.length > 4 * Math.ceil(50 * 1024 * 1024 / 3)) return null;
    try {
      const bytes = atob(value);
      return bytes.length <= 50 * 1024 * 1024 && bytes.startsWith("%PDF") ? bytes : null;
    } catch (_error) {
      return null;
    }
  }

  function writeTempPDF(bytes) {
    const file = services.dirsvc.get("TmpD", Components.interfaces.nsIFile).clone();
    file.append("zotero-companion-acquire.pdf");
    file.createUnique(Components.interfaces.nsIFile.NORMAL_FILE_TYPE, 0o600);
    try {
      const stream = Components.classes["@mozilla.org/network/file-output-stream;1"]
        .createInstance(Components.interfaces.nsIFileOutputStream);
      stream.init(file, 0x02 | 0x08 | 0x20, 0o600, 0);
      const binary = Components.classes["@mozilla.org/binaryoutputstream;1"]
        .createInstance(Components.interfaces.nsIBinaryOutputStream);
      binary.setOutputStream(stream);
      binary.writeBytes(bytes, bytes.length);
      binary.close();
      return file;
    } catch (error) {
      if (file.exists()) file.remove(false);
      throw error;
    }
  }

  async function acquireAttachment(data) {
    if (!data || typeof data.item_key !== "string" || !data.item_key || typeof data.pdf_base64 !== "string")
      return response(400, { error: "item_key_and_pdf_required" });
    if (data.mode && !["apply", "dry-run"].includes(data.mode))
      return response(400, { error: "invalid_mode" });
    const bytes = pdfBytes(data.pdf_base64);
    if (!bytes) return response(422, { error: "invalid_pdf" });
    const parent = zotero.Items.getByLibraryAndKey(libraryID(), data.item_key);
    if (!parent || !parent.isRegularItem()) return response(404, { error: "item_not_found" });
    if (data.mode !== "apply") return response(200, {
      mode: "dry-run", item_key: parent.key, byte_length: bytes.length
    });
    let file;
    try {
      file = writeTempPDF(bytes);
      const attachment = await zotero.Attachments.importFromFile({
        file, parentItemID: parent.id, libraryID: libraryID(), contentType: "application/pdf"
      });
      return response(200, { mode: "apply", item_key: parent.key, attachment_key: attachment.key });
    } finally {
      if (file && file.exists()) file.remove(false);
    }
  }

  function endpointError(error) {
    return response(500, { error });
  }

  // Live refresh: collection changes re-render every project page (a move can
  // leave one tree and enter another); item filing re-renders the owning page.
  let pending = null;
  let syncing = false;

  function queueSync(allProjects, collectionKeys) {
    pending = pending || { all: false, keys: new Set() };
    pending.all = pending.all || allProjects;
    for (const key of collectionKeys) pending.keys.add(key);
    if (syncing) return;
    syncing = true;
    (async () => {
      try {
        while (pending) {
          await zotero.Promise.delay(SYNC_DELAY_MS);
          const batch = pending;
          pending = null;
          await runSync(batch);
        }
      } finally {
        syncing = false;
      }
    })();
  }

  async function runSync(batch) {
    const registry = await readRegistry();
    const command = registry && registry.sync_command;
    if (!command || !command.length) {
      lastSync = { at: new Date().toISOString(), ok: false, error: "no sync_command in projects.json" };
      return;
    }
    let slugs = [];
    if (!batch.all) {
      const parents = new Map(collectionRows().map(c => [c.key, c.parent]));
      const inProject = (key, root) => {
        while (key && key !== root) key = parents.get(key);
        return Boolean(key);
      };
      slugs = Object.entries(registry.projects || {})
        .filter(([, entry]) => [...batch.keys].some(key => inProject(key, entry.collection)))
        .map(([slug]) => slug);
      if (!slugs.length) return;
    }
    const runs = batch.all ? [[]] : slugs.map(slug => ["--slug", slug]);
    try {
      for (const extra of runs) {
        await zotero.Utilities.Internal.exec(command[0], [...command.slice(1), ...extra]);
      }
      lastSync = { at: new Date().toISOString(), ok: true, projects: batch.all ? "all" : slugs };
    } catch (error) {
      lastSync = { at: new Date().toISOString(), ok: false, projects: batch.all ? "all" : slugs, error: String(error) };
    }
  }

  const observer = {
    notify(event, type, ids) {
      if (type === "collection") {
        queueSync(true, []);
        return;
      }
      const keys = [];
      for (const id of ids) {
        const found = zotero.Collections.get(Number(String(id).split("-")[0]));
        if (found && found.libraryID === libraryID()) keys.push(found.key);
      }
      if (keys.length) queueSync(false, keys);
    }
  };

  function status() {
    return response(200, {
      plugin: "CSE Zotero",
      version: VERSION,
      zoteroVersion: zotero.version,
      libraryID: libraryID(),
      endpoints: {
        status: { method: "GET", path: STATUS_PATH },
        tagCleanup: { method: "POST", path: TAG_CLEANUP_PATH, defaultMode: "dry-run" },
        savedSearches: { method: "POST", path: SEARCHES_PATH, defaultMode: "dry-run" },
        projectOrganize: { method: "POST", path: ORGANIZE_PATH, defaultMode: "dry-run" },
        acquireMetadata: { method: "POST", path: ACQUIRE_METADATA_PATH, defaultMode: "dry-run" },
        acquireAttachment: { method: "POST", path: ACQUIRE_ATTACHMENT_PATH, defaultMode: "dry-run" }
      },
      projectSync: { observing: observerID !== null, lastSync },
      config: plan.getConfig()
    });
  }

  function register() {
    zotero.Server.Endpoints[STATUS_PATH] = class {
      supportedMethods = ["GET"];
      init(_request) {
        return status();
      }
    };
    zotero.Server.Endpoints[TAG_CLEANUP_PATH] = class {
      supportedMethods = ["POST"];
      supportedDataTypes = ["application/json"];
      init(request) {
        const data = requestData(request);
        if (data === null) return response(400, { error: "invalid_json" });
        if (data.mode !== "apply") return tagReport().then(report => response(200, {
          mode: "dry-run",
          report,
          applyToken: plan.APPLY_TOKEN
        }));
        return applyTagCleanup(data);
      }
    };
    zotero.Server.Endpoints[SEARCHES_PATH] = class {
      supportedMethods = ["POST"];
      supportedDataTypes = ["application/json"];
      init(request) {
        const data = requestData(request);
        if (data === null) return response(400, { error: "invalid_json" });
        if (data.mode !== "apply") {
          return response(200, {
            mode: "dry-run",
            searches: plan.WORKFLOW_SEARCHES.map(([name, tag]) => ({ name, tag })),
            applyToken: plan.SEARCH_TOKEN
          });
        }
        return createWorkflowSearches(data);
      }
    };
    zotero.Server.Endpoints[ORGANIZE_PATH] = class {
      supportedMethods = ["POST"];
      supportedDataTypes = ["application/json"];
      init(request) {
        const data = requestData(request);
        if (data === null) return response(400, { error: "invalid_json" });
        return projectOrganize(data);
      }
    };
    zotero.Server.Endpoints[ACQUIRE_METADATA_PATH] = class {
      supportedMethods = ["POST"];
      supportedDataTypes = ["application/json"];
      permitBookmarklet = false;
      init(request) {
        const data = requestData(request);
        if (data === null) return response(400, { error: "invalid_json" });
        if (metadataInFlight) return response(409, { error: "metadata_acquisition_busy" });
        metadataInFlight = true;
        return acquireMetadata(data).catch(() => endpointError("metadata_acquisition_failed"))
          .finally(() => { metadataInFlight = false; });
      }
    };
    zotero.Server.Endpoints[ACQUIRE_ATTACHMENT_PATH] = class {
      supportedMethods = ["POST"];
      supportedDataTypes = ["application/json"];
      permitBookmarklet = false;
      init(request) {
        const data = requestData(request);
        if (data === null) return response(400, { error: "invalid_json" });
        return acquireAttachment(data).catch(() => endpointError("attachment_import_failed"));
      }
    };
    observerID = zotero.Notifier.registerObserver(observer, ["collection", "collection-item"], "zotero-companion");
  }

  function unregister() {
    for (const path of registeredPaths) {
      if (zotero.Server.Endpoints[path]) delete zotero.Server.Endpoints[path];
    }
    if (observerID !== null) zotero.Notifier.unregisterObserver(observerID);
    observerID = null;
  }

  return {
    start: register,
    stop: unregister,
    paths: registeredPaths
  };
})(Zotero, ZoteroCompanionPlan, ZoteroCompanionOrganize, Services);
