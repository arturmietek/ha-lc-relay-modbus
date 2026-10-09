# LC Technology Modbus Relay for Home Assistant

Home Assistant integration (domain `lc_relay`) for the Shenzhen LC Technology
Modbus RTU relay boards with optocoupler inputs (1, 2, 4 and 8 channel
variants), reached through a Modbus TCP gateway.

It does not open its own socket: it asks Home Assistant's Modbus broker
(`homeassistant.components.modbus.async_get_unit`, HA 2026.10+) for a unit, so
it shares one connection with every other integration talking to the same
gateway.

## Why

Every variant of the board answers only a read of **exactly 8 coils / 8
discrete inputs** starting at address 0 — a shorter read errors or times out.
This integration always reads the full block but creates entities only for the
number of channels you declare during setup.

## Entities

| Entity | Source |
|---|---|
| `switch` Relay 1..N | coils 0..N-1 (FC01 read, FC05 write) |
| `binary_sensor` Input 1..N | discrete inputs 0..N-1 (FC02), on = high level |
| `sensor` Baud rate (diagnostic) | holding register 1000, re-read hourly |

## Services

`lc_relay.pulse` — turns a relay on and lets **the board itself** turn it off
after `duration` seconds (0.1 s resolution, "flash ON" mode, FC16 to the
relay's flash register). The pulse ends on time even if the link drops.

## Setup

Settings → Devices & services → Add integration → *LC Technology Modbus Relay*:
gateway host/port, unit ID (factory default 255) and channel count. The
channel count and poll interval (default 2 s) can be changed later under
*Configure*; lowering the count removes the dropped channels' entities.

Board address/baud rate are not changed by this integration; use the
vendor's commands from the manual for that.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
```

Tests run the real Home Assistant Modbus broker over
`modbus_connection.mock.MockModbusConnection`; no hardware needed.
