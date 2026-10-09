"""Protocol for the Shenzhen LC Technology Modbus relay + input board.

Pure Python on top of a `modbus_connection.ModbusUnit`; no Home Assistant
imports, so it can be tested and reused on its own.

The board ships in 1, 2, 4 and 8 channel variants, but every variant answers
only a read of exactly 8 coils / 8 discrete inputs starting at address 0. A
shorter read times out or errors, so the full block is always read and the
caller decides how many channels physically exist.
"""

from __future__ import annotations

from dataclasses import dataclass

from modbus_connection import ModbusUnit

MAX_CHANNELS = 8
"""Width of the coil and discrete input blocks on every variant."""

BLOCK_START = 0

BAUD_RATE_REGISTER = 0x03E8
"""Holding register with the RS-485 baud rate code (read only here)."""

BAUD_RATES: dict[int, int] = {2: 4800, 3: 9600, 4: 19200}
"""Baud rate code to bits per second."""

FLASH_REGISTERS: tuple[int, ...] = tuple(0x0003 + 5 * i for i in range(MAX_CHANNELS))
"""Per-relay register pair for the timed ("flash") modes, relay 1 first."""

FLASH_ON = 0x0004
"""Turn the relay on now and off again after the delay."""

FLASH_STEP = 0.1
"""Delay unit of the flash modes, in seconds."""

MAX_FLASH_DELAY = 0xFFFF * FLASH_STEP


@dataclass(frozen=True, slots=True)
class BoardState:
    """One snapshot of the board, always all 8 channels wide."""

    relays: tuple[bool, ...]
    inputs: tuple[bool, ...]


def baud_rate_from_code(code: int) -> int | None:
    """Return the baud rate a register code stands for, or None if unknown."""
    return BAUD_RATES.get(code)


def _check_channel(channel: int) -> None:
    if not 1 <= channel <= MAX_CHANNELS:
        raise ValueError(f"channel must be 1..{MAX_CHANNELS}, got {channel}")


class LcRelayBoard:
    """One relay board, addressed through a Modbus unit."""

    def __init__(self, unit: ModbusUnit) -> None:
        """Wrap the unit the board answers on."""
        self._unit = unit

    async def async_read_state(self) -> BoardState:
        """Read all relays and inputs (two requests, 8 bits each)."""
        relays = await self._unit.read_coils(BLOCK_START, MAX_CHANNELS)
        inputs = await self._unit.read_discrete_inputs(BLOCK_START, MAX_CHANNELS)
        return BoardState(
            relays=tuple(relays[:MAX_CHANNELS]),
            inputs=tuple(inputs[:MAX_CHANNELS]),
        )

    async def async_read_baud_rate(self) -> int | None:
        """Return the configured RS-485 baud rate, or None for an unknown code."""
        (code,) = await self._unit.read_holding_registers(BAUD_RATE_REGISTER, 1)
        return baud_rate_from_code(code)

    async def async_set_relay(self, channel: int, on: bool) -> None:
        """Switch one relay (1-based channel)."""
        _check_channel(channel)
        await self._unit.write_coil(BLOCK_START + channel - 1, on)

    async def async_pulse(self, channel: int, seconds: float) -> None:
        """Turn a relay on and let the board turn it off after ``seconds``.

        The board times the pulse itself, so it ends on time even if the link
        drops in between. Resolution is 0.1 s.
        """
        _check_channel(channel)
        steps = round(seconds / FLASH_STEP)
        if not 1 <= steps <= 0xFFFF:
            raise ValueError(
                f"pulse must be {FLASH_STEP}..{MAX_FLASH_DELAY:.1f} s, got {seconds}"
            )
        await self._unit.write_registers(
            FLASH_REGISTERS[channel - 1], [FLASH_ON, steps]
        )
