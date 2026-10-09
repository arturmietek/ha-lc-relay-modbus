"""Tests for setup, polling, unload and sharing the gateway."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.components.modbus.connection import DATA_MODBUS_CONNECTIONS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ENTRY_DATA, HOST, PORT, UNIT_ID, ReopenableConnection
from custom_components.lc_relay.const import CONF_CHANNELS, CONF_UNIT_ID, DOMAIN


async def test_entities_only_for_declared_channels(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    entities = er.async_entries_for_config_entry(entity_registry, loaded_entry.entry_id)
    assert sorted(e.entity_id for e in entities) == [
        "binary_sensor.lc_relay_50_input_1",
        "binary_sensor.lc_relay_50_input_2",
        "sensor.lc_relay_50_baud_rate",
        "sensor.lc_relay_50_modbus_address",
        "switch.lc_relay_50_relay_1",
        "switch.lc_relay_50_relay_2",
    ]
    assert hass.states.get("switch.lc_relay_50_relay_1").state == STATE_ON
    assert hass.states.get("switch.lc_relay_50_relay_2").state == STATE_OFF
    assert hass.states.get("binary_sensor.lc_relay_50_input_1").state == STATE_OFF
    assert hass.states.get("binary_sensor.lc_relay_50_input_2").state == STATE_ON
    assert hass.states.get("sensor.lc_relay_50_baud_rate").state == "9600"
    assert hass.states.get("sensor.lc_relay_50_modbus_address").state == "50"


async def test_poll_picks_up_changes_with_full_reads(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    unit.coil[0] = [False, True] + [False] * 6
    unit.discrete[0] = [True] * 8
    unit.read_events.clear()

    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("switch.lc_relay_50_relay_1").state == STATE_OFF
    assert hass.states.get("switch.lc_relay_50_relay_2").state == STATE_ON
    assert hass.states.get("binary_sensor.lc_relay_50_input_1").state == STATE_ON
    # Coils and inputs every poll, 8 wide; the baud rate is not due yet.
    assert [(e.register_type, e.address, e.count) for e in unit.read_events] == [
        ("coil", 0, 8),
        ("discrete", 0, 8),
    ]


async def test_baud_rate_reread_hourly(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    unit.holding[0x03E8] = 4
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.lc_relay_50_baud_rate").state == "19200"


async def test_baud_rate_failure_does_not_break_relays(
    hass: HomeAssistant, entry: MockConfigEntry, unit: MockModbusUnit
) -> None:
    unit.fail_read(0x03E8, ModbusTimeoutError("no answer"))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("switch.lc_relay_50_relay_1").state == STATE_ON
    assert hass.states.get("sensor.lc_relay_50_baud_rate").state == "unknown"


async def test_setup_retries_when_board_silent(
    hass: HomeAssistant, entry: MockConfigEntry, unit: MockModbusUnit
) -> None:
    unit.fail_requests(ModbusTimeoutError("no answer"))
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_entities_unavailable_while_board_silent(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    unit: MockModbusUnit,
    freezer: FrozenDateTimeFactory,
) -> None:
    unit.fail_requests(ModbusTimeoutError("no answer"))
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("switch.lc_relay_50_relay_1").state == STATE_UNAVAILABLE

    unit.fail_requests(None)
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("switch.lc_relay_50_relay_1").state == STATE_ON


async def test_lowering_channels_removes_entities(
    hass: HomeAssistant,
    loaded_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    hass.config_entries.async_update_entry(loaded_entry, options={CONF_CHANNELS: 1})
    await hass.config_entries.async_reload(loaded_entry.entry_id)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(entity_registry, loaded_entry.entry_id)
    assert sorted(e.entity_id for e in entities) == [
        "binary_sensor.lc_relay_50_input_1",
        "sensor.lc_relay_50_baud_rate",
        "sensor.lc_relay_50_modbus_address",
        "switch.lc_relay_50_relay_1",
    ]


async def test_unload_releases_the_connection(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, connection: ReopenableConnection
) -> None:
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    assert loaded_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data[DATA_MODBUS_CONNECTIONS]
    assert connection.closes == 1


async def test_two_boards_share_one_gateway_connection(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, connection: ReopenableConnection
) -> None:
    """The point of the broker: independent entries, one link."""
    other_unit = connection.for_unit(51)
    other_unit.coil[0] = [False] * 8
    other = MockConfigEntry(
        domain=DOMAIN,
        title="LC Relay 51",
        data={**ENTRY_DATA, CONF_UNIT_ID: 51},
        unique_id=f"tcp:{HOST}:{PORT}:51",
    )
    other.add_to_hass(hass)
    assert await hass.config_entries.async_setup(other.entry_id)
    await hass.async_block_till_done()

    (shared,) = hass.data[DATA_MODBUS_CONNECTIONS].values()
    assert shared.units == {loaded_entry.entry_id: {UNIT_ID}, other.entry_id: {51}}
    assert hass.states.get("switch.lc_relay_51_relay_1").state == STATE_OFF

    # Unloading one board leaves the link up for the other.
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    assert connection.closes == 0
    assert await hass.config_entries.async_unload(other.entry_id)
    assert connection.closes == 1
