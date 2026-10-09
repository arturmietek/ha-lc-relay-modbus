# LC Technology Modbus Relay for Home Assistant

Home Assistant integration (domain `lc_relay`) for the Shenzhen LC Technology
Modbus RTU relay boards with optocoupler inputs (1, 2, 4 and 8 channel
variants). The board's RS-485 line can be reached either:

- **over the network**, through a Modbus TCP gateway (e.g. Waveshare
  RS485-to-Ethernet), or
- **over a serial port**, through a USB RS-485 adapter (Modbus RTU).

It does not open its own connection: it asks Home Assistant's Modbus broker
(`homeassistant.components.modbus.async_get_unit`, HA 2026.10+) for a unit, so
it shares one connection with every other integration on the same gateway or
serial port.

## Why

Every variant of the board answers only a read of **exactly 8 coils / 8
discrete inputs** starting at address 0 — a shorter read errors or times out.
This integration always reads the full block but creates entities only for the
number of channels you declare during setup.

## Installation

HACS → ⋮ → *Custom repositories* → add
`https://github.com/arturmietek/ha-lc-relay-modbus` as an *Integration*, install
it and restart Home Assistant. Requires Home Assistant 2026.10 or newer.

## Setup

Settings → Devices & services → Add integration → *LC Technology Modbus Relay*,
then pick how the board is connected:

| Option | Asks for |
|---|---|
| **Network (Modbus TCP gateway)** | gateway host and port |
| **Serial port (Modbus RTU)** | serial port, baud rate (4800/9600/19200), parity, stop bits |
| **Connection already in use** | shown only when Home Assistant already holds a Modbus connection; lists it with the integrations using it and prefills the link |

Each option then asks for the unit ID (factory default 255) and the number of
channels on the board.

All integrations on one serial port share one connection, so they must use the
same baud rate, parity and stop bits. A mismatch is refused with *already in
use by another integration with different link settings* instead of opening a
second connection to the port. For the same reason, a serial port that some
other software keeps open (e.g. another Modbus integration that does not use
the broker) cannot be used at the same time.

The channel count and the poll interval (default 2 s) can be changed later
under *Configure*; lowering the count removes the dropped channels' entities.

## Entities

| Entity | Source |
|---|---|
| `switch` Relay 1..N | coils 0..N-1 (FC01 read, FC05 write) |
| `binary_sensor` Input 1..N | discrete inputs 0..N-1 (FC02), on = high level |
| `sensor` Baud rate (diagnostic) | holding register 1000, re-read hourly |
| `sensor` Modbus address (diagnostic) | the unit ID from the configuration |

Entity names are translated (English, Polish).

## Actions

`lc_relay.pulse` — turns a relay on and lets **the board itself** turn it off
after `duration` seconds (0.1–6553.5 s, 0.1 s resolution; the board's
"flash ON" mode, FC16 to the relay's flash register). The pulse ends on time
even if the connection drops.

```yaml
action: lc_relay.pulse
target:
  entity_id: switch.garage_relays_relay_2
data:
  duration: 2.5
```

## Not supported

The integration does not change the board's address or baud rate. The board
only takes a new address as a broadcast, which would readdress every LC board
on the line at once; use the vendor's commands from the manual with the board
connected on its own.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
```

Tests run the real Home Assistant Modbus broker over
`modbus_connection.mock.MockModbusConnection`, for both the TCP and the serial
path; no hardware needed.
