"""Tests for the config and options flows."""

from __future__ import annotations

from unittest.mock import patch

from modbus_connection import ModbusSerialParams, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.modbus.connection import (
    DATA_MODBUS_CONNECTIONS,
    _async_acquire,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from .conftest import ENTRY_DATA, HOST, PORT, UNIT_ID
from custom_components.lc_relay.const import (
    CONF_BAUDRATE,
    CONF_CHANNELS,
    CONF_PARITY,
    CONF_SCAN_INTERVAL,
    CONF_STOPBITS,
    CONF_UNIT_ID,
    DOMAIN,
)

TCP_INPUT = {CONF_HOST: HOST, CONF_PORT: PORT, CONF_UNIT_ID: UNIT_ID, CONF_CHANNELS: 1}

SERIAL_PORT = "/dev/serial/by-id/usb-1a86_USB_Single_Serial-if00"
SERIAL_INPUT = {
    CONF_DEVICE: SERIAL_PORT,
    CONF_BAUDRATE: "9600",
    CONF_PARITY: "none",
    CONF_STOPBITS: "1",
    CONF_UNIT_ID: UNIT_ID,
    CONF_CHANNELS: 2,
}


async def _start(hass: HomeAssistant, link: str) -> dict:
    """Open the flow and pick the link type from the menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert link in result["menu_options"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": link}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == link
    return result


async def test_menu_without_open_links(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["menu_options"] == ["tcp", "serial"]


async def test_tcp_flow_creates_entry(
    hass: HomeAssistant, unit: MockModbusUnit
) -> None:
    result = await _start(hass, "tcp")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TCP_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LC Relay 50"
    assert result["data"] == {CONF_TYPE: "tcp", **TCP_INPUT}
    assert result["result"].unique_id == f"tcp:{HOST}:{PORT}:{UNIT_ID}"
    # Probe and setup read the full 8-wide blocks, even for a 1-channel board.
    bit_reads = {
        (e.register_type, e.address, e.count)
        for e in unit.read_events
        if e.register_type in ("coil", "discrete")
    }
    assert bit_reads == {("coil", 0, 8), ("discrete", 0, 8)}


async def test_serial_flow_creates_entry(
    hass: HomeAssistant, unit: MockModbusUnit
) -> None:
    result = await _start(hass, "serial")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SERIAL_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_TYPE: "serial",
        **SERIAL_INPUT,
        CONF_BAUDRATE: 9600,
        CONF_STOPBITS: 1,
    }
    assert result["result"].unique_id == f"serial:{SERIAL_PORT}:{UNIT_ID}"
    (shared,) = hass.data[DATA_MODBUS_CONNECTIONS].values()
    assert shared.params == ModbusSerialParams(
        device=SERIAL_PORT, baudrate=9600, parity="N", stopbits=1
    )


async def test_serial_settings_must_match_the_port_holder(
    hass: HomeAssistant, unit: MockModbusUnit
) -> None:
    """Another integration holds the port at 19200: the real broker refuses."""
    _async_acquire(
        hass, ModbusSerialParams(device=SERIAL_PORT, baudrate=19200), "other", 1
    )
    result = await _start(hass, "serial")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SERIAL_INPUT
    )
    assert result["errors"] == {"base": "link_conflict"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**SERIAL_INPUT, CONF_BAUDRATE: "19200"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("field", "value"), [(CONF_BAUDRATE, "115200"), (CONF_PARITY, "N")]
)
async def test_serial_rejects_unsupported_settings(
    hass: HomeAssistant, unit: MockModbusUnit, field: str, value: str
) -> None:
    result = await _start(hass, "serial")
    with pytest.raises(Exception):  # noqa: B017 - schema rejects it
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {**SERIAL_INPUT, field: value}
        )


async def test_probe_releases_the_connection(
    hass: HomeAssistant, unit: MockModbusUnit
) -> None:
    result = await _start(hass, "tcp")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TCP_INPUT
    )

    # The flow's own hold is gone; only the new entry holds the link.
    (shared,) = hass.data[DATA_MODBUS_CONNECTIONS].values()
    assert shared.transient == 0
    assert shared.units == {result["result"].entry_id: {UNIT_ID}}


async def test_cannot_connect_then_recovers(
    hass: HomeAssistant, unit: MockModbusUnit
) -> None:
    unit.fail_requests(ModbusTimeoutError("no answer"))
    result = await _start(hass, "tcp")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TCP_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    unit.fail_requests(None)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], TCP_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_link_conflict_from_broker(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.lc_relay.config_flow.async_get_temporary_unit",
        side_effect=HomeAssistantError("different link settings"),
    ):
        result = await _start(hass, "tcp")
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], TCP_INPUT
        )
    assert result["errors"] == {"base": "link_conflict"}


async def test_already_configured(
    hass: HomeAssistant, entry: MockConfigEntry, unit: MockModbusUnit
) -> None:
    result = await _start(hass, "tcp")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**TCP_INPUT, CONF_HOST: HOST.upper()}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_same_gateway_other_unit_is_a_new_board(
    hass: HomeAssistant, entry: MockConfigEntry, connection: MockModbusConnection
) -> None:
    connection.for_unit(51)
    result = await _start(hass, "tcp")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**TCP_INPUT, CONF_UNIT_ID: 51}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("channels", [0, 9])
async def test_channels_out_of_range_rejected(
    hass: HomeAssistant, unit: MockModbusUnit, channels: int
) -> None:
    result = await _start(hass, "tcp")
    with pytest.raises(Exception):  # noqa: B017 - schema rejects it
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {**TCP_INPUT, CONF_CHANNELS: channels}
        )


async def test_options_flow(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CHANNELS: 8, CONF_SCAN_INTERVAL: 5}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert loaded_entry.options == {CONF_CHANNELS: 8, CONF_SCAN_INTERVAL: 5}
    assert loaded_entry.data == ENTRY_DATA
    assert loaded_entry.runtime_data.channels == 8
    assert hass.states.get("switch.lc_relay_50_relay_8") is not None


async def test_existing_link_prefills_tcp(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, connection: MockModbusConnection
) -> None:
    """A second board on the gateway the first one already holds."""
    connection.for_unit(51)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["menu_options"] == ["existing", "tcp", "serial"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "existing"}
    )
    options = result["data_schema"].schema["link"].config["options"]
    assert options == [
        {"value": f"tcp:{HOST}:{PORT}", "label": f"tcp:{HOST}:{PORT} (LC Relay 50)"}
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"link": f"tcp:{HOST}:{PORT}"}
    )
    assert result["step_id"] == "tcp"
    suggested = {
        key.schema: key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggested == {CONF_HOST: HOST, CONF_PORT: PORT}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**TCP_INPUT, CONF_UNIT_ID: 51}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    (shared,) = hass.data[DATA_MODBUS_CONNECTIONS].values()
    assert sorted(unit_id for held in shared.units.values() for unit_id in held) == [
        UNIT_ID,
        51,
    ]


async def test_existing_link_prefills_serial_port(
    hass: HomeAssistant, unit: MockModbusUnit
) -> None:
    _async_acquire(hass, ModbusSerialParams(device=SERIAL_PORT), "other", 1)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "existing"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"link": f"serial:{SERIAL_PORT}"}
    )
    assert result["step_id"] == "serial"
    suggested = {
        key.schema: key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggested == {CONF_DEVICE: SERIAL_PORT}
