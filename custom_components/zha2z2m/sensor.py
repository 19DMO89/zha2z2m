"""Status sensor that shows the progress of the migration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_UPDATED, format_ieee
from .migration import async_z2m_devices, device_display_name
from .store import MigrationStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([MigrationStatusSensor(hass.data[DOMAIN], entry)])


class MigrationStatusSensor(SensorEntity):
    """Number of exported ZHA devices that are not migrated yet."""

    _attr_has_entity_name = True
    _attr_translation_key = "pending_devices"
    _attr_icon = "mdi:swap-horizontal-bold"
    _attr_native_unit_of_measurement = "devices"
    _attr_should_poll = False

    def __init__(self, store: MigrationStore, entry: ConfigEntry) -> None:
        self._store = store
        self._attr_unique_id = f"{entry.entry_id}_pending"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self._updated)
        )

    @callback
    def _updated(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        if not self._store.has_export:
            return None
        return len(self._store.pending_ieees())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        store = self._store
        found = {ieee for _, ieee in async_z2m_devices(self.hass).values()}
        pending = [
            {
                "name": device_display_name(store.devices[ieee]),
                "ieee": format_ieee(ieee),
                "found_in_z2m": ieee in found,
            }
            for ieee in store.pending_ieees()
        ]
        return {
            "exported_at": store.data.get("exported_at"),
            "export_file": store.data.get("export_file"),
            "exported_devices": len(store.devices),
            "migrated_devices": len(store.migrated),
            "pending": pending,
        }
