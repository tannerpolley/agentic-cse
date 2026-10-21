"""Paths for live-corpus integration checks kept outside the package checkout."""

from zotero_companion.config import load_config


CONFIG = load_config()
WIKI_ROOT = CONFIG.wiki_root
REGISTRY_ROOT = CONFIG.data_root / "domains" / "thermophysical" / "source" / "registry"
NORMALIZED_RECORDS = (
    CONFIG.data_root / "domains" / "thermophysical" / "normalized" / "registry-records.csv"
)
