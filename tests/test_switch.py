"""Tests for the relay switches and the pulse service."""

from __future__ import annotations

from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit, WriteEvent
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.lc_relay.const import DOMAIN

RELAY_2 = "switch.lc_relay_50_relay_2"


@pytest.fixture
def writes(unit: MockModbusUnit) -> list[tuple]:
    events: list[tuple] = []

    def record(event: WriteEvent) -> None:
        events.append((event.register_type, event.address, event.values))

    unit.on_write(record)
    return events


async def test_turn_on_and_off(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, writes: list[tuple]
) -> None:
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: RELAY_2}, blocking=True
    )
    assert hass.states.get(RELAY_2).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: RELAY_2}, blocking=True
    )
    assert hass.states.get(RELAY_2).state == STATE_OFF
    assert writes == [("coil", 1, [True]), ("coil", 1, [False])]


async def test_write_failure_raises_and_keeps_state(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, unit: MockModbusUnit
) -> None:
    unit.fail_write(1, ModbusTimeoutError("no answer"), register_type="coil")
    with pytest.raises(HomeAssistantError, match="relay_2"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: RELAY_2}, blocking=True
        )
    assert hass.states.get(RELAY_2).state == STATE_OFF


async def test_pulse(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, writes: list[tuple]
) -> None:
    await hass.services.async_call(
        DOMAIN, "pulse", {ATTR_ENTITY_ID: RELAY_2, "duration": 1.5}, blocking=True
    )
    assert writes == [("holding", 0x08, [4, 15])]
    assert hass.states.get(RELAY_2).state == STATE_ON


@pytest.mark.parametrize("duration", [0, 7000])
async def test_pulse_duration_validated(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, duration: float
) -> None:
    with pytest.raises(Exception):  # noqa: B017 - schema rejects it
        await hass.services.async_call(
            DOMAIN,
            "pulse",
            {ATTR_ENTITY_ID: RELAY_2, "duration": duration},
            blocking=True,
        )
