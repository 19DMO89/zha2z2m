"""Config flow and the migration wizard (options flow)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CONFIRM,
    CONF_COPY_AREAS,
    CONF_PRESERVE_NAMES,
    CONF_REPLACE_YAML,
    CONF_SHOW_IN_SIDEBAR,
    CONF_Z2M_DEVICE,
    CONF_ZHA_DEVICE,
    DOMAIN,
    EXPORT_DIR,
    SKIP,
    ZHA_DOMAIN,
    format_ieee,
)
from .exporter import ExportError, async_export_zha
from .matcher import candidates
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
from .references import async_replace_device_ids, migrated_device_ids, scan_files
from .store import MigrationStore


class Zha2Z2MConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create the (single) migration helper entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="ZHA → Zigbee2MQTT Migration", data={})
        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MigrationWizard()


class MigrationWizard(OptionsFlow):
    """Step by step wizard: export → disable ZHA → migrate devices → fix references."""

    def __init__(self) -> None:
        self._z2m_device_id: str | None = None
        self._ieee: str | None = None
        self._preserve_names = True
        self._copy_areas = True

    @property
    def _store(self) -> MigrationStore:
        return self.hass.data[DOMAIN]

    def _done(self, result: str) -> ConfigFlowResult:
        return self.async_show_form(
            step_id="done", description_placeholders={"result": result}
        )

    async def async_step_done(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_create_entry(data=dict(self.config_entry.options))

    # ------------------------------------------------------------------ menu

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        store = self._store
        z2m_found = {ieee for _, ieee in async_z2m_devices(self.hass).values()}
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "export",
                "disable_zha",
                "migrate",
                "auto_migrate",
                "references",
                "enable_zha",
                "settings",
            ],
            description_placeholders={
                "exported_at": store.data.get("exported_at") or "–",
                "exported": str(len(store.devices)),
                "migrated": str(len(store.migrated)),
                "ready": str(len(set(store.pending_ieees()) & z2m_found)),
                "zha_state": "active" if async_zha_active(self.hass) else "inactive",
            },
        )

    # ---------------------------------------------------------------- export

    async def async_step_export(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                export = await async_export_zha(self.hass, self._store)
            except ExportError as err:
                errors["base"] = err.key
            else:
                entities = sum(len(d["entities"]) for d in export["devices"].values())
                lines = [
                    f"✅ {len(export['devices'])} devices / {entities} entities exported.",
                    f"File: `{export['export_file']}`",
                ]
                if export["zha"]["network_backup_available"]:
                    lines.append(
                        f"🔑 Network backup: `{EXPORT_DIR}/coordinator_backup.json` and "
                        f"`{EXPORT_DIR}/z2m_configuration_snippet.yaml`"
                    )
                return self._done("\n\n".join(lines))
        return self.async_show_form(step_id="export", errors=errors)

    # ----------------------------------------------------------- disable ZHA

    async def async_step_disable_zha(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        store = self._store
        if not store.has_export:
            return self.async_abort(reason="export_first")
        if user_input is not None:
            if not user_input.get(CONF_CONFIRM):
                return self.async_create_entry(data=dict(self.config_entry.options))
            await async_set_zha_enabled(self.hass, False)
            return self._done("✅ ZHA disabled.")

        zha = store.data.get("zha", {})
        return self.async_show_form(
            step_id="disable_zha",
            data_schema=vol.Schema(
                {vol.Required(CONF_CONFIRM, default=False): BooleanSelector()}
            ),
            description_placeholders={
                "port": zha.get("port") or "?",
                "radio": zha.get("radio_type") or "?",
                "adapter": zha.get("z2m_adapter") or "?",
                "entries": str(len(self.hass.config_entries.async_entries(ZHA_DOMAIN))),
            },
        )

    async def async_step_enable_zha(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            if user_input.get(CONF_CONFIRM):
                await async_set_zha_enabled(self.hass, True)
                return self._done("✅ ZHA enabled again.")
            return self.async_create_entry(data=dict(self.config_entry.options))
        return self.async_show_form(
            step_id="enable_zha",
            data_schema=vol.Schema(
                {vol.Required(CONF_CONFIRM, default=False): BooleanSelector()}
            ),
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={**self.config_entry.options, **user_input}
            )
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SHOW_IN_SIDEBAR,
                        default=self.config_entry.options.get(CONF_SHOW_IN_SIDEBAR, True),
                    ): BooleanSelector()
                }
            ),
        )

    # -------------------------------------------------------- migrate device

    async def async_step_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        store = self._store
        if not store.has_export:
            return self.async_abort(reason="export_first")
        if async_zha_active(self.hass):
            return self.async_abort(reason="zha_active")

        if user_input is not None:
            self._z2m_device_id = user_input[CONF_Z2M_DEVICE]
            return await self.async_step_migrate_source()

        done = store.migrated_z2m_device_ids()
        options = []
        for device_id, (device, ieee) in sorted(
            async_z2m_devices(self.hass).items(),
            key=lambda item: device_display_name(item[1][0]).lower(),
        ):
            if device_id in done:
                continue
            label = f"{device_display_name(device)} ({format_ieee(ieee)})"
            if ieee in store.devices and ieee not in store.migrated:
                label += f"  ✓ ZHA: {device_display_name(store.devices[ieee])}"
            options.append(SelectOptionDict(value=device_id, label=label))
        if not options:
            return self.async_abort(reason="no_z2m_devices")

        return self.async_show_form(
            step_id="migrate",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_Z2M_DEVICE): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def async_step_migrate_source(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        store = self._store
        assert self._z2m_device_id
        if user_input is not None and CONF_ZHA_DEVICE in user_input:
            self._ieee = user_input[CONF_ZHA_DEVICE]
            self._preserve_names = user_input[CONF_PRESERVE_NAMES]
            self._copy_areas = user_input[CONF_COPY_AREAS]
            return await self.async_step_migrate_entities()

        _, z2m_ieee = async_z2m_devices(self.hass)[self._z2m_device_id]
        options = [
            SelectOptionDict(
                value=ieee,
                label=(
                    f"{device_display_name(device)} – {device.get('manufacturer') or ''} "
                    f"{device.get('model') or ''} ({format_ieee(ieee)})"
                    + ("  ✓ same IEEE" if ieee == z2m_ieee else "")
                ),
            )
            for ieee, device in sorted(
                store.devices.items(), key=lambda i: device_display_name(i[1]).lower()
            )
            if ieee not in store.migrated
        ]
        if not options:
            return self.async_abort(reason="nothing_pending")

        default = z2m_ieee if z2m_ieee in store.devices else vol.UNDEFINED
        return self.async_show_form(
            step_id="migrate_source",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZHA_DEVICE, default=default): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    ),
                    vol.Required(CONF_PRESERVE_NAMES, default=True): BooleanSelector(),
                    vol.Required(CONF_COPY_AREAS, default=True): BooleanSelector(),
                }
            ),
            description_placeholders={
                "z2m_device": device_display_name(
                    dr.async_get(self.hass).async_get(self._z2m_device_id)
                )
            },
        )

    async def async_step_migrate_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        store = self._store
        assert self._ieee and self._z2m_device_id
        old = store.devices[self._ieee]
        new_entities = async_z2m_entities(self.hass, self._z2m_device_id)
        errors: dict[str, str] = {}

        if user_input is not None and all(
            e["entity_id"] in user_input for e in old["entities"]
        ):
            try:
                result = await async_migrate_device(
                    self.hass,
                    store,
                    self._ieee,
                    self._z2m_device_id,
                    user_input,
                    preserve_names=self._preserve_names,
                    copy_areas=self._copy_areas,
                )
            except MigrationError as err:
                errors["base"] = err.key
            else:
                persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_{self._ieee}")
                return self._done(result.as_markdown())

        suggestion = async_suggest(self.hass, store, self._ieee, self._z2m_device_id)
        schema: dict[Any, Any] = {}
        for entity in sorted(old["entities"], key=lambda e: e["entity_id"]):
            options = [SelectOptionDict(value=SKIP, label="— skip / not available —")]
            options += [
                SelectOptionDict(
                    value=new["entity_id"],
                    label=f"{new['entity_id']} ({new.get('original_name') or new['domain']})",
                )
                for new in candidates(entity, new_entities)
            ]
            default = (user_input or {}).get(entity["entity_id"]) or suggestion.get(
                entity["entity_id"], SKIP
            )
            schema[vol.Required(entity["entity_id"], default=default)] = SelectSelector(
                SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
            )

        if not schema:
            return self.async_abort(reason="no_entities")

        return self.async_show_form(
            step_id="migrate_entities",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "zha_device": device_display_name(old),
                "z2m_device": device_display_name(
                    dr.async_get(self.hass).async_get(self._z2m_device_id)
                ),
            },
        )

    # ---------------------------------------------------------- auto migrate

    async def async_step_auto_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        store = self._store
        if not store.has_export:
            return self.async_abort(reason="export_first")
        if async_zha_active(self.hass):
            return self.async_abort(reason="zha_active")
        pairs = async_auto_candidates(self.hass, store)
        if not pairs:
            return self.async_abort(reason="no_auto_candidates")

        if user_input is not None:
            results = []
            for ieee, device_id in pairs:
                try:
                    result = await async_migrate_device(
                        self.hass,
                        store,
                        ieee,
                        device_id,
                        async_suggest(self.hass, store, ieee, device_id),
                        preserve_names=user_input[CONF_PRESERVE_NAMES],
                        copy_areas=user_input[CONF_COPY_AREAS],
                    )
                except MigrationError as err:
                    results.append(f"❌ {format_ieee(ieee)}: {err.key}")
                else:
                    persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_{ieee}")
                    results.append(result.as_markdown())
            return self._done("\n\n".join(results))

        devices = dr.async_get(self.hass)
        listing = "\n".join(
            f"- {device_display_name(store.devices[ieee])} → "
            f"{device_display_name(devices.async_get(device_id))}"
            for ieee, device_id in pairs
        )
        return self.async_show_form(
            step_id="auto_migrate",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRESERVE_NAMES, default=True): BooleanSelector(),
                    vol.Required(CONF_COPY_AREAS, default=True): BooleanSelector(),
                }
            ),
            description_placeholders={"devices": listing},
        )

    # ------------------------------------------------------------ references

    async def async_step_references(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        store = self._store
        ids = migrated_device_ids(store.migrated)
        if not ids:
            return self.async_abort(reason="nothing_migrated")

        if user_input is not None:
            changed: list[str] = []
            if user_input.get(CONF_REPLACE_YAML):
                changed = await async_replace_device_ids(self.hass, ids)
            report = await self.hass.async_add_executor_job(
                scan_files, self.hass.config.config_dir, ids
            )
            lines = [
                "✅ Updated: " + ", ".join(f"`{c}`" for c in changed)
                if changed
                else "No file was changed."
            ]
            lines += _report_lines(report)
            return self._done("\n\n".join(lines))

        report = await self.hass.async_add_executor_job(
            scan_files, self.hass.config.config_dir, ids
        )
        return self.async_show_form(
            step_id="references",
            data_schema=vol.Schema(
                {vol.Required(CONF_REPLACE_YAML, default=False): BooleanSelector()}
            ),
            description_placeholders={
                "report": "\n".join(_report_lines(report)) or "✅ Nothing found."
            },
        )


def _report_lines(report: dict[str, dict[str, int]]) -> list[str]:
    lines = []
    for file, counts in report.items():
        parts = []
        if counts["device_ids"]:
            parts.append(f"{counts['device_ids']}× old device id")
        if counts["zha_device_automations"]:
            parts.append(f"{counts['zha_device_automations']}× `domain: zha` (rebuild!)")
        if counts["zha_event"]:
            parts.append(f"{counts['zha_event']}× `zha_event` (rebuild!)")
        lines.append(f"- `{file}`: " + ", ".join(parts))
    return lines
