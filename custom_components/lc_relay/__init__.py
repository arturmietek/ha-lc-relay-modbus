"""Shenzhen LC Technology Modbus relay boards."""

from __future__ import annotations

from datetime import timedelta
import re

import voluptuous as vol

from homeassistant.components.modbus import async_get_unit
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.typing import ConfigType

from .board import FLASH_STEP, MAX_FLASH_DELAY, LcRelayBoard
from .const import (
    ATTR_DURATION,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SERVICE_PULSE,
)
from .coordinator import LcRelayConfigEntry, LcRelayCoordinator
from .helpers import modbus_params

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_CHANNEL_KEY = re.compile(r"_(?:relay|input)_(\d+)$")


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the pulse service."""
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_PULSE,
        entity_domain=SWITCH_DOMAIN,
        schema={
            vol.Required(ATTR_DURATION): vol.All(
                vol.Coerce(float), vol.Range(min=FLASH_STEP, max=MAX_FLASH_DELAY)
            )
        },
        func="async_pulse",
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LcRelayConfigEntry) -> bool:
    """Set up a relay board from a config entry."""
    unit = async_get_unit(
        hass, entry, modbus_params(entry.data), entry.data[CONF_UNIT_ID]
    )
    interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = LcRelayCoordinator(
        hass, entry, LcRelayBoard(unit), timedelta(seconds=interval)
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _async_remove_surplus_channels(hass, entry, coordinator.channels)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


@callback
def _async_remove_surplus_channels(
    hass: HomeAssistant, entry: LcRelayConfigEntry, channels: int
) -> None:
    """Drop entities of channels beyond the count, after it was lowered."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (match := _CHANNEL_KEY.search(entity.unique_id)) and int(
            match.group(1)
        ) > channels:
            registry.async_remove(entity.entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: LcRelayConfigEntry) -> bool:
    """Unload a config entry; the shared connection is released by the broker."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
