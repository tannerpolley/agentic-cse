/* Agent jobs only. The official Connector's toolbar and ordinary tabs are unchanged. */
(() => {
  const CONNECTOR_VERSION = "5.0.217";
  const MODULE_REVISION = 4;
  const KEY = "cseAgentJob", RULE = 900000000;
  let active = null, busy = false;
  const retiredTabs = new Set(), retiredSessions = new Set();
  const retire = a => {
    if (Number.isInteger(a.tab)) retiredTabs.add(a.tab);
    if (a.session_id) retiredSessions.add(a.session_id);
  };
  const host = url => new URL(url).hostname.toLowerCase().replace(/\.+$/, "");
  const safeURL = url => { const u = new URL(url); u.username = u.password = ""; return u.href; };
  const agentTab = tab => active && tab?.id === active.tab;
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
      if (interactive && !a.interactiveUntil) {
        a.interactiveUntil = Date.now() + 300000;
        a.deadline += 300000;
        api("progress", { id: a.id, result: { check: { kind, url: safeURL(url) } } }).catch(() => {
          try { halt("Check notification channel failed; no retry", url); } catch (_) {}
        });
      }
      a.autoUntil ||= Date.now() + 15000;
      a.check = { kind, url, status, until: interactive ? a.interactiveUntil : a.autoUntil };
    } else if (status >= 200 && status < 400) a.check = null;
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
    await chrome.storage.local.set({ [KEY]: { id: a.id, window: a.window, tab: a.tab, session_id: a.session_id } });
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
    check(final, r.status, text.startsWith("%PDF") ? "" : text,
      [{ name: "cf-mitigated", value: r.getResponseHeader?.("cf-mitigated") },
       { name: "x-amzn-waf-action", value: r.getResponseHeader?.("x-amzn-waf-action") }]);
    if (options.csePDF && r.status !== 404) pdf(r.response, final);
    if ((options.successCodes === null && (r.status < 200 || r.status >= 300)) ||
        (Array.isArray(options.successCodes) && !options.successCodes.includes(r.status))) {
      const error = new Zotero.HTTP.StatusError(r, url, r.responseText);
      delete error.retryAfter;
      throw error;
    }
    return r;
  };
  const fetchAttachment = Zotero.ItemSaver._fetchAttachment;
  Zotero.ItemSaver._fetchAttachment = async function(attachment, tab, ...args) {
    if (retiredTabs.has(tab?.id)) throw Error("Agent tab is closed");
    if (!agentTab(tab)) return fetchAttachment.call(this, attachment, tab, ...args);
    live(active);
    let cookies;
    try { cookies = await Zotero.Connector_Browser.getAllCookies({ url: attachment.url, partitionKey: {} }, tab); }
    catch (_) { cookies = await Zotero.Connector_Browser.getAllCookies({ url: attachment.url }, tab); }
    const r = await Zotero.HTTP.request("GET", attachment.url, {
      cseJob: active.id, csePDF: attachment.mimeType === "application/pdf", maxBackoff: 0,
      responseType: "arraybuffer", timeout: 30000, successCodes: false, referrer: attachment.referrer,
      headers: { Cookie: cookies.filter(c => c.partitionKey).map(c => c.name + "=" + c.value).join("; ") }
    });
    const error = this._validateResponse(attachment, r);
    if (r.status < 200 || r.status >= 400 || error) throw Error("Connector attachment failed: HTTP " + r.status);
    return r.response;
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
  for (const key of ["bypassAmazonCaptcha", "passJSDetectionViaHiddenIframe", "passJSDetectionViaWindowPrompt"]) {
    const original = Zotero.BotBypass[key];
    Zotero.BotBypass[key] = function(target, tab, ...args) {
      if (agentTab(tab) || tab?.cseJob) halt("Connector challenge bypass blocked", target.url || target, true);
      return original.call(this, target, tab, ...args);
    };
  }
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
    if (!active || active.done || d.tabId !== active.tab) return;
    try {
      valid(d.url);
      if (d.type === "main_frame") {
        active.status = d.statusCode;
        pageCheck(d.url, d.statusCode, "", d.responseHeaders || []);
      } else if (active.check && (d.responseHeaders || []).some(h =>
        (h.name.toLowerCase() === "cf-mitigated" && h.value === "challenge") ||
        (h.name.toLowerCase() === "x-amzn-waf-action" && ["challenge", "captcha"].includes(h.value)))) {
        pageCheck(active.check.url, d.statusCode, "", d.responseHeaders);
      } else check(d.url, d.statusCode, "", d.responseHeaders || []);
    } catch (_) {}
  }, { urls: ["<all_urls>"] }, ["responseHeaders"]);
  const inspect = tab => {
    if (tab.url === "about:blank") return;
    active.url = safeURL(tab.url || active.url); active.title = tab.title || "";
    valid(tab.url);
    pageCheck(tab.url, active.status, active.title);
    if (/^(login|sign in|log in)$/i.test(active.title.trim()) || /\/(login|signin|sign-in)(?:[/?#]|$)/i.test(tab.url))
      halt("Publisher login wall", tab.url, true);
  };
  chrome.tabs.onUpdated.addListener((id, _change, tab) => {
    if (!active || active.done || id !== active.tab) return;
    try { inspect(tab); } catch (_) {}
  });

  async function recover() {
    const pending = (await chrome.storage.local.get(KEY))[KEY];
    if (!pending) return;
    if ((await chrome.storage.session.get(KEY))[KEY] === pending.id) {
      retire(pending);
      if (pending.window) await chrome.windows.remove(pending.window).catch(() => {});
    } else if (pending.session_id) retiredSessions.add(pending.session_id);
    await chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [RULE] });
    const result = pending.result || { session_id: pending.session_id, error: "Connector worker restarted; no retry" };
    await api("finish", { id: pending.id, result }).catch(error => { if (!error.message.endsWith("404")) throw error; });
    await chrome.storage.local.remove(KEY);
    await chrome.storage.session.remove(KEY);
  }
  async function run(job) {
    const a = active = { ...job, url: job.url, title: "", status: null, session_id: null };
    try {
      await checkpoint(a);
      const window = await chrome.windows.create({ url: "about:blank", state: "minimized", focused: false });
      a.window = window.id; a.tab = window.tabs[0].id;
      await checkpoint(a);
      const domains = Object.entries(a.cooldowns).filter(([h, t]) => h.includes(".") && t > Date.now() / 1000).map(([h]) => h);
      await chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [RULE], addRules: domains.length ? [{
        id: RULE, priority: 10000, action: { type: "block" }, condition: { requestDomains: domains, tabIds: [a.tab] }
      }] : [] });
      live(a); valid(a.url);
      await chrome.tabs.update(a.tab, { url: a.url });
      let saving = false;
      while (!a.stop && !a.finished && Date.now() < a.deadline) {
        const tab = await chrome.tabs.get(a.tab);
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
      retire(a);
      if (a.window) await chrome.windows.remove(a.window).catch(() => {});
      await chrome.declarativeNetRequest.updateSessionRules({ removeRuleIds: [RULE] });
      const result = { session_id: a.session_id, stop: a.stop || null, error: a.error || null,
        url: a.url, title: a.title, status: a.stop?.status ?? a.status };
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
