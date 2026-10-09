"""Polling for the LC Technology relay board."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import logging

from modbus_connection import ModbusError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .board import BoardState, LcRelayBoard
from .const import BAUD_RATE_INTERVAL, CONF_CHANNELS, DOMAIN

_LOGGER = logging.getLogger(__name__)

type LcRelayConfigEntry = ConfigEntry[LcRelayCoordinator]


@dataclass(frozen=True, slots=True)
class LcRelayData:
    """What the entities read from."""

    state: BoardState
    baud_rate: int | None


class LcRelayCoordinator(DataUpdateCoordinator[LcRelayData]):
    """Poll relays and inputs; the baud rate only every hour."""

    config_entry: LcRelayConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LcRelayConfigEntry,
        board: LcRelayBoard,
        interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=interval,
        )
        self.board = board
        self._baud_rate_read_at: datetime | None = None

    @property
    def channels(self) -> int:
        """How many channels the user said the board has."""
        entry = self.config_entry
        return entry.options.get(CONF_CHANNELS, entry.data[CONF_CHANNELS])

    async def _async_update_data(self) -> LcRelayData:
        try:
            state = await self.board.async_read_state()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return LcRelayData(state, await self._async_baud_rate())

    async def _async_baud_rate(self) -> int | None:
        """Re-read the baud rate when it is due, else keep the last value."""
        previous = self.data.baud_rate if self.data else None
        now = dt_util.utcnow()
        if (
            self._baud_rate_read_at is not None
            and now - self._baud_rate_read_at < BAUD_RATE_INTERVAL
        ):
            return previous
        try:
            baud_rate = await self.board.async_read_baud_rate()
        except ModbusError as err:
            # Diagnostic only: never fail the relay poll over it.
            _LOGGER.debug("%s: could not read the baud rate: %s", self.name, err)
            return previous
        self._baud_rate_read_at = now
        return baud_rate

    def async_set_relay_state(self, channel: int, on: bool) -> None:
        """Record a relay write the board acknowledged, ahead of the next poll."""
        relays = list(self.data.state.relays)
        relays[channel - 1] = on
        self.async_set_updated_data(
            replace(self.data, state=replace(self.data.state, relays=tuple(relays)))
        )
