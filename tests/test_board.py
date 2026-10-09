"""Tests for the board protocol, without Home Assistant."""

from __future__ import annotations

from modbus_connection.mock import MockModbusConnection, ReadEvent, WriteEvent
import pytest

from custom_components.lc_relay.board import (
    BAUD_RATE_REGISTER,
    FLASH_REGISTERS,
    BoardState,
    LcRelayBoard,
    baud_rate_from_code,
)


@pytest.fixture
def conn() -> MockModbusConnection:
    return MockModbusConnection()


async def test_read_state_always_reads_full_blocks(conn: MockModbusConnection) -> None:
    unit = conn.for_unit(50)
    unit.coil[0] = [True, False, True, False, False, False, False, True]
    unit.discrete[0] = [False] * 7 + [True]

    state = await LcRelayBoard(unit).async_read_state()

    assert state == BoardState(
        relays=(True, False, True, False, False, False, False, True),
        inputs=(False,) * 7 + (True,),
    )
    # The hardware answers nothing but 8-wide reads at address 0.
    assert unit.read_events == [
        ReadEvent("coil", 0, 8),
        ReadEvent("discrete", 0, 8),
    ]


@pytest.mark.parametrize(
    ("code", "expected"), [(2, 4800), (3, 9600), (4, 19200), (0, None), (7, None)]
)
async def test_baud_rate(
    conn: MockModbusConnection, code: int, expected: int | None
) -> None:
    unit = conn.for_unit(50)
    unit.holding[BAUD_RATE_REGISTER] = code

    assert await LcRelayBoard(unit).async_read_baud_rate() == expected
    assert baud_rate_from_code(code) == expected


@pytest.mark.parametrize(("channel", "on"), [(1, True), (8, False), (3, True)])
async def test_set_relay_writes_single_coil(
    conn: MockModbusConnection, channel: int, on: bool
) -> None:
    unit = conn.for_unit(50)
    writes: list[WriteEvent] = []
    unit.on_write(writes.append)

    await LcRelayBoard(unit).async_set_relay(channel, on)

    assert [
        (w.register_type, w.address, w.values, w.function_code) for w in writes
    ] == [("coil", channel - 1, [on], 5)]


@pytest.mark.parametrize("channel", [0, 9, -1])
async def test_channel_out_of_range(conn: MockModbusConnection, channel: int) -> None:
    board = LcRelayBoard(conn.for_unit(50))
    with pytest.raises(ValueError):
        await board.async_set_relay(channel, True)
    with pytest.raises(ValueError):
        await board.async_pulse(channel, 1)


def test_flash_registers_match_the_manual() -> None:
    assert FLASH_REGISTERS == (0x03, 0x08, 0x0D, 0x12, 0x17, 0x1C, 0x21, 0x26)


async def test_pulse_matches_manual_frame(conn: MockModbusConnection) -> None:
    """Manual: FF 10 00 03 00 02 04 00 04 00 14 -> relay 1 on for 2 s."""
    unit = conn.for_unit(50)
    writes: list[WriteEvent] = []
    unit.on_write(writes.append)

    await LcRelayBoard(unit).async_pulse(1, 2.0)

    assert [
        (w.register_type, w.address, w.values, w.function_code) for w in writes
    ] == [("holding", 0x0003, [0x0004, 0x0014], 16)]


async def test_pulse_rounds_to_tenths(conn: MockModbusConnection) -> None:
    unit = conn.for_unit(50)
    writes: list[WriteEvent] = []
    unit.on_write(writes.append)

    await LcRelayBoard(unit).async_pulse(8, 0.26)

    assert writes[0].address == 0x26
    assert writes[0].values == [4, 3]


@pytest.mark.parametrize("seconds", [0, 0.04, 6553.6, -1])
async def test_pulse_out_of_range(conn: MockModbusConnection, seconds: float) -> None:
    with pytest.raises(ValueError):
        await LcRelayBoard(conn.for_unit(50)).async_pulse(1, seconds)
