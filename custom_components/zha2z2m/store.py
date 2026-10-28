"""Persistent state of the migration (export snapshot + migrated devices)."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import SIGNAL_UPDATED, STORAGE_KEY, STORAGE_VERSION


class MigrationStore:
    """Wraps the Home Assistant storage file of this integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] = {}

    async def async_load(self) -> None:
        self.data = await self._store.async_load() or {}
        self.data.setdefault("devices", {})
        self.data.setdefault("migrated", {})

    async def async_save(self) -> None:
        await self._store.async_save(self.data)
        self.async_notify()

    @callback
    def async_notify(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)

    @property
    def has_export(self) -> bool:
        return bool(self.data.get("exported_at"))

    @property
    def devices(self) -> dict[str, dict[str, Any]]:
        """Exported ZHA devices keyed by normalized IEEE address."""
        return self.data["devices"]

    @property
    def migrated(self) -> dict[str, dict[str, Any]]:
        """Finished migrations keyed by normalized IEEE address."""
        return self.data["migrated"]

    def pending_ieees(self) -> list[str]:
        return [ieee for ieee in self.devices if ieee not in self.migrated]

    def migrated_z2m_device_ids(self) -> set[str]:
        return {m["z2m_device_id"] for m in self.migrated.values()}

    def set_export(self, export: dict[str, Any]) -> None:
        """Replace the snapshot but keep the information about migrated devices."""
        migrated = self.migrated
        self.data = {**export, "migrated": migrated}
