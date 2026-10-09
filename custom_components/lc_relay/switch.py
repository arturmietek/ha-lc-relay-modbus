"""Relays of the LC Technology board."""

from __future__ import annotations

from typing import Any

from modbus_connection import ModbusError

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LcRelayConfigEntry, LcRelayCoordinator
from .entity import LcRelayChannelEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LcRelayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add one switch per declared channel."""
    coordinator = entry.runtime_data
    async_add_entities(
        LcRelaySwitch(coordinator, channel)
        for channel in range(1, coordinator.channels + 1)
    )


class LcRelaySwitch(LcRelayChannelEntity, SwitchEntity):
    """One relay."""

    def __init__(self, coordinator: LcRelayCoordinator, channel: int) -> None:
        """Initialize the relay."""
        super().__init__(coordinator, "relay", channel)

    @property
    def is_on(self) -> bool:
        """Whether the relay is energized."""
        return self.coordinator.data.state.relays[self.channel - 1]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Energize the relay."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Release the relay."""
        await self._async_set(False)

    async def _async_set(self, on: bool) -> None:
        try:
            await self.coordinator.board.async_set_relay(self.channel, on)
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"entity": self.entity_id, "error": str(err)},
            ) from err
        self.coordinator.async_set_relay_state(self.channel, on)

    async def async_pulse(self, duration: float) -> None:
        """Turn on for ``duration`` seconds, timed by the board itself."""
        try:
            await self.coordinator.board.async_pulse(self.channel, duration)
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"entity": self.entity_id, "error": str(err)},
            ) from err
        self.coordinator.async_set_relay_state(self.channel, True)
