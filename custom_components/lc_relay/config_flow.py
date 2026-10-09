"""Config flow for the LC Technology relay board."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from modbus_connection import ModbusError
import voluptuous as vol

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.components.modbus.connection import async_get_connection_info
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
    TextSelector,
)

from .board import BAUD_RATES, MAX_CHANNELS, LcRelayBoard
from .const import (
    CONF_BAUDRATE,
    CONF_CHANNELS,
    CONF_PARITY,
    CONF_SCAN_INTERVAL,
    CONF_STOPBITS,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_CHANNELS,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STOPBITS,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    TYPE_SERIAL,
    TYPE_TCP,
)
from .helpers import board_unique_id, modbus_params

_LOGGER = logging.getLogger(__name__)


def _box(minimum: int, maximum: int, unit: str | None = None) -> vol.All:
    """An integer input box with bounds."""
    config = NumberSelectorConfig(
        min=minimum, max=maximum, step=1, mode=NumberSelectorMode.BOX
    )
    if unit is not None:
        config["unit_of_measurement"] = unit
    return vol.All(NumberSelector(config), vol.Coerce(int))


def _choice(options: list[str], key: str | None = None) -> SelectSelector:
    """A dropdown over fixed values."""
    config = SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
    if key is not None:
        config["translation_key"] = key
    return SelectSelector(config)


CHANNELS_SELECTOR = vol.All(
    NumberSelector(
        NumberSelectorConfig(
            min=1, max=MAX_CHANNELS, step=1, mode=NumberSelectorMode.SLIDER
        )
    ),
    vol.Coerce(int),
)

BOARD_FIELDS = {
    vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): _box(1, 255),
    vol.Required(CONF_CHANNELS, default=DEFAULT_CHANNELS): CHANNELS_SELECTOR,
}

STEP_TCP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): _box(1, 65535),
        **BOARD_FIELDS,
    }
)

STEP_SERIAL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE): SerialPortSelector(),
        # Only the rates the board can be set to.
        vol.Required(CONF_BAUDRATE, default=str(DEFAULT_BAUDRATE)): vol.All(
            _choice([str(rate) for rate in BAUD_RATES.values()]), vol.Coerce(int)
        ),
        vol.Required(CONF_PARITY, default=DEFAULT_PARITY): _choice(
            ["N", "E", "O"], CONF_PARITY
        ),
        vol.Required(CONF_STOPBITS, default=str(DEFAULT_STOPBITS)): vol.All(
            _choice(["1", "2"]), vol.Coerce(int)
        ),
        **BOARD_FIELDS,
    }
)


async def async_probe(hass: HomeAssistant, data: Mapping[str, Any]) -> str | None:
    """Read the board once; return an error key, or None if it answered."""
    try:
        async with async_get_temporary_unit(
            hass, modbus_params(data), data[CONF_UNIT_ID]
        ) as unit:
            await LcRelayBoard(unit).async_read_state()
    except ModbusError as err:
        _LOGGER.debug("Probe of %s failed: %s", board_unique_id(data), err)
        return "cannot_connect"
    except HomeAssistantError as err:
        # The broker refuses a link already open with other settings.
        _LOGGER.debug("Probe of %s refused: %s", board_unique_id(data), err)
        return "link_conflict"
    return None


CONF_LINK = "link"
STEP_EXISTING = "existing"


def _open_links(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Links the Modbus broker already holds, as form prefills keyed by endpoint.

    Only the endpoint is public: a serial link's baud rate and framing still
    have to be entered, and the broker refuses them if they differ.
    """
    links: dict[str, dict[str, Any]] = {}
    for info in async_get_connection_info(hass):
        match info.endpoint:
            case ("tcp", host, port):
                links[f"tcp:{host}:{port}"] = {
                    CONF_TYPE: TYPE_TCP,
                    CONF_HOST: host,
                    CONF_PORT: port,
                }
            case ("serial", device):
                links[f"serial:{device}"] = {
                    CONF_TYPE: TYPE_SERIAL,
                    CONF_DEVICE: device,
                }
    return links


def _link_label(hass: HomeAssistant, key: str) -> str:
    """The endpoint, followed by the entries using it."""
    users = sorted(
        entry.title
        for info in async_get_connection_info(hass)
        if ":".join(str(part) for part in info.endpoint) == key
        for entry_id in info.units
        if (entry := hass.config_entries.async_get_entry(entry_id)) is not None
    )
    return f"{key} ({', '.join(users)})" if users else key


class LcRelayConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up one relay board."""

    VERSION = 1

    def __init__(self) -> None:
        """Start without a link picked."""
        self._prefill: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask how the board is reached."""
        options = [TYPE_TCP, TYPE_SERIAL]
        if _open_links(self.hass):
            options.insert(0, STEP_EXISTING)
        return self.async_show_menu(step_id="user", menu_options=options)

    async def async_step_existing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick a link another integration already opened."""
        links = _open_links(self.hass)
        if user_input is not None and (link := links.get(user_input[CONF_LINK])):
            self._prefill = {k: v for k, v in link.items() if k != CONF_TYPE}
            if link[CONF_TYPE] == TYPE_SERIAL:
                return await self.async_step_serial()
            return await self.async_step_tcp()
        return self.async_show_form(
            step_id=STEP_EXISTING,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LINK): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=key, label=_link_label(self.hass, key)
                                )
                                for key in links
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """A board behind a Modbus TCP gateway."""
        return await self._async_step_link(TYPE_TCP, STEP_TCP_SCHEMA, user_input)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """A board on an RS-485 serial port."""
        return await self._async_step_link(TYPE_SERIAL, STEP_SERIAL_SCHEMA, user_input)

    async def _async_step_link(
        self,
        link_type: str,
        schema: vol.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link and the board, then probe it."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: link_type, **user_input}
            await self.async_set_unique_id(board_unique_id(data))
            self._abort_if_unique_id_configured()
            if (error := await async_probe(self.hass, data)) is None:
                return self.async_create_entry(
                    title=f"LC Relay {data[CONF_UNIT_ID]}", data=data
                )
            errors["base"] = error
        return self.async_show_form(
            step_id=link_type,
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or self._prefill
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> LcRelayOptionsFlow:
        """Return the options flow."""
        return LcRelayOptionsFlow()


class LcRelayOptionsFlow(OptionsFlowWithReload):
    """Change the channel count and the poll interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        entry = self.config_entry
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CHANNELS,
                        default=entry.options.get(
                            CONF_CHANNELS, entry.data[CONF_CHANNELS]
                        ),
                    ): CHANNELS_SELECTOR,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): _box(MIN_SCAN_INTERVAL, MAX_SCAN_INTERVAL, "s"),
                }
            ),
        )
