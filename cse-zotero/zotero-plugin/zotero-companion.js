/* global Zotero, ZoteroCompanionPlan */

var ZoteroCompanion = (function (zotero, plan) {
  "use strict";

  const VERSION = "1.0.0";
  const STATUS_PATH = "/zotero-companion/status";
  const TAG_CLEANUP_PATH = "/zotero-companion/tag-cleanup";
  const SEARCHES_PATH = "/zotero-companion/saved-searches";
  const registeredPaths = [STATUS_PATH, TAG_CLEANUP_PATH, SEARCHES_PATH];

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

  function status() {
    return response(200, {
      plugin: "CSE Zotero",
      version: VERSION,
      zoteroVersion: zotero.version,
      libraryID: libraryID(),
      endpoints: {
        status: { method: "GET", path: STATUS_PATH },
        tagCleanup: { method: "POST", path: TAG_CLEANUP_PATH, defaultMode: "dry-run" },
        savedSearches: { method: "POST", path: SEARCHES_PATH, defaultMode: "dry-run" }
      },
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
  }

  function unregister() {
    for (const path of registeredPaths) {
      if (zotero.Server.Endpoints[path]) delete zotero.Server.Endpoints[path];
    }
  }

  return {
    start: register,
    stop: unregister,
    paths: registeredPaths
  };
})(Zotero, ZoteroCompanionPlan);
