"""Optocoupler inputs of the LC Technology board."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LcRelayConfigEntry, LcRelayCoordinator
from .entity import LcRelayChannelEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LcRelayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add one binary sensor per declared channel."""
    coordinator = entry.runtime_data
    async_add_entities(
        LcRelayInput(coordinator, channel)
        for channel in range(1, coordinator.channels + 1)
    )


class LcRelayInput(LcRelayChannelEntity, BinarySensorEntity):
    """One optocoupler input; on means a high level."""

    def __init__(self, coordinator: LcRelayCoordinator, channel: int) -> None:
        """Initialize the input."""
        super().__init__(coordinator, "input", channel)

    @property
    def is_on(self) -> bool:
        """Whether the input sees a high level."""
        return self.coordinator.data.state.inputs[self.channel - 1]
