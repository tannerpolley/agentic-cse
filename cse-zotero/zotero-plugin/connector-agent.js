/* Agent jobs use the native Connector; ordinary tabs keep its ordinary behavior. */
(() => {
  const CONNECTOR_VERSION = "5.0.217";
  const MODULE_REVISION = 19;
  const marker = Zotero.getExtensionURL("cse-agent-job.html") + "#";
  const agentTabs = new Set();
  let active = null, busy = false;
  const api = async (action, data = {}) => {
    const response = await fetch("http://127.0.0.1:23119/zotero-companion/acquire-job", {
      method: "POST", headers: { "Content-Type": "application/json", "X-Zotero-Connector-API-Version": "3", "X-Zotero-Version": Zotero.version },
      body: JSON.stringify({ action, ...data }), signal: AbortSignal.timeout(5000)
    });
    if (!response.ok) throw Error("CSE job channel HTTP " + response.status);
    return response.json();
  };
  const sendMessage = Zotero.Messaging.sendMessage;
  Zotero.Messaging.sendMessage = function(name, args, tab, ...rest) {
    if (agentTabs.has(tab?.id) && active?.tabs.has(tab.id) && name === "progressWindow.done") active.ok = Boolean(args[0]);
    return sendMessage.call(this, name, args, tab, ...rest);
  };
  const callMethod = Zotero.Connector.callMethod;
  Zotero.Connector.callMethod = function(options, data, tab, ...rest) {
    const method = typeof options === "string" ? options : options.method;
    if (agentTabs.has(tab?.id) && active?.tabs.has(tab.id) && ["saveItems", "saveSnapshot"].includes(method)) active.session_id = data.sessionID;
    return callMethod.call(this, options, data, tab, ...rest);
  };
  for (const [object, name] of [[Zotero.BotBypass, "passJSDetectionViaWindowPrompt"], [Zotero.Connector_Browser, "openWindow"]]) {
    const original = object[name];
    object[name] = async function(url, ...args) {
      const tab = name === "openWindow" ? args[1] : args[0];
      if (!agentTabs.has(tab?.id)) return original.call(this, url, ...args);
      if (active?.tabs.has(tab.id)) {
        active.handoff = url;
        active.stop = { reason: "Publisher requires a human save", cooldown: true };
      }
      throw Error("Publisher requires a human save");
    };
  }
  chrome.webRequest.onHeadersReceived.addListener(d => {
    if (active?.tab !== d.tabId || d.type !== "main_frame") return;
    active.status = d.statusCode;
    active.challenge = d.responseHeaders?.some(h => h.name.toLowerCase() === "cf-mitigated" && h.value === "challenge");
  }, { urls: ["<all_urls>"] }, ["responseHeaders"]);
  async function run(job) {
    const a = active = { ...job, url: job.url, title: "", status: null, session_id: null, tabs: new Set() };
    try {
      const window = await chrome.windows.create({ url: [marker + job.id, job.url], state: "normal", focused: false });
      a.window = window.id; a.tab = window.tabs[1].id;
      for (const tab of window.tabs) { a.tabs.add(tab.id); agentTabs.add(tab.id); }
      await chrome.tabs.update(a.tab, { active: true });
      let stableURL, stableSince, checkSince, started = false;
      while (Date.now() < job.deadline && !a.stop && a.ok === undefined) {
        const tab = await chrome.tabs.get(a.tab);
        if (tab.url !== "about:blank" && tab.status === "complete") {
          a.url = tab.url; a.title = tab.title || "";
          if (a.status === 429 || a.challenge || /just a moment|checking your browser|verify you are human|captcha/i.test(a.title)) {
            checkSince ??= Date.now();
            if (Date.now() - checkSince >= 15000) {
              a.stop = { reason: a.status === 429 ? "Publisher HTTP 429" : "Publisher check did not clear within 15 seconds", cooldown: true };
              a.handoff = a.url;
            }
          } else {
            checkSince = undefined;
            if (stableURL !== tab.url) { stableURL = tab.url; stableSince = Date.now(); }
            if (!started && Date.now() - stableSince >= 3000) {
              const translators = Zotero.Connector_Browser.getTabInfo(tab.id).translators || [];
              if (!translators.length) { a.handoff = "no Zotero translator for this page (login, check page or unsupported)"; break; }
              if (translators[0].itemType === "multiple") { a.handoff = "Multiple-item page; open one paper to save"; break; }
              started = true;
              Promise.resolve(Zotero.Connector_Browser.saveWithTranslator(tab, 0)).catch(error => { a.handoff = String(error); a.ok = false; });
            }
          }
        }
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      if (a.ok === undefined && !a.stop && !a.handoff) a.handoff = "Connector attempt timed out; save with the normal Zotero Connector";
    } catch (error) { a.handoff ||= String(error); }
    finally {
      if (a.window) await chrome.windows.remove(a.window).catch(() => {});
      // ponytail: native work after this 60-second tab retention is left to the Connector.
      setTimeout(() => { for (const id of a.tabs) agentTabs.delete(id); }, 60000);
      active = null;
      await api("finish", { id: job.id, result: { session_id: a.session_id, ok: a.ok === true,
        stop: a.stop || null, handoff: a.handoff || null, url: a.url, title: a.title, status: a.status } });
    }
  }
  async function tick() {
    if (busy) return;
    busy = true;
    try {
      await chrome.runtime.getPlatformInfo();
      const result = await api("pickup", { protocol: 1, version: Zotero.version, supported_version: CONNECTOR_VERSION,
        module_revision: MODULE_REVISION, compatible: Zotero.version === CONNECTOR_VERSION });
      if (!result.job && result.expected_revision > MODULE_REVISION) {
        const key = "cseAgentReloadRevision", stored = await chrome.storage.local.get(key);
        if (stored[key] !== result.expected_revision) {
          await chrome.storage.local.set({ [key]: result.expected_revision }); chrome.runtime.reload();
        }
      } else if (result.job) await run(result.job);
    } catch (error) { Zotero.logError(error); }
    finally { busy = false; }
  }
  Zotero.initDeferred.promise.then(async () => {
    for (const window of await chrome.windows.getAll({ populate: true })) {
      if (window.tabs[0]?.url?.startsWith(marker)) await chrome.windows.remove(window.id).catch(() => {});
    }
    setInterval(tick, 20000); tick();
  }).catch(error => Zotero.logError(error));
})();
