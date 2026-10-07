/* Agent jobs only. The official Connector's toolbar and ordinary tabs are unchanged. */
(() => {
  const CONNECTOR_VERSION = "5.0.217";
  const MODULE_REVISION = 9;
  const KEY = "cseAgentJob", RULE = 900000000;
  const RULES = [RULE, ...ZoteroCompanionURL.blocked.map((_, i) => RULE + i + 1)];
  const marker = Zotero.getExtensionURL("cse-agent-job.html") + "#";
  let active = null, busy = false;
  const host = url => new URL(url).hostname.toLowerCase().replace(/\.+$/, "");
  const safeURL = url => { const u = new URL(url); u.username = u.password = ""; return u.href; };
  const agentTab = tab => active && (tab?.id === active.tab || tab?.id === active.prompt?.tab);
  const monitorURL = url => url.startsWith(Zotero.getExtensionURL("browserAttachmentMonitor/browserAttachmentMonitor.html"));
  const challenge = text => ["just a moment", "captcha", "cf-chl-", "unusual activity", "access denied",
    "verify you are human", "pow_challenge", "sign in to access", "log in to access", "login required"]
    .find(s => text.toLowerCase().includes(s));
  const api = async (action, data = {}) => {
    const response = await fetch("http://127.0.0.1:23119/zotero-companion/acquire-job", {
      method: "POST", headers: { "Content-Type": "application/json", "X-Zotero-Connector-API-Version": "3", "X-Zotero-Version": Zotero.version },
      body: JSON.stringify({ action, ...data }), signal: AbortSignal.timeout(5000)
    });
    if (!response.ok) throw Error("CSE job channel HTTP " + response.status);
    return response.json();
  };
  const live = a => {
    if (!a || a !== active || a.done || a.stop || Date.now() >= a.deadline)
      throw Error("Agent attempt stopped; no retry");
  };
  const halt = (reason, url, cooldown = false, status = null) => {
    const a = active;
    if (a && !a.stop) {
      a.stop = { reason, host: host(url || a.url), url: safeURL(url || a.url), cooldown, status };
      if (a.window) chrome.windows.remove(a.window).catch(() => {});
      if (a.prompt) chrome.windows.remove(a.prompt.window).catch(() => {});
    }
    throw Error("Agent attempt stopped; no retry");
  };
  const valid = url => {
    try { ZoteroCompanionURL.parse(url); } catch (_) { halt("Unsafe remote URL", url); }
    if (active.cooldowns[host(url)] > Date.now() / 1000) halt("Responding host cooldown active", url);
  };
  const check = (url, status, text = "", headers = []) => {
    const found = challenge(text);
    const cloudflare = headers.some(h => h.name.toLowerCase() === "cf-mitigated" && h.value === "challenge");
    const amazon = headers.some(h => h.name.toLowerCase() === "x-amzn-waf-action" && ["challenge", "captcha"].includes(h.value));
    if (found || cloudflare || amazon) halt("Publisher access challenge: " + (found || (cloudflare ? "Cloudflare" : "CAPTCHA")), url, true, status);
    if ([401, 403, 429].includes(status)) halt("Publisher HTTP " + status + "; no retry", url, status === 429, status);
  };
  const pageCheck = (url, status, text = "", headers = []) => {
    const a = active, lower = text.toLowerCase();
    if (status === 429 || ["access denied", "unusual activity", "login required", "sign in to access", "log in to access"].some(s => lower.includes(s)))
      return check(url, status, text, headers);
    const interactive = /captcha|verify you are human|human verification/.test(lower) ||
      headers.some(h => h.name.toLowerCase() === "x-amzn-waf-action" && h.value === "captcha");
    const automatic = /just a moment|checking (?:your browser|if)|pow_challenge/.test(lower) ||
      headers.some(h => h.name.toLowerCase() === "cf-mitigated" && h.value === "challenge");
    if (interactive || automatic) {
      if (!interactive && a.check?.kind === "interactive") return;
      const kind = interactive ? "interactive" : "automatic";
      if (interactive && !a.interactiveUntil) {
        a.interactiveUntil = Date.now() + 300000;
        a.deadline += 300000;
        chrome.windows.update(a.prompt?.window || a.window, { state: "minimized", focused: false }).catch(() => {});
        api("progress", { id: a.id, result: { check: { kind, url: safeURL(url) } } }).catch(() => {
          try { halt("Check notification channel failed; no retry", url); } catch (_) {}
        });
      }
      a.autoUntil ||= Date.now() + 15000;
      a.check = { kind, url, status, until: interactive ? a.interactiveUntil : a.autoUntil };
    } else if (status >= 200 && status < 400 && !a.prompt) a.check = null;
    else if (!a.check && [401, 403].includes(status)) check(url, status, text, headers);
  };
  // Inspect snapshots the official Connector already sends; never inject or interact.
  const offscreen = Zotero.OffscreenManager.sendMessage;
  Zotero.OffscreenManager.sendMessage = function(message, payload, tab, ...args) {
    if (agentTab(tab) && message === "Translate.setDocument") {
      const html = payload[0].replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, "");
      let signal = html.match(/<title\b[^>]*>([\s\S]*?)<\/title>/i)?.[1] || "";
      if (/\b(?:type|role)\s*=\s*["']?checkbox/i.test(html) && /verify you are human|captcha/i.test(html.replace(/<[^>]*>/g, " ")))
        signal += " Verify you are human";
      if (challenge(signal)) pageCheck(active.url, active.status, signal);
    }
    return offscreen.call(this, message, payload, tab, ...args);
  };
  const checkpoint = async a => {
    await chrome.storage.local.set({ [KEY]: { id: a.id, window: a.window, tab: a.tab, prompt: a.prompt, session_id: a.session_id } });
    await chrome.storage.session.set({ [KEY]: a.id });
    await api("progress", { id: a.id, result: { checkpoint: Number.isInteger(a.window) } });
  };
  const callMethod = Zotero.Connector.callMethod;
  Zotero.Connector.callMethod = async function(options, data, tab) {
    if (agentTab(tab) && (typeof options === "string" ? options : options.method) === "saveItems") {
      const a = active;
      a.session_id = data.sessionID;
      await api("prepare", { id: a.id, session_id: a.session_id, metadata: data.items?.[0] || {} });
      await checkpoint(a);
    }
    return callMethod.call(this, options, data, tab);
  };
  const prompt = Zotero.BotBypass.passJSDetectionViaWindowPrompt;
  Zotero.BotBypass.passJSDetectionViaWindowPrompt = async function(url, tab) {
    if (!agentTab(tab)) return prompt.call(this, url, tab);
    const a = active;
    live(a); valid(url);
    const window = await chrome.windows.create({ url: [marker + a.id, Zotero.getExtensionURL("browserAttachmentMonitor/browserAttachmentMonitor.html")],
      type: "popup", state: "minimized", focused: false });
    a.prompt = { window: window.id, tab: window.tabs[1].id, url };
    try {
      await chrome.tabs.update(a.prompt.tab, { active: true });
      live(a); await checkpoint(a); await blockCooldowns(a);
      pageCheck(url, null, "CAPTCHA");
      return await Zotero.BrowserAttachmentMonitor.waitForAttachment(a.prompt.tab, url, Math.max(1, a.interactiveUntil - Date.now()));
    } catch (_) {
      if (!a.stop) halt(Date.now() >= a.interactiveUntil ? "Interactive publisher check unanswered after 5 minutes"
        : "Interactive publisher check closed or failed; no retry", url);
      throw Error("Agent attempt stopped; no retry");
    } finally {
      await chrome.windows.remove(window.id).catch(() => {});
      a.prompt = null; a.check = null;
    }
  };
  const sendMessage = Zotero.Messaging.sendMessage;
  Zotero.Messaging.sendMessage = function(name, args, tab, ...rest) {
    if (agentTab(tab) && name === "progressWindow.done") {
      active.finished = true;
      if (!args[0]) active.error = "Connector reported translation failure";
      if (args[1] === "siteAccessLimits") halt("Connector reported publisher access limits", active.url, true);
    }
    return sendMessage.call(this, name, args, tab, ...rest);
  };
  chrome.webRequest.onHeadersReceived.addListener(d => {
    const a = active;
    if (!a || a.done) return;
    const owned = agentTab({ id: d.tabId });
    const background = d.tabId === -1 && d.initiator === "chrome-extension://" + chrome.runtime.id;
    if (!owned && !background) return;
    const headers = d.responseHeaders || [];
    const signal = headers.find(h => (h.name.toLowerCase() === "cf-mitigated" && h.value.toLowerCase() === "challenge") ||
      (h.name.toLowerCase() === "x-amzn-waf-action" && ["challenge", "captcha"].includes(h.value.toLowerCase())));
    if (d.statusCode === 429 || signal) {
      const responding = host(d.url), reason = d.statusCode === 429 ? "Publisher HTTP 429" : "Publisher access check: " + signal.name;
      if (!a.observations[responding] || d.statusCode === 429) {
        a.observations[responding] = { host: responding, status: d.statusCode, reason, cooldown: true, at: Date.now() / 1000 };
        api("progress", { id: a.id, result: { observations: Object.values(a.observations) } }).catch(() => {});
      }
    }
    // Observe the navigation response; the job loop owns waits and handoff.
    if (owned && d.type === "main_frame" && !monitorURL(d.url)) {
      if (d.tabId === a.tab) { a.status = d.statusCode; a.headers = headers; }
      else a.prompt.status = d.statusCode;
    }
  }, { urls: ["<all_urls>"] }, ["responseHeaders"]);
  for (const event of [chrome.webRequest.onBeforeRequest, chrome.webRequest.onBeforeRedirect]) event.addListener(d => {
    if (!active || active.done || d.type !== "main_frame" || !agentTab({ id: d.tabId })) return;
    const url = d.redirectUrl || d.url;
    if (d.tabId === active.prompt?.tab && monitorURL(url)) return;
    try { valid(url); } catch (_) {}
  }, { urls: ["<all_urls>"] });
  const inspect = tab => {
    if (tab.url === "about:blank" || (tab.id === active.prompt?.tab && monitorURL(tab.url))) return;
    if (tab.id === active.tab) { active.url = safeURL(tab.url || active.url); active.title = tab.title || ""; }
    valid(tab.url);
    pageCheck(tab.url, tab.id === active.tab ? active.status : active.prompt.status, tab.title || "", tab.id === active.tab ? active.headers || [] : []);
    if (/^(login|sign in|log in)$/i.test((tab.title || "").trim()) || /\/(login|signin|sign-in)(?:[/?#]|$)/i.test(tab.url))
      halt("Publisher login wall", tab.url, true);
  };
  chrome.tabs.onUpdated.addListener((id, _change, tab) => {
    if (!active || active.done || !agentTab({ id })) return;
    try { inspect(tab); } catch (_) {}
  });

  async function recover() {
    const pending = (await chrome.storage.local.get(KEY))[KEY];
    const windows = await chrome.windows.getAll({ populate: true });
    for (const window of windows) if (window.tabs?.some(tab => tab.url?.startsWith(marker)))
      await chrome.windows.remove(window.id).catch(() => {});
    await chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: RULES });
    if (!pending) return;
    if ((await chrome.storage.session.get(KEY))[KEY] === pending.id) {
      if (pending.window) await chrome.windows.remove(pending.window).catch(() => {});
      if (pending.prompt) await chrome.windows.remove(pending.prompt.window).catch(() => {});
    }
    const result = pending.result || { session_id: pending.session_id, error: "Connector worker restarted; no retry" };
    await api("finish", { id: pending.id, result }).catch(error => { if (!error.message.endsWith("404")) throw error; });
    await chrome.storage.local.remove(KEY);
    await chrome.storage.session.remove(KEY);
  }
  async function blockCooldowns(a) {
    const domains = Object.entries(a.cooldowns).filter(([h, t]) => h.includes(".") && t > Date.now() / 1000).map(([h]) => h);
    await chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: RULES, addRules: [
      ...ZoteroCompanionURL.blocked.map((regexFilter, i) => ({
        id: RULE + i + 1, priority: 10000, action: { type: "block" }, condition: {
          regexFilter, resourceTypes: ["main_frame"], tabIds: [a.tab, a.prompt?.tab].filter(Number.isInteger) } })),
      ...(domains.length ? [{ id: RULE, priority: 10000, action: { type: "block" }, condition: {
        requestDomains: domains, tabIds: [a.tab, -1, a.prompt?.tab].filter(Number.isInteger) } }] : [])
    ] });
  }
  async function run(job) {
    const a = active = { ...job, url: job.url, title: "", status: null, session_id: null, observations: {} };
    try {
      valid(a.url);
      await checkpoint(a);
      const window = await chrome.windows.create({ url: [marker + a.id, "about:blank"], state: "minimized", focused: false });
      a.window = window.id; a.tab = window.tabs[1].id;
      await checkpoint(a);
      await blockCooldowns(a);
      live(a); valid(a.url);
      await chrome.tabs.update(a.tab, { url: a.url, active: true });
      let saving = false;
      while (!a.stop && !a.finished && Date.now() < a.deadline) {
        const tab = await chrome.tabs.get(a.tab);
        if (tab.url === "about:blank") { await new Promise(resolve => setTimeout(resolve, 250)); continue; }
        inspect(tab);
        if (a.check) {
          if (Date.now() >= a.check.until) halt(a.check.kind === "automatic"
            ? "Automatic publisher check did not clear within 15 seconds"
            : "Interactive publisher check unanswered after 5 minutes", a.check.url, a.check.kind === "automatic", a.check.status);
          await new Promise(resolve => setTimeout(resolve, 250));
          continue;
        }
        const info = Zotero.Connector_Browser.getTabInfo(a.tab);
        if (!saving && tab.status === "complete" && info.translators?.length) {
          if (info.translators[0].itemType === "multiple") halt("Multiple-paper page refused", a.url);
          saving = true;
          Zotero.Connector_Browser.saveWithTranslator(tab, 0, { fallbackOnFailure: false })
            .catch(() => { a.error = "Connector could not save this paper"; a.finished = true; });
        }
        await new Promise(resolve => setTimeout(resolve, 250));
      }
      if (!a.stop && !a.finished) halt("Connector attempt timed out; no reload or retry", a.url);
    } catch (_) {
      if (!a.stop) a.error = "Connector attempt failed or disconnected; no retry";
    } finally {
      a.done = true;
      if (a.window) await chrome.windows.remove(a.window).catch(() => {});
      if (a.prompt) await chrome.windows.remove(a.prompt.window).catch(() => {});
      await chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: RULES });
      const result = { session_id: a.session_id, stop: a.stop || null, error: a.error || null,
        url: a.url, title: a.title, status: a.stop?.status ?? a.status, observations: Object.values(a.observations) };
      await chrome.storage.local.set({ [KEY]: { id: a.id, result } });
      active = null;
      await recover();
    }
  }
  async function poll() {
    chrome.runtime.getPlatformInfo(); // Reset MV3's idle timer without changing the official manifest.
    if (!busy) await recover();
    const response = await api("pickup", { protocol: 1, version: Zotero.version, supported_version: CONNECTOR_VERSION, module_revision: MODULE_REVISION,
      compatible: Zotero.version === CONNECTOR_VERSION });
    if (!busy && !active && !response.job && response.expected_revision > MODULE_REVISION) {
      busy = true;
      try {
        const key = "cseAgentReloadRevision", revision = response.expected_revision;
        if (((await chrome.storage.local.get(key))[key] || 0) < revision) {
          await chrome.storage.local.set({ [key]: revision });
          chrome.runtime.reload();
        }
      } finally { busy = false; }
      return;
    }
    if (active && response.cancelled) { try { halt("Connector attempt cancelled; no retry", active.url); } catch (_) {} }
    if (response.job && !busy) {
      busy = true;
      try { await run(response.job); } finally { busy = false; }
    }
  }
  const tick = () => Zotero.initDeferred.promise.then(poll).catch(() => {});
  chrome.runtime.onStartup.addListener(tick);
  setInterval(tick, 20000);
  tick();
})();
