/* Agent jobs only. The official Connector's toolbar and ordinary tabs are unchanged. */
(() => {
  const CONNECTOR_VERSION = "5.0.217";
  const MODULE_REVISION = 5;
  const KEY = "cseAgentJob", WINDOW_STATE = "cseAgentWindowState", RULE = 900000000;
  let active = null, busy = false;
  const retiredTabs = new Set(), retiredSessions = new Set();
  const retire = a => {
    if (Number.isInteger(a.tab)) retiredTabs.add(a.tab);
    if (Number.isInteger(a.prompt?.tab)) retiredTabs.add(a.prompt.tab);
    if (a.session_id) retiredSessions.add(a.session_id);
  };
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
    const u = new URL(url);
    if (!["http:", "https:"].includes(u.protocol) || u.username || u.password) halt("Unsafe remote URL", url);
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
      if (a.diagnostic && !a.diagnostic.checks.some(c => c.kind === kind))
        a.diagnostic.checks.push({ kind, status, url: safeURL(url), elapsed_ms: Date.now() - a.diagnostic.started });
      if (interactive && !a.interactiveUntil && !a.diagnostic) {
        a.interactiveUntil = Date.now() + 300000;
        a.deadline += 300000;
        chrome.windows.update(a.prompt?.window || a.window, { state: "minimized", focused: false }).catch(() => {});
        api("progress", { id: a.id, result: { check: { kind, url: safeURL(url) } } }).catch(() => {
          try { halt("Check notification channel failed; no retry", url); } catch (_) {}
        });
      }
      a.autoUntil ||= Date.now() + 15000;
      a.check = { kind, url, status, until: interactive && !a.diagnostic ? a.interactiveUntil : a.autoUntil };
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
  const pdf = (bytes, url) => {
    if (!(bytes instanceof ArrayBuffer) || new TextDecoder().decode(new Uint8Array(bytes).slice(0, 4)) !== "%PDF")
      halt("Non-PDF bytes where a PDF was expected", url);
    if (bytes.byteLength > 52428800) halt("PDF exceeds 50 MiB limit", url);
  };
  const checkpoint = async a => {
    await chrome.storage.local.set({ [KEY]: { id: a.id, window: a.window, tab: a.tab, prompt: a.prompt, session_id: a.session_id } });
    await chrome.storage.session.set({ [KEY]: a.id });
  };

  // Native message dispatch supplies the source tab; tag only that job's requests.
  const cohttp = Zotero.COHTTP.request, low = Zotero.HTTP._requestFetch;
  Zotero.COHTTP.request = function(method, url, options, tab) {
    if (retiredTabs.has(tab?.id)) throw Error("Agent tab is closed");
    return cohttp.call(this, method, url, agentTab(tab) ? { ...options, cseJob: active.id, maxBackoff: 0 } : options, tab);
  };
  Zotero.HTTP._requestFetch = async function(method, url, options) {
    if (!options.cseJob) return low.call(this, method, url, options);
    const a = active;
    live(a);
    if (options.cseJob !== a.id) throw Error("Agent job expired");
    const u = new URL(url);
    if (u.hostname === "127.0.0.1" || (u.protocol === "chrome-extension:" && u.hostname === chrome.runtime.id))
      return low.call(this, method, url, { ...options, maxBackoff: 0 });
    valid(url);
    options.maxBackoff = 0;
    const r = await low.call(this, method, url, { ...options, successCodes: false });
    live(a);
    const final = r.responseURL || url;
    valid(final);
    const bytes = r.response instanceof ArrayBuffer ? new Uint8Array(r.response) : null;
    const text = bytes ? new TextDecoder().decode(bytes.slice(0, 200000)) : typeof r.response === "string" ? r.response.slice(0, 200000) : "";
    const headers =
      [{ name: "cf-mitigated", value: r.getResponseHeader?.("cf-mitigated") },
       { name: "x-amzn-waf-action", value: r.getResponseHeader?.("x-amzn-waf-action") }];
    const blocked = [401, 429].includes(r.status) || /access denied|unusual activity|login required|sign in to access|log in to access/i.test(text);
    const bypass = !blocked && options.cseBotBypass && options.cseAttachment &&
      (r.status < 200 || r.status >= 400 || Zotero.ItemSaver._validateResponse(options.cseAttachment, r)) &&
      Zotero.BotBypass.canBotBypass(options.cseAttachment.url, r) !== Zotero.BotBypass.BYPASS_TYPE.NONE;
    if (!bypass) {
      check(final, r.status, text.startsWith("%PDF") ? "" : text, headers);
      if (options.csePDF && r.status !== 404) pdf(r.response, final);
    }
    if ((options.successCodes === null && (r.status < 200 || r.status >= 300)) ||
        (Array.isArray(options.successCodes) && !options.successCodes.includes(r.status))) {
      const error = new Zotero.HTTP.StatusError(r, url, r.responseText);
      delete error.retryAfter;
      throw error;
    }
    return r;
  };
  Zotero.CSEAgent = { attachmentOptions(attachment, tab, bypass) {
    if (retiredTabs.has(tab?.id)) throw Error("Agent tab is closed");
    if (!agentTab(tab)) return {};
    live(active);
    return { cseJob: active.id, csePDF: attachment.mimeType === "application/pdf", cseAttachment: attachment, cseBotBypass: bypass, maxBackoff: 0 };
  } };
  const fetchAttachment = Zotero.ItemSaver._fetchAttachment, attempted = new WeakSet();
  Zotero.ItemSaver._fetchAttachment = function(attachment, tab, bypass = true) {
    if (retiredTabs.has(tab?.id)) throw Error("Agent tab is closed");
    if (!agentTab(tab)) return fetchAttachment.call(this, attachment, tab, bypass);
    live(active);
    bypass = bypass && !attempted.has(attachment);
    attempted.add(attachment);
    return fetchAttachment.call(this, attachment, tab, bypass);
  };
  const callMethod = Zotero.Connector.callMethod;
  Zotero.Connector.callMethod = async function(options, data, tab) {
    const sid = typeof options === "object" && options.queryString?.match(/(?:^|&)sessionID=([^&]+)/)?.[1];
    if (retiredTabs.has(tab?.id) || (sid && retiredSessions.has(sid))) throw Error("Agent save is closed");
    if (agentTab(tab) || (sid && sid === active?.session_id)) {
      const a = active;
      live(a);
      const method = typeof options === "string" ? options : options.method;
      if (method === "saveItems") {
        if (data.items?.length !== 1) halt("Multiple-paper page refused", a.url);
        a.session_id = data.sessionID;
        await checkpoint(a);
        await api("progress", { id: a.id, result: { session_id: a.session_id } });
      }
      if (method === "saveAttachment" && options.headers?.["Content-Type"] === "application/pdf") pdf(data, a.url);
    }
    return callMethod.call(this, options, data, tab);
  };
  const amazon = Zotero.BotBypass.bypassAmazonCaptcha;
  Zotero.BotBypass.bypassAmazonCaptcha = function(attachment, options) {
    if (!options.cseJob) return amazon.call(this, attachment, options);
    live(active);
    return amazon.call(this, attachment, { ...options, cseBotBypass: false });
  };
  const iframe = Zotero.BotBypass.passJSDetectionViaHiddenIframe;
  Zotero.BotBypass.passJSDetectionViaHiddenIframe = async function(url, tab) {
    if (!agentTab(tab)) return iframe.call(this, url, tab);
    const a = active;
    live(a); valid(url); a.hidden = true;
    try { return await iframe.call(this, url, tab); }
    finally { a.hidden = false; }
  };
  const prompt = Zotero.BotBypass.passJSDetectionViaWindowPrompt;
  Zotero.BotBypass.passJSDetectionViaWindowPrompt = async function(url, tab) {
    if (!agentTab(tab)) return prompt.call(this, url, tab);
    const a = active;
    live(a); valid(url);
    const window = await chrome.windows.create({ url: Zotero.getExtensionURL("browserAttachmentMonitor/browserAttachmentMonitor.html"),
      type: "popup", state: "minimized", focused: false });
    a.prompt = { window: window.id, tab: window.tabs[0].id, url };
    try {
      live(a); await checkpoint(a); await blockCooldowns(a);
      pageCheck(url, null, "CAPTCHA");
      return await Zotero.BrowserAttachmentMonitor.waitForAttachment(a.prompt.tab, url, Math.max(1, a.interactiveUntil - Date.now()));
    } catch (_) {
      if (!a.stop) halt(Date.now() >= a.interactiveUntil ? "Interactive publisher check unanswered after 5 minutes"
        : "Interactive publisher check closed or failed; no retry", url);
      throw Error("Agent attempt stopped; no retry");
    } finally {
      retiredTabs.add(window.tabs[0].id);
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
    if (!active || active.done || !agentTab({ id: d.tabId }) || monitorURL(d.url)) return;
    try {
      valid(d.url);
      if (active.hidden && d.type === "sub_frame" && ![401, 429].includes(d.statusCode) && Zotero.BotBypass.isUrlWhitelisted(d.url)) return;
      if (d.type === "main_frame") {
        if (d.tabId === active.tab) active.status = d.statusCode;
        else active.prompt.status = d.statusCode;
        pageCheck(d.url, d.statusCode, "", d.responseHeaders || []);
      } else if (active.check && (d.responseHeaders || []).some(h =>
        (h.name.toLowerCase() === "cf-mitigated" && h.value === "challenge") ||
        (h.name.toLowerCase() === "x-amzn-waf-action" && ["challenge", "captcha"].includes(h.value)))) {
        pageCheck(active.check.url, d.statusCode, "", d.responseHeaders);
      } else check(d.url, d.statusCode, "", d.responseHeaders || []);
    } catch (_) {}
  }, { urls: ["<all_urls>"] }, ["responseHeaders"]);
  const inspect = tab => {
    if (tab.url === "about:blank" || monitorURL(tab.url)) return;
    if (tab.id === active.tab) { active.url = safeURL(tab.url || active.url); active.title = tab.title || ""; }
    valid(tab.url);
    pageCheck(tab.url, tab.id === active.tab ? active.status : active.prompt.status, tab.title || "");
    if (/^(login|sign in|log in)$/i.test((tab.title || "").trim()) || /\/(login|signin|sign-in)(?:[/?#]|$)/i.test(tab.url))
      halt("Publisher login wall", tab.url, true);
  };
  chrome.tabs.onUpdated.addListener((id, _change, tab) => {
    if (!active || active.done || !agentTab({ id })) return;
    try { inspect(tab); } catch (_) {}
  });

  async function recover() {
    const pending = (await chrome.storage.local.get(KEY))[KEY];
    if (!pending) return;
    if ((await chrome.storage.session.get(KEY))[KEY] === pending.id) {
      retire(pending);
      if (pending.window) await chrome.windows.remove(pending.window).catch(() => {});
      if (pending.prompt) await chrome.windows.remove(pending.prompt.window).catch(() => {});
    } else if (pending.session_id) retiredSessions.add(pending.session_id);
    await chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [RULE] });
    const result = pending.result || { session_id: pending.session_id, error: "Connector worker restarted; no retry" };
    await api("finish", { id: pending.id, result }).catch(error => { if (!error.message.endsWith("404")) throw error; });
    await chrome.storage.local.remove(KEY);
    await chrome.storage.session.remove(KEY);
  }
  async function blockCooldowns(a) {
    const domains = Object.entries(a.cooldowns).filter(([h, t]) => h.includes(".") && t > Date.now() / 1000).map(([h]) => h);
    await chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [RULE], addRules: domains.length ? [{
      id: RULE, priority: 10000, action: { type: "block" }, condition: { requestDomains: domains, tabIds: [a.tab, a.prompt?.tab].filter(Number.isInteger) }
    }] : [] });
  }
  async function run(job) {
    const a = active = { ...job, url: job.url, title: "", status: null, session_id: null };
    try {
      // One public test load; never translate or save it to the library.
      if (job.publisher === "connector-window-diagnostic") {
        if (job.url !== "https://nowsecure.nl/") throw Error("Unsupported diagnostic URL");
        a.diagnostic = { phases: [], checks: [], focus_window: (await chrome.windows.getLastFocused()).id, state: "minimized" };
      }
      await checkpoint(a);
      const preferred = (await chrome.storage.local.get(WINDOW_STATE))[WINDOW_STATE];
      const window = await chrome.windows.create({ url: "about:blank", state: !a.diagnostic && preferred === "normal" ? "normal" : "minimized", focused: false });
      a.window = window.id; a.tab = window.tabs[0].id;
      await checkpoint(a);
      await blockCooldowns(a);
      live(a); valid(a.url);
      if (a.diagnostic) a.diagnostic.started = Date.now();
      await chrome.tabs.update(a.tab, { url: a.url });
      let saving = false;
      while (!a.stop && !a.finished && Date.now() < a.deadline) {
        const tab = await chrome.tabs.get(a.tab);
        inspect(tab);
        if (a.diagnostic) {
          const elapsed = Date.now() - a.diagnostic.started;
          const cleared = !a.check && a.status >= 200 && a.status < 400 && tab.status === "complete";
          if (cleared || elapsed >= 15000) {
            const observed = await chrome.windows.get(a.window);
            a.diagnostic.phases.push({ state: a.diagnostic.state, cleared, elapsed_ms: elapsed, status: a.status, title: a.title,
              check: a.check?.kind || null, observed_state: observed.state, observed_focused: observed.focused });
            if (cleared || a.diagnostic.state === "normal") {
              a.diagnostic.focus_unchanged = (await chrome.windows.getLastFocused()).id === a.diagnostic.focus_window;
              if (cleared && a.diagnostic.focus_unchanged) await chrome.storage.local.set({ [WINDOW_STATE]: a.diagnostic.state });
              a.finished = true; break;
            }
            await chrome.windows.update(a.window, { state: "normal", focused: false });
            a.diagnostic.state = "normal"; a.diagnostic.started = Date.now(); a.autoUntil = Date.now() + 15000;
            if (a.check) a.check.until = a.autoUntil;
          }
          await new Promise(resolve => setTimeout(resolve, 250));
          continue;
        }
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
      retire(a);
      if (a.window) await chrome.windows.remove(a.window).catch(() => {});
      if (a.prompt) await chrome.windows.remove(a.prompt.window).catch(() => {});
      await chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [RULE] });
      const result = { session_id: a.session_id, stop: a.stop || null, error: a.error || null,
        url: a.url, title: a.title, status: a.stop?.status ?? a.status, ...(a.diagnostic ? { diagnostic: a.diagnostic } : {}) };
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
