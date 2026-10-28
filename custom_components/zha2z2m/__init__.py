"""ZHA → Zigbee2MQTT migration helper."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    Event,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    CONF_COPY_AREAS,
    CONF_PRESERVE_NAMES,
    DOMAIN,
    format_ieee,
    normalize_ieee,
)
from .exporter import ExportError, async_export_zha
from .migration import (
    MigrationError,
    async_auto_candidates,
    async_migrate_device,
    async_set_zha_enabled,
    async_suggest,
    async_z2m_devices,
    device_display_name,
    z2m_ieee,
)
from .panel import async_remove_panel, async_update_panel
from .references import async_replace_device_ids, migrated_device_ids, scan_files
from .store import MigrationStore
from .websocket import async_register as async_register_websocket

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

MIGRATE_SCHEMA = vol.Schema(
    {
        vol.Required("z2m_device_id"): cv.string,
        vol.Optional("zha_ieee"): cv.string,
        vol.Optional(CONF_PRESERVE_NAMES, default=True): cv.boolean,
        vol.Optional(CONF_COPY_AREAS, default=True): cv.boolean,
    }
)
AUTO_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_PRESERVE_NAMES, default=True): cv.boolean,
        vol.Optional(CONF_COPY_AREAS, default=True): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    store = MigrationStore(hass)
    await store.async_load()
    hass.data[DOMAIN] = store

    _async_register_services(hass, store)
    if not hass.data.get(f"{DOMAIN}_ws_registered"):
        async_register_websocket(hass)
        hass.data[f"{DOMAIN}_ws_registered"] = True
    await async_update_panel(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    @callback
    def _device_created(event: Event) -> None:
        if event.data.get("action") != "create":
            return
        device = dr.async_get(hass).async_get(event.data["device_id"])
        if device is None or not (ieee := z2m_ieee(device)):
            return
        if ieee not in store.devices or ieee in store.migrated:
            return
        old = store.devices[ieee]
        persistent_notification.async_create(
            hass,
            f"Zigbee2MQTT found **{device_display_name(device)}** "
            f"({format_ieee(ieee)}), which was **{device_display_name(old)}** in ZHA.\n\n"
            "Open *Settings → Devices & services → \"ZHA → Zigbee2MQTT Migration\" → "
            "Configure → Migrate a device* to take over names, entity ids and areas.",
            title="ZHA → Zigbee2MQTT: device found",
            notification_id=f"{DOMAIN}_{ieee}",
        )
        store.async_notify()

    entry.async_on_unload(
        hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, _device_created)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_update_panel(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        async_remove_panel(hass)
        hass.data.pop(DOMAIN, None)
        for service in hass.services.async_services_for_domain(DOMAIN):
            hass.services.async_remove(DOMAIN, service)
    return unloaded


@callback
def _async_register_services(hass: HomeAssistant, store: MigrationStore) -> None:
    async def export(call: ServiceCall) -> ServiceResponse:
        try:
            result = await async_export_zha(hass, store)
        except ExportError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key=err.key
            ) from err
        return {
            "file": result["export_file"],
            "devices": len(result["devices"]),
            "entities": sum(len(d["entities"]) for d in result["devices"].values()),
        }

    async def disable_zha(call: ServiceCall) -> None:
        if not store.has_export:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="export_first"
            )
        await async_set_zha_enabled(hass, False)

    async def enable_zha(call: ServiceCall) -> None:
        await async_set_zha_enabled(hass, True)

    async def _migrate(ieee: str, device_id: str, call: ServiceCall) -> dict:
        try:
            result = await async_migrate_device(
                hass,
                store,
                ieee,
                device_id,
                async_suggest(hass, store, ieee, device_id),
                preserve_names=call.data[CONF_PRESERVE_NAMES],
                copy_areas=call.data[CONF_COPY_AREAS],
            )
        except MigrationError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key=err.key
            ) from err
        persistent_notification.async_dismiss(hass, f"{DOMAIN}_{ieee}")
        return result.as_dict()

    async def migrate_device(call: ServiceCall) -> ServiceResponse:
        device_id = call.data["z2m_device_id"]
        z2m = async_z2m_devices(hass).get(device_id)
        if z2m is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unknown_z2m_device"
            )
        ieee = normalize_ieee(call.data.get("zha_ieee") or z2m[1])
        if ieee not in store.devices:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unknown_zha_device"
            )
        return await _migrate(ieee, device_id, call)

    async def auto_migrate(call: ServiceCall) -> ServiceResponse:
        results = [
            await _migrate(ieee, device_id, call)
            for ieee, device_id in async_auto_candidates(hass, store)
        ]
        return {"migrated": results}

    async def replace_device_references(call: ServiceCall) -> ServiceResponse:
        ids = migrated_device_ids(store.migrated)
        changed = await async_replace_device_ids(hass, ids)
        report = await hass.async_add_executor_job(
            scan_files, hass.config.config_dir, ids
        )
        return {"changed_files": changed, "remaining": report}

    hass.services.async_register(
        DOMAIN, "export", export, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(DOMAIN, "disable_zha", disable_zha)
    hass.services.async_register(DOMAIN, "enable_zha", enable_zha)
    hass.services.async_register(
        DOMAIN,
        "migrate_device",
        migrate_device,
        schema=MIGRATE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "auto_migrate",
        auto_migrate,
        schema=AUTO_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "replace_device_references",
        replace_device_references,
        supports_response=SupportsResponse.OPTIONAL,
    )
