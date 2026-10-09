"""Fixtures: the real HA Modbus broker over an in-memory connection."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant

from custom_components.lc_relay.const import (
    CONF_CHANNELS,
    CONF_UNIT_ID,
    DOMAIN,
)

HOST = "192.168.100.16"
PORT = 502
UNIT_ID = 50

ENTRY_DATA = {
    CONF_TYPE: "tcp",
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_UNIT_ID: UNIT_ID,
    CONF_CHANNELS: 2,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


class ReopenableConnection(MockModbusConnection):
    """One in-memory link that survives the broker closing it.

    The broker builds a fresh connection after closing the last one; here the
    same object stands in for each, so the units' stores carry over.
    """

    def __init__(self) -> None:
        super().__init__()
        self.closes = 0

    async def close(self) -> None:
        self.closes += 1
        self.simulate_connection_lost()


@pytest.fixture
def connection() -> Generator[ReopenableConnection]:
    """Every link the broker opens is this one in-memory connection."""
    conn = ReopenableConnection()
    with patch(
        "homeassistant.components.modbus.connection.ModbusConnection",
        side_effect=lambda params: conn,
    ):
        yield conn


@pytest.fixture
def unit(connection: MockModbusConnection) -> MockModbusUnit:
    """The board at UNIT_ID: relay 1 on, input 2 high, 9600 bps."""
    board = connection.for_unit(UNIT_ID)
    board.coil[0] = [True] + [False] * 7
    board.discrete[0] = [False, True] + [False] * 6
    board.holding[0x03E8] = 3
    return board


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """A two-channel board."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="LC Relay 50",
        data=ENTRY_DATA,
        unique_id=f"tcp:{HOST}:{PORT}:{UNIT_ID}",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
async def loaded_entry(
    hass: HomeAssistant, entry: MockConfigEntry, unit: MockModbusUnit
) -> MockConfigEntry:
    """The two-channel board, set up."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
