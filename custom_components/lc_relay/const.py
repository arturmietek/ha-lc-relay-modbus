"""Constants for the LC Technology relay board integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "lc_relay"

MANUFACTURER: Final = "Shenzhen LC Technology"
MODEL: Final = "Modbus RTU relay board"

TYPE_TCP: Final = "tcp"
TYPE_SERIAL: Final = "serial"

CONF_BAUDRATE: Final = "baudrate"
CONF_PARITY: Final = "parity"
CONF_STOPBITS: Final = "stopbits"
CONF_UNIT_ID: Final = "unit_id"
CONF_CHANNELS: Final = "channels"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_PORT: Final = 502
DEFAULT_BAUDRATE: Final = 9600
"""Factory baud rate of the board."""
DEFAULT_PARITY: Final = "none"
PARITIES: Final = {"none": "N", "even": "E", "odd": "O"}
"""Parity option to the letter modbus-connection takes."""
DEFAULT_STOPBITS: Final = 1
DEFAULT_UNIT_ID: Final = 255
"""Factory address of the board."""
DEFAULT_CHANNELS: Final = 8
DEFAULT_SCAN_INTERVAL: Final = 2
"""Seconds between polls of relays and inputs."""

MIN_SCAN_INTERVAL: Final = 1
MAX_SCAN_INTERVAL: Final = 300

BAUD_RATE_INTERVAL: Final = timedelta(hours=1)
"""The baud rate only changes when someone reprograms the board."""

SERVICE_PULSE: Final = "pulse"
ATTR_DURATION: Final = "duration"
