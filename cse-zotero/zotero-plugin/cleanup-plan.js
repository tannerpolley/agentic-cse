/* global module */

(function (global) {
  "use strict";

  const APPLY_TOKEN = "ZOTERO-COMPANION-APPLY-v1";
  const SEARCH_TOKEN = "ZOTERO-COMPANION-SEARCHES-v1";

  const MANUAL_TAG_MAPPINGS = [
    ["★", "priority:key"],
    ["Review", "role:review"],
    ["Presentation", "role:presentation"],
    ["Machine Learning", "method:machine-learning"],
    ["Uncertainty Quantification", "method:uncertainty-quantification"],
    ["Simulation", "method:simulation"],
    ["Thermodynamics", "topic:thermodynamics"],
    ["Transport", "topic:transport"]
  ];

  const WORKFLOW_TAGS = [
    { name: "status:to-read", color: "#5B8FF9", position: 0 },
    { name: "status:reading", color: "#F6BD16", position: 1 },
    { name: "status:reviewed", color: "#5AD8A6", position: 2 },
    { name: "priority:key", color: "#E8684A", position: 3 }
  ];

  const WORKFLOW_SEARCHES = [
    ["Workflow — To Read", "status:to-read"],
    ["Workflow — Reading", "status:reading"],
    ["Workflow — Reviewed", "status:reviewed"],
    ["Workflow — Key Papers", "priority:key"]
  ];

  function asNumber(value) {
    return Number(value || 0);
  }

  function summarizeRows(rows) {
    const manual = {};
    const automatic = {};
    let manualAssignments = 0;
    let automaticAssignments = 0;
    for (const row of rows || []) {
      const name = String(row.name ?? row.tag ?? "");
      const type = asNumber(row.type);
      const count = asNumber(row.count ?? row.assignments ?? 0);
      if (type === 1) {
        automatic[name] = (automatic[name] || 0) + count;
        automaticAssignments += count;
      } else {
        manual[name] = (manual[name] || 0) + count;
        manualAssignments += count;
      }
    }
    const mappingNames = new Set(MANUAL_TAG_MAPPINGS.flat());
    const unexpectedManualTags = Object.keys(manual)
      .filter(name => !mappingNames.has(name))
      .sort();
    const mappings = MANUAL_TAG_MAPPINGS
      .filter(([oldName]) => manual[oldName])
      .map(([oldName, newName]) => ({
        oldName,
        newName,
        assignments: manual[oldName]
      }));
    return {
      automaticAssignments,
      automaticTags: automatic,
      manualAssignments,
      manualTags: manual,
      mappings,
      unexpectedManualTags,
      workflowTags: WORKFLOW_TAGS
    };
  }

  function getConfig() {
    return {
      applyToken: APPLY_TOKEN,
      searchToken: SEARCH_TOKEN,
      manualTagMappings: MANUAL_TAG_MAPPINGS.map(([oldName, newName]) => ({ oldName, newName })),
      workflowTags: WORKFLOW_TAGS,
      workflowSearches: WORKFLOW_SEARCHES.map(([name, tag]) => ({ name, tag }))
    };
  }

  const api = {
    APPLY_TOKEN,
    SEARCH_TOKEN,
    MANUAL_TAG_MAPPINGS,
    WORKFLOW_TAGS,
    WORKFLOW_SEARCHES,
    getConfig,
    summarizeRows
  };

  global.ZoteroCompanionPlan = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(this);
