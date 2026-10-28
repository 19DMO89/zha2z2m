"""Websocket API used by the sidebar panel."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import persistent_notification, websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, SKIP, VERSION, ZHA_DOMAIN, format_ieee, normalize_ieee
from .exporter import ExportError, async_export_zha
from .migration import (
    MigrationError,
    async_auto_candidates,
    async_migrate_device,
    async_set_zha_enabled,
    async_suggest,
    async_z2m_devices,
    async_z2m_entities,
    async_zha_active,
    device_display_name,
)
from .references import (
    async_find_references,
    async_replace_device_ids,
    migrated_device_ids,
    scan_files,
)
from .store import MigrationStore

OPTIONS_SCHEMA = {
    vol.Optional("preserve_names", default=True): bool,
    vol.Optional("copy_areas", default=True): bool,
}


@callback
def async_register(hass: HomeAssistant) -> None:
    for command in (
        ws_status,
        ws_export,
        ws_set_zha,
        ws_suggest,
        ws_migrate,
        ws_auto_migrate,
        ws_references,
        ws_replace_references,
    ):
        websocket_api.async_register_command(hass, command)


def _store(hass: HomeAssistant) -> MigrationStore | None:
    return hass.data.get(DOMAIN)


def _not_loaded(connection: websocket_api.ActiveConnection, msg: dict) -> None:
    connection.send_error(msg["id"], "not_loaded", "ZHA2Z2M is not loaded")


@callback
def _status(hass: HomeAssistant, store: MigrationStore) -> dict[str, Any]:
    done = store.migrated_z2m_device_ids()
    return {
        "version": VERSION,
        "exported_at": store.data.get("exported_at"),
        "export_file": store.data.get("export_file"),
        "zha": store.data.get("zha"),
        "zha_installed": bool(hass.config_entries.async_entries(ZHA_DOMAIN)),
        "zha_active": async_zha_active(hass),
        "zha_devices": [
            {
                "ieee": ieee,
                "ieee_display": format_ieee(ieee),
                "name": device_display_name(device),
                "manufacturer": device.get("manufacturer"),
                "model": device.get("model"),
                "area_name": device.get("area_name"),
                "entities": len(device["entities"]),
                "migrated": ieee in store.migrated,
                "z2m_device_id": store.migrated.get(ieee, {}).get("z2m_device_id"),
            }
            for ieee, device in store.devices.items()
        ],
        "z2m_devices": [
            {
                "device_id": device_id,
                "name": device_display_name(device),
                "ieee": ieee,
                "ieee_display": format_ieee(ieee),
                "manufacturer": device.manufacturer,
                "model": device.model,
                "migrated": device_id in done,
                "match": ieee
                if ieee in store.devices and ieee not in store.migrated
                else None,
            }
            for device_id, (device, ieee) in async_z2m_devices(hass).items()
        ],
    }


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/status"})
@callback
def ws_status(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (store := _store(hass)) is None:
        return _not_loaded(connection, msg)
    connection.send_result(msg["id"], _status(hass, store))


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/export"})
@websocket_api.async_response
async def ws_export(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (store := _store(hass)) is None:
        return _not_loaded(connection, msg)
    try:
        export = await async_export_zha(hass, store)
    except ExportError as err:
        connection.send_error(msg["id"], err.key, err.key)
        return
    connection.send_result(
        msg["id"],
        {
            "file": export["export_file"],
            "devices": len(export["devices"]),
            "entities": sum(len(d["entities"]) for d in export["devices"].values()),
            "network_backup": export["zha"]["network_backup_available"],
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/set_zha", vol.Required("enabled"): bool}
)
@websocket_api.async_response
async def ws_set_zha(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (store := _store(hass)) is None:
        return _not_loaded(connection, msg)
    if not msg["enabled"] and not store.has_export:
        connection.send_error(msg["id"], "export_first", "export_first")
        return
    changed = await async_set_zha_enabled(hass, msg["enabled"])
    connection.send_result(msg["id"], {"changed": changed})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/suggest",
        vol.Required("ieee"): str,
        vol.Required("z2m_device_id"): str,
    }
)
@callback
def ws_suggest(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (store := _store(hass)) is None:
        return _not_loaded(connection, msg)
    ieee = normalize_ieee(msg["ieee"])
    if ieee not in store.devices:
        connection.send_error(msg["id"], "unknown_zha_device", "unknown_zha_device")
        return
    if dr.async_get(hass).async_get(msg["z2m_device_id"]) is None:
        connection.send_error(msg["id"], "unknown_z2m_device", "unknown_z2m_device")
        return
    old = store.devices[ieee]
    connection.send_result(
        msg["id"],
        {
            "old_entities": [
                {
                    "entity_id": e["entity_id"],
                    "domain": e["domain"],
                    "name": e.get("friendly_name") or e["entity_id"],
                }
                for e in sorted(old["entities"], key=lambda e: e["entity_id"])
            ],
            "new_entities": [
                {
                    "entity_id": e["entity_id"],
                    "domain": e["domain"],
                    "name": e.get("original_name") or e["domain"],
                }
                for e in sorted(
                    async_z2m_entities(hass, msg["z2m_device_id"]),
                    key=lambda e: e["entity_id"],
                )
            ],
            "mapping": async_suggest(hass, store, ieee, msg["z2m_device_id"]),
            "skip": SKIP,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/migrate",
        vol.Required("ieee"): str,
        vol.Required("z2m_device_id"): str,
        vol.Required("mapping"): {str: str},
        **OPTIONS_SCHEMA,
    }
)
@websocket_api.async_response
async def ws_migrate(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (store := _store(hass)) is None:
        return _not_loaded(connection, msg)
    ieee = normalize_ieee(msg["ieee"])
    try:
        result = await async_migrate_device(
            hass,
            store,
            ieee,
            msg["z2m_device_id"],
            msg["mapping"],
            preserve_names=msg["preserve_names"],
            copy_areas=msg["copy_areas"],
        )
    except MigrationError as err:
        connection.send_error(msg["id"], err.key, err.key)
        return
    persistent_notification.async_dismiss(hass, f"{DOMAIN}_{ieee}")
    connection.send_result(msg["id"], result.as_dict())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/auto_migrate", **OPTIONS_SCHEMA}
)
@websocket_api.async_response
async def ws_auto_migrate(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (store := _store(hass)) is None:
        return _not_loaded(connection, msg)
    results = []
    for ieee, device_id in async_auto_candidates(hass, store):
        try:
            result = await async_migrate_device(
                hass,
                store,
                ieee,
                device_id,
                async_suggest(hass, store, ieee, device_id),
                preserve_names=msg["preserve_names"],
                copy_areas=msg["copy_areas"],
            )
        except MigrationError as err:
            results.append({"ieee": format_ieee(ieee), "error": err.key})
            continue
        persistent_notification.async_dismiss(hass, f"{DOMAIN}_{ieee}")
        results.append(result.as_dict())
    connection.send_result(msg["id"], {"results": results})


async def _references(hass: HomeAssistant, store: MigrationStore) -> dict[str, Any]:
    ids = migrated_device_ids(store.migrated)
    files = await hass.async_add_executor_job(scan_files, hass.config.config_dir, ids)
    automations: set[str] = set()
    scripts: set[str] = set()
    for old_id in ids:
        refs = async_find_references(hass, old_id)
        automations.update(refs.get("automations", []))
        scripts.update(refs.get("scripts", []))
    return {
        "files": files,
        "automations": sorted(automations),
        "scripts": sorted(scripts),
    }


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/references"})
@websocket_api.async_response
async def ws_references(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    if (store := _store(hass)) is None:
        return _not_loaded(connection, msg)
    connection.send_result(msg["id"], await _references(hass, store))


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/replace_references"})
@websocket_api.async_response
async def ws_replace_references(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    if (store := _store(hass)) is None:
        return _not_loaded(connection, msg)
    changed = await async_replace_device_ids(hass, migrated_device_ids(store.migrated))
    connection.send_result(
        msg["id"], {"changed": changed, **(await _references(hass, store))}
    )
