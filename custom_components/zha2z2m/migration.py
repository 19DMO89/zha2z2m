"""Take over names, entity ids, areas and labels from ZHA to Zigbee2MQTT."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)
from homeassistant.util import dt as dt_util

from .const import (
    MQTT_DOMAIN,
    SKIP,
    Z2M_IDENTIFIER_RE,
    ZHA_DOMAIN,
    format_ieee,
    normalize_ieee,
)
from .matcher import suggest_mapping
from .references import async_find_references
from .store import MigrationStore

_LOGGER = logging.getLogger(__name__)


class MigrationError(HomeAssistantError):
    """Raised when a device cannot be migrated."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


@dataclass
class MigrationResult:
    ieee: str
    old_name: str
    new_device_id: str
    renamed: list[tuple[str, str]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    references: dict[str, list[str]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ieee": format_ieee(self.ieee),
            "device": self.old_name,
            "z2m_device_id": self.new_device_id,
            "renamed": [{"from": a, "to": b} for a, b in self.renamed],
            "skipped": self.skipped,
            "failed": [{"entity_id": a, "reason": b} for a, b in self.failed],
            "references": self.references,
        }

    def as_markdown(self) -> str:
        lines = [f"**{self.old_name}** ({format_ieee(self.ieee)})"]
        lines += [f"- ✅ `{new}` → `{old}`" for new, old in self.renamed]
        lines += [f"- ⏭️ `{old}` (no Z2M counterpart)" for old in self.skipped]
        lines += [f"- ❌ `{old}`: {reason}" for old, reason in self.failed]
        refs = [r for items in self.references.values() for r in items]
        if refs:
            lines.append(
                "- ⚠️ Still uses the old device id: " + ", ".join(f"`{r}`" for r in refs)
            )
        return "\n".join(lines)


def device_display_name(device: dict[str, Any] | dr.DeviceEntry) -> str:
    if isinstance(device, dict):
        return device.get("name_by_user") or device.get("name") or device["ieee"]
    return device.name_by_user or device.name or device.id


def z2m_ieee(device: dr.DeviceEntry) -> str:
    for domain, ident in device.identifiers:
        if domain == MQTT_DOMAIN and (match := Z2M_IDENTIFIER_RE.match(ident)):
            return normalize_ieee(match.group(1))
    return ""


@callback
def async_z2m_devices(hass: HomeAssistant) -> dict[str, tuple[dr.DeviceEntry, str]]:
    """All Zigbee2MQTT devices in HA: {device_id: (device, ieee)}."""
    result = {}
    for device in dr.async_get(hass).devices.values():
        if ieee := z2m_ieee(device):
            result[device.id] = (device, ieee)
    return result


@callback
def async_z2m_entities(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    """The MQTT entities of a Zigbee2MQTT device in the same shape as the export."""
    entities = []
    for entry in er.async_entries_for_device(
        er.async_get(hass), device_id, include_disabled_entities=True
    ):
        if entry.platform != MQTT_DOMAIN:
            continue
        state = hass.states.get(entry.entity_id)
        attrs = state.attributes if state else {}
        entities.append(
            {
                "entity_id": entry.entity_id,
                "unique_id": entry.unique_id,
                "domain": entry.domain,
                "original_name": entry.original_name,
                "translation_key": entry.translation_key,
                "device_class": entry.device_class
                or entry.original_device_class
                or attrs.get("device_class"),
                "unit_of_measurement": entry.unit_of_measurement
                or attrs.get("unit_of_measurement"),
            }
        )
    return entities


@callback
def async_zha_active(hass: HomeAssistant) -> bool:
    return any(
        entry.state is ConfigEntryState.LOADED
        for entry in hass.config_entries.async_entries(ZHA_DOMAIN)
    )


async def async_set_zha_enabled(hass: HomeAssistant, enabled: bool) -> int:
    """Enable or disable all ZHA config entries, returns how many changed."""
    changed = 0
    for entry in hass.config_entries.async_entries(ZHA_DOMAIN):
        disabled_by = None if enabled else ConfigEntryDisabler.USER
        if entry.disabled_by == disabled_by:
            continue
        await hass.config_entries.async_set_disabled_by(entry.entry_id, disabled_by)
        changed += 1
    return changed


@callback
def async_suggest(
    hass: HomeAssistant, store: MigrationStore, ieee: str, z2m_device_id: str
) -> dict[str, str]:
    old = store.devices[ieee]
    new_device = dr.async_get(hass).async_get(z2m_device_id)
    return suggest_mapping(
        old["entities"],
        device_display_name(old),
        async_z2m_entities(hass, z2m_device_id),
        device_display_name(new_device) if new_device else "",
    )


def _valid_area(hass: HomeAssistant, area_id: str | None) -> str | None:
    if area_id and ar.async_get(hass).async_get_area(area_id):
        return area_id
    return None


def _valid_labels(hass: HomeAssistant, labels: list[str]) -> set[str]:
    label_reg = lr.async_get(hass)
    return {label for label in labels if label_reg.async_get_label(label)}


def _expected_friendly_name(device_name: str, entry: er.RegistryEntry) -> str:
    if entry.original_name:
        return f"{device_name} {entry.original_name}"
    return device_name


async def async_migrate_device(
    hass: HomeAssistant,
    store: MigrationStore,
    ieee: str,
    z2m_device_id: str,
    mapping: dict[str, str],
    *,
    preserve_names: bool = True,
    copy_areas: bool = True,
) -> MigrationResult:
    """Apply a migration for one device.

    mapping is {old_zha_entity_id: new_z2m_entity_id | SKIP}.
    """
    if async_zha_active(hass):
        raise MigrationError("zha_active")
    if ieee not in store.devices:
        raise MigrationError("unknown_zha_device")

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    new_device = dev_reg.async_get(z2m_device_id)
    if new_device is None:
        raise MigrationError("unknown_z2m_device")

    targets = [t for t in mapping.values() if t != SKIP]
    if len(targets) != len(set(targets)):
        raise MigrationError("duplicate_target")

    old = store.devices[ieee]
    old_entities = {e["entity_id"]: e for e in old["entities"]}
    result = MigrationResult(ieee, device_display_name(old), z2m_device_id)

    # 1. Device: name, area, labels
    device_name = device_display_name(new_device)
    device_changes: dict[str, Any] = {}
    if preserve_names:
        device_name = old.get("name_by_user") or old.get("name") or device_name
        device_changes["name_by_user"] = device_name
    if copy_areas:
        if area_id := _valid_area(hass, old.get("area_id")):
            device_changes["area_id"] = area_id
        if labels := _valid_labels(hass, old.get("labels", [])):
            device_changes["labels"] = set(new_device.labels) | labels
    if device_changes:
        dev_reg.async_update_device(z2m_device_id, **device_changes)

    # 2. Entities: free the old entity id, then give it to the new entity
    for old_id, new_id in mapping.items():
        old_entity = old_entities.get(old_id)
        if old_entity is None:
            continue
        if new_id == SKIP:
            result.skipped.append(old_id)
            continue
        new_entry = ent_reg.async_get(new_id)
        if new_entry is None or new_entry.domain != old_entity["domain"]:
            result.failed.append((old_id, f"{new_id} not found"))
            continue

        existing = ent_reg.async_get(old_id)
        if existing and existing.entity_id != new_id:
            if existing.platform != ZHA_DOMAIN:
                result.failed.append((old_id, f"id is used by {existing.platform}"))
                continue
            # Removing (not renaming) the old registry entry keeps the recorder
            # history under the old entity id, so history continues seamlessly.
            ent_reg.async_remove(old_id)

        changes: dict[str, Any] = {}
        if new_id != old_id:
            changes["new_entity_id"] = old_id
        if old_entity.get("name"):
            changes["name"] = old_entity["name"]
        elif preserve_names and old_entity.get("friendly_name"):
            if old_entity["friendly_name"] != _expected_friendly_name(device_name, new_entry):
                changes["name"] = old_entity["friendly_name"]
        if old_entity.get("icon"):
            changes["icon"] = old_entity["icon"]
        if old_entity.get("aliases"):
            changes["aliases"] = set(new_entry.aliases) | set(old_entity["aliases"])
        if copy_areas:
            if area_id := _valid_area(hass, old_entity.get("area_id")):
                changes["area_id"] = area_id
            if labels := _valid_labels(hass, old_entity.get("labels", [])):
                changes["labels"] = set(new_entry.labels) | labels
        if old_entity.get("hidden_by") == er.RegistryEntryHider.USER:
            changes["hidden_by"] = er.RegistryEntryHider.USER
        if old_entity.get("disabled_by") == er.RegistryEntryDisabler.USER:
            changes["disabled_by"] = er.RegistryEntryDisabler.USER

        try:
            if changes:
                ent_reg.async_update_entity(new_id, **changes)
            for options_domain, options in (old_entity.get("options") or {}).items():
                if options_domain == ZHA_DOMAIN or options_domain.endswith(".private"):
                    continue
                ent_reg.async_update_entity_options(old_id, options_domain, options)
        except (ValueError, HomeAssistantError) as err:
            _LOGGER.warning("Could not migrate %s to %s: %s", new_id, old_id, err)
            result.failed.append((old_id, str(err)))
            continue
        result.renamed.append((new_id, old_id))

    result.references = async_find_references(hass, old["device_id"])

    store.migrated[ieee] = {
        "z2m_device_id": z2m_device_id,
        "old_device_id": old["device_id"],
        "migrated_at": dt_util.now().isoformat(),
        "entities": dict(result.renamed),
        "skipped": result.skipped,
    }
    await store.async_save()
    return result


@callback
def async_auto_candidates(
    hass: HomeAssistant, store: MigrationStore
) -> list[tuple[str, str]]:
    """Pairs (ieee, z2m_device_id) that can be matched by IEEE address."""
    done = store.migrated_z2m_device_ids()
    return [
        (ieee, device_id)
        for device_id, (_, ieee) in async_z2m_devices(hass).items()
        if ieee in store.devices and ieee not in store.migrated and device_id not in done
    ]
