/* global module */

// Checks a project-organize request against the Companion project registry.
// Pure logic, shared by the add-on and its Node tests: every collection a step
// touches must sit inside the requested project's registered collection tree.

(function (global) {
  "use strict";

  const ORGANIZE_TOKEN = "ZOTERO-COMPANION-ORGANIZE-v1";
  const KEY = /^[A-Z0-9]{8}$/;

  // collections: [{ key, name, parent }] for the whole user library.
  function resolvePlan(request, registry, collections) {
    const errors = [];
    const steps = [];
    const table = new Map(collections.map(c => [c.key, { name: c.name, parent: c.parent || "" }]));
    const projects = (registry && registry.projects) || {};
    const slug = request && request.project;
    let scope;
    if (slug) {
      scope = projects[slug] && projects[slug].collection;
      if (!scope) errors.push(`project ${slug} is not registered`);
    } else {
      // Without a project, only new project collections directly under the root.
      scope = registry && registry.root_collection;
      if (!scope) errors.push("the registry has no root collection");
    }
    if (scope && !table.has(scope)) errors.push(`collection ${scope} is not in the library`);
    const operations = request && Array.isArray(request.operations) ? request.operations : null;
    if (!operations || !operations.length) errors.push("operations must be a non-empty array");
    if (errors.length) return { errors, steps, scope };

    const within = key => {
      const seen = new Set();
      while (key && !seen.has(key)) {
        if (key === scope) return true;
        seen.add(key);
        key = table.has(key) ? table.get(key).parent : "";
      }
      return false;
    };
    const path = key => {
      const names = [];
      while (key && table.has(key)) {
        names.unshift(table.get(key).name);
        if (key === scope) break;
        key = table.get(key).parent;
      }
      return names.join(" / ");
    };
    const inScope = (key, index, field) => {
      if (typeof key !== "string" || !table.has(key) || !within(key)) {
        errors.push(`operation ${index}: ${field} ${JSON.stringify(key)} is not inside ${path(scope) || scope}`);
        return false;
      }
      return true;
    };

    operations.forEach((operation, index) => {
      const op = operation && operation.op;
      if (!slug && op !== "create") {
        errors.push(`operation ${index}: only create is allowed without a project`);
        return;
      }
      if (op === "create") {
        const parent = operation.parent || scope;
        const name = typeof operation.name === "string" ? operation.name.trim() : "";
        if (!name) return errors.push(`operation ${index}: create needs a name`);
        if (!slug && parent !== scope) return errors.push(`operation ${index}: new project collections go directly under the root`);
        if (!inScope(parent, index, "parent")) return;
        const ref = operation.id ? `@${operation.id}` : `@${index}`;
        if (table.has(ref)) return errors.push(`operation ${index}: duplicate id ${operation.id}`);
        table.set(ref, { name, parent });
        steps.push({ op, name, parent, ref, path: path(ref) });
      } else if (op === "rename") {
        const name = typeof operation.name === "string" ? operation.name.trim() : "";
        if (!name) return errors.push(`operation ${index}: rename needs a name`);
        if (!inScope(operation.collection, index, "collection")) return;
        const from = path(operation.collection);
        table.get(operation.collection).name = name;
        steps.push({ op, collection: operation.collection, name, from, path: path(operation.collection) });
      } else if (op === "move") {
        const { collection, parent } = operation;
        if (!inScope(collection, index, "collection") || !inScope(parent, index, "parent")) return;
        if (collection === scope) return errors.push(`operation ${index}: the project collection itself cannot move`);
        let cursor = parent;
        while (cursor) {
          if (cursor === collection) return errors.push(`operation ${index}: cannot move a collection inside itself`);
          cursor = table.get(cursor).parent;
        }
        const from = path(collection);
        table.get(collection).parent = parent;
        steps.push({ op, collection, parent, from, path: path(collection) });
      } else if (op === "add" || op === "remove") {
        const items = operation.items;
        if (!Array.isArray(items) || !items.length || !items.every(item => KEY.test(item))) {
          return errors.push(`operation ${index}: ${op} needs items as Zotero item keys`);
        }
        if (!inScope(operation.collection, index, "collection")) return;
        steps.push({ op, collection: operation.collection, items, path: path(operation.collection) });
      } else {
        errors.push(`operation ${index}: unknown op ${JSON.stringify(op)}`);
      }
    });
    return { errors, steps, scope };
  }

  const api = { ORGANIZE_TOKEN, resolvePlan };
  global.ZoteroCompanionOrganize = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(this);
