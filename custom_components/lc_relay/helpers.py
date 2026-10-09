"""Link parameters from config entry data."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from modbus_connection import ModbusSerialParams, ModbusTcpParams

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE

from .const import (
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    TYPE_SERIAL,
    TYPE_TCP,
)


def modbus_params(data: Mapping[str, Any]) -> ModbusTcpParams | ModbusSerialParams:
    """Build the link the board is reached over.

    Every integration on one serial port has to ask for identical settings:
    the broker shares one connection per port and refuses a mismatch.
    """
    if data.get(CONF_TYPE, TYPE_TCP) == TYPE_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE],
            baudrate=data.get(CONF_BAUDRATE, DEFAULT_BAUDRATE),
            parity=data.get(CONF_PARITY, DEFAULT_PARITY),
            stopbits=data.get(CONF_STOPBITS, DEFAULT_STOPBITS),
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])


def board_unique_id(data: Mapping[str, Any]) -> str:
    """One board per unit id on one link, e.g. ``tcp:192.168.100.16:502:50``."""
    endpoint = ":".join(str(part) for part in modbus_params(data).endpoint)
    return f"{endpoint}:{data[CONF_UNIT_ID]}"
