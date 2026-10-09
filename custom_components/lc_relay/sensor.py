"""Diagnostic sensors of the LC Technology board."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .board import BAUD_RATES
from .const import CONF_UNIT_ID
from .coordinator import LcRelayConfigEntry, LcRelayCoordinator
from .entity import LcRelayEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LcRelayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the diagnostic sensors."""
    coordinator = entry.runtime_data
    async_add_entities([LcRelayBaudRate(coordinator), LcRelayUnitId(coordinator)])


class LcRelayBaudRate(LcRelayEntity, SensorEntity):
    """The RS-485 baud rate programmed into the board."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options = [str(rate) for rate in BAUD_RATES.values()]
    _attr_translation_key = "baud_rate"

    def __init__(self, coordinator: LcRelayCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "baud_rate")

    @property
    def native_value(self) -> str | None:
        """The baud rate, or None when it was never read or is unknown."""
        baud_rate = self.coordinator.data.baud_rate
        return None if baud_rate is None else str(baud_rate)


class LcRelayUnitId(LcRelayEntity, SensorEntity):
    """The Modbus address the board is polled at.

    Read only: the board only takes a new address as a broadcast, which would
    readdress every LC board on the line at once.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "unit_id"

    def __init__(self, coordinator: LcRelayCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "unit_id")
        self._attr_native_value = coordinator.config_entry.data[CONF_UNIT_ID]
