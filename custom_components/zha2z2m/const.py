"""Constants for the ZHA → Zigbee2MQTT migration helper."""

from __future__ import annotations

import re

DOMAIN = "zha2z2m"

# Keep in sync with manifest.json (checked by the release workflow).
VERSION = "0.1.0"

PANEL_URL_PATH = DOMAIN
PANEL_STATIC_URL = f"/{DOMAIN}_static"
PANEL_ELEMENT = "zha2z2m-panel"
PANEL_TITLE = "ZHA → Z2M"
PANEL_ICON = "mdi:swap-horizontal-bold"
CONF_SHOW_IN_SIDEBAR = "show_in_sidebar"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

EXPORT_DIR = "zha2z2m"
EXPORT_LATEST = "zha_export_latest.json"
COORDINATOR_BACKUP_FILE = "coordinator_backup.json"
Z2M_SNIPPET_FILE = "z2m_configuration_snippet.yaml"

SIGNAL_UPDATED = f"{DOMAIN}_updated"

ZHA_DOMAIN = "zha"
MQTT_DOMAIN = "mqtt"

# Zigbee2MQTT registers its devices in Home Assistant with the identifier
# ("mqtt", "zigbee2mqtt_0x00158d0001234567"). Groups and the bridge use other
# patterns and are ignored on purpose.
Z2M_IDENTIFIER_RE = re.compile(r"^zigbee2mqtt_(0x[0-9a-fA-F]{16})$")

CONF_PRESERVE_NAMES = "preserve_names"
CONF_COPY_AREAS = "copy_areas"
CONF_Z2M_DEVICE = "z2m_device"
CONF_ZHA_DEVICE = "zha_device"
CONF_CONFIRM = "confirm"
CONF_REPLACE_YAML = "replace_yaml"

SKIP = "__skip__"

# Mapping of ZHA radio types to the matching Zigbee2MQTT adapter setting.
RADIO_TO_Z2M_ADAPTER = {
    "ezsp": "ember",
    "znp": "zstack",
    "deconz": "deconz",
    "zigate": "zigate",
    "xbee": None,
}

# YAML files whose device ids can be rewritten after a migration.
REFERENCE_FILES = ("automations.yaml", "scripts.yaml", "scenes.yaml")


def normalize_ieee(value: str) -> str:
    """Return an IEEE address as 16 lowercase hex chars, or "" if invalid."""
    cleaned = value.strip().lower().replace(":", "").replace("-", "")
    if cleaned.startswith("0x"):
        cleaned = cleaned[2:]
    if re.fullmatch(r"[0-9a-f]{16}", cleaned):
        return cleaned
    return ""


def format_ieee(ieee: str) -> str:
    """Format a normalized IEEE address the way Zigbee2MQTT shows it."""
    return f"0x{ieee}"
