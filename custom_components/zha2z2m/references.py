"""Find and replace old ZHA device ids in automations, scripts and scenes.

Entity ids are taken over by the migration, so everything that references
entities keeps working. Only things that reference a *device id* (device
triggers/conditions/actions or `target: device_id`) need attention.
"""

from __future__ import annotations

import glob
import os
import shutil

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import REFERENCE_FILES


@callback
def async_find_references(hass: HomeAssistant, device_id: str) -> dict[str, list[str]]:
    """Automations and scripts that still use a device id."""
    result: dict[str, list[str]] = {}
    try:
        from homeassistant.components.automation import (  # noqa: PLC0415
            automations_with_device,
        )

        if found := automations_with_device(hass, device_id):
            result["automations"] = sorted(found)
    except ImportError:
        pass
    try:
        from homeassistant.components.script import scripts_with_device  # noqa: PLC0415

        if found := scripts_with_device(hass, device_id):
            result["scripts"] = sorted(found)
    except ImportError:
        pass
    return result


def scan_files(config_dir: str, device_ids: dict[str, str]) -> dict[str, dict[str, int]]:
    """Count device id usages and ZHA specific constructs per file.

    Returns {file: {"device_ids": n, "zha_device_automations": n, "zha_event": n}}.
    """
    files = [os.path.join(config_dir, name) for name in REFERENCE_FILES]
    files += glob.glob(os.path.join(config_dir, ".storage", "lovelace*"))
    report: dict[str, dict[str, int]] = {}
    for path in files:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        counts = {
            "device_ids": sum(text.count(old) for old in device_ids),
            "zha_device_automations": text.count("domain: zha"),
            "zha_event": text.count("zha_event"),
        }
        if any(counts.values()):
            report[os.path.relpath(path, config_dir)] = counts
    return report


def replace_device_ids(config_dir: str, device_ids: dict[str, str]) -> list[str]:
    """Replace old device ids with new ones in the YAML files (with backup)."""
    changed = []
    stamp = dt_util.now().strftime("%Y%m%d_%H%M%S")
    for name in REFERENCE_FILES:
        path = os.path.join(config_dir, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        new_text = text
        for old, new in device_ids.items():
            new_text = new_text.replace(old, new)
        if new_text == text:
            continue
        shutil.copy2(path, f"{path}.zha2z2m_{stamp}.bak")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(new_text)
        changed.append(name)
    return changed


async def async_replace_device_ids(
    hass: HomeAssistant, device_ids: dict[str, str]
) -> list[str]:
    """Rewrite the YAML files and reload what changed."""
    changed = await hass.async_add_executor_job(
        replace_device_ids, hass.config.config_dir, device_ids
    )
    for name in changed:
        domain = name.removesuffix("s.yaml")
        if hass.services.has_service(domain, "reload"):
            await hass.services.async_call(domain, "reload", blocking=True)
    return changed


def migrated_device_ids(migrated: dict[str, dict]) -> dict[str, str]:
    return {m["old_device_id"]: m["z2m_device_id"] for m in migrated.values()}
