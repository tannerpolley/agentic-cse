/* global ChromeUtils, Components, Services, Zotero */

var ZoteroCompanionBootstrap = {
  scope: null,

  startup({ rootURI }) {
    // Services is available through the legacy import on Zotero 7-9 and keeps
    // this bootstrapped plugin independent of the active Zotero window.
    if (typeof Services === "undefined") {
      ({ Services } = Components.utils.import("resource://gre/modules/Services.jsm"));
    }

    this.scope = { Zotero };
    Services.scriptloader.loadSubScript(rootURI + "cleanup-plan.js", this.scope);
    Services.scriptloader.loadSubScript(rootURI + "zotero-companion.js", this.scope);
    this.scope.ZoteroCompanion.start(this.scope.ZoteroCompanionPlan);
  },

  shutdown() {
    if (this.scope && this.scope.ZoteroCompanion) {
      this.scope.ZoteroCompanion.stop();
    }
    this.scope = null;
  },

  install() {},
  uninstall() {}
};

function startup(data, reason) {
  ZoteroCompanionBootstrap.startup(data, reason);
}

function shutdown(data, reason) {
  ZoteroCompanionBootstrap.shutdown(data, reason);
}

function install(data, reason) {
  ZoteroCompanionBootstrap.install(data, reason);
}

function uninstall(data, reason) {
  ZoteroCompanionBootstrap.uninstall(data, reason);
}
