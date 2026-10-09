"""Base entity for the LC Technology relay board."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import LcRelayCoordinator


class LcRelayEntity(CoordinatorEntity[LcRelayCoordinator]):
    """An entity of one relay board."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: LcRelayCoordinator, key: str) -> None:
        """Bind the entity to the board's device."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        assert entry.unique_id is not None
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            model_id=f"{coordinator.channels}-channel",
            name=entry.title,
            # Explicit: clears the unit id 0.1.0 stored here; the board has none.
            serial_number=None,
        )


class LcRelayChannelEntity(LcRelayEntity):
    """An entity tied to one channel (1-based)."""

    def __init__(
        self, coordinator: LcRelayCoordinator, kind: str, channel: int
    ) -> None:
        """Name the entity after its channel."""
        super().__init__(coordinator, f"{kind}_{channel}")
        self.channel = channel
        self._attr_translation_key = kind
        self._attr_translation_placeholders = {"channel": str(channel)}
