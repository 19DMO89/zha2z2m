"""Sidebar panel of the migration helper."""

from __future__ import annotations

import os

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_SHOW_IN_SIDEBAR,
    DOMAIN,
    PANEL_ELEMENT,
    PANEL_ICON,
    PANEL_STATIC_URL,
    PANEL_TITLE,
    PANEL_URL_PATH,
    VERSION,
)

_DATA_STATIC = f"{DOMAIN}_static_registered"
_DATA_PANEL = f"{DOMAIN}_panel_registered"


async def async_update_panel(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Show or hide the sidebar panel according to the options."""
    if entry.options.get(CONF_SHOW_IN_SIDEBAR, True):
        await async_register_panel(hass)
    else:
        async_remove_panel(hass)


async def async_register_panel(hass: HomeAssistant) -> None:
    if hass.data.get(_DATA_PANEL):
        return
    if not hass.data.get(_DATA_STATIC):
        # Static paths cannot be unregistered, so only register them once.
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    PANEL_STATIC_URL,
                    os.path.join(os.path.dirname(__file__), "frontend"),
                    cache_headers=False,
                )
            ]
        )
        hass.data[_DATA_STATIC] = True
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_ELEMENT,
        module_url=f"{PANEL_STATIC_URL}/zha2z2m-panel.js?v={VERSION}",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        require_admin=True,
        config={},
    )
    hass.data[_DATA_PANEL] = True


def async_remove_panel(hass: HomeAssistant) -> None:
    if hass.data.pop(_DATA_PANEL, False):
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
