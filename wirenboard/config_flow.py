"""Config flow for Wiren Board integration."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow

from .const import (
    CONF_CLIENT_ID,
    CONF_DISCOVERY_TOPIC,
    CONF_HOST,
    CONF_KEEPALIVE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TOPIC_PREFIX,
    CONF_USE_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DEFAULT_CLIENT_ID,
    DEFAULT_DISCOVERY_TOPIC,
    DEFAULT_KEEPALIVE,
    DEFAULT_PORT,
    DEFAULT_TOPIC_PREFIX,
    DEFAULT_USE_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .mqtt_client import WirenBoardMqttClient


class WirenBoardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wiren Board."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._client = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Test MQTT connection
                if not await self._test_mqtt_connection(user_input):
                    errors["base"] = "cannot_connect"
                else:
                    # Create unique ID based on host and client_id
                    unique_id = f"{user_input[CONF_HOST]}_{user_input.get(CONF_CLIENT_ID, DEFAULT_CLIENT_ID)}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"Wiren Board - {user_input[CONF_HOST]}", data=user_input
                    )
            except AbortFlow:
                raise
            except Exception as ex:
                errors["base"] = "unknown"

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=user_input.get(CONF_HOST, "localhost")
                    if user_input
                    else "localhost",
                ): str,
                vol.Required(
                    CONF_PORT,
                    default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    if user_input
                    else DEFAULT_PORT,
                ): int,
                # vol.Optional(
                #     CONF_USERNAME,
                #     default=user_input.get(CONF_USERNAME, "") if user_input else "",
                # ): str,
                # vol.Optional(
                #     CONF_PASSWORD,
                #     default=user_input.get(CONF_PASSWORD, "") if user_input else "",
                # ): str,
                # vol.Required(
                #     CONF_CLIENT_ID,
                #     default=user_input.get(CONF_CLIENT_ID, DEFAULT_CLIENT_ID)
                #     if user_input
                #     else DEFAULT_CLIENT_ID,
                # ): str,
                # vol.Required(
                #     CONF_TOPIC_PREFIX,
                #     default=user_input.get(CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX)
                #     if user_input
                #     else DEFAULT_TOPIC_PREFIX,
                # ): str,
                vol.Required(
                    CONF_DISCOVERY_TOPIC,
                    default=user_input.get(
                        CONF_DISCOVERY_TOPIC, DEFAULT_DISCOVERY_TOPIC
                    )
                    if user_input
                    else DEFAULT_DISCOVERY_TOPIC,
                ): str,
                # vol.Required(
                #     CONF_USE_SSL,
                #     default=user_input.get(CONF_USE_SSL, DEFAULT_USE_SSL)
                #     if user_input
                #     else DEFAULT_USE_SSL,
                # ): bool,
                # vol.Required(
                #     CONF_VERIFY_SSL,
                #     default=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
                #     if user_input
                #     else DEFAULT_VERIFY_SSL,
                # ): bool,
                # vol.Required(
                #     CONF_KEEPALIVE,
                #     default=user_input.get(CONF_KEEPALIVE, DEFAULT_KEEPALIVE)
                #     if user_input
                #     else DEFAULT_KEEPALIVE,
                # ): int,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def _test_mqtt_connection(self, config):
        """Test MQTT connection with provided configuration."""
        try:
            self._client = WirenBoardMqttClient(
                hass=self.hass,
                host=config[CONF_HOST],
                port=config[CONF_PORT],
                username=config.get(CONF_USERNAME),
                password=config.get(CONF_PASSWORD),
                client_id=config.get(CONF_CLIENT_ID),
                use_ssl=config.get(CONF_USE_SSL),
                verify_ssl=config.get(CONF_VERIFY_SSL),
                keepalive=config.get(CONF_KEEPALIVE),
            )

            # Test connection
            connected = await self._client.test_connection()
            if connected:
                await self._client.disconnect()
            return connected

        except Exception as ex:
            if self._client:
                await self._client.disconnect()
            return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return WirenBoardOptionsFlow(config_entry)


class WirenBoardOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Wiren Board."""

    def __init__(self, config_entry):
        self.config_entry = config_entry
        self._client = None

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            try:
                # Test MQTT connection if any connection parameters changed
                connection_changed = any(
                    user_input.get(key) != self.config_entry.data.get(key)
                    for key in [
                        CONF_HOST,
                        CONF_PORT,
                        CONF_USERNAME,
                        CONF_PASSWORD,
                        CONF_USE_SSL,
                        CONF_VERIFY_SSL,
                        CONF_KEEPALIVE,
                    ]
                )

                if connection_changed:
                    if not await self._test_mqtt_connection(user_input):
                        errors["base"] = "cannot_connect"
                    else:
                        self.hass.config_entries.async_update_entry(
                            self.config_entry,
                            data={**self.config_entry.data, **user_input},
                        )
                        return self.async_create_entry(title="", data={})
                else:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data={**self.config_entry.data, **user_input}
                    )
                    return self.async_create_entry(title="", data={})

            except Exception as ex:
                errors["base"] = "unknown"

        data = self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=data.get(CONF_HOST, "localhost")
                    ): str,
                    vol.Required(
                        CONF_PORT, default=data.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    vol.Optional(
                        CONF_USERNAME, default=data.get(CONF_USERNAME, "")
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD, default=data.get(CONF_PASSWORD, "")
                    ): str,
                    vol.Required(
                        CONF_CLIENT_ID,
                        default=data.get(CONF_CLIENT_ID, DEFAULT_CLIENT_ID),
                    ): str,
                    vol.Required(
                        CONF_TOPIC_PREFIX,
                        default=data.get(CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX),
                    ): str,
                    vol.Required(
                        CONF_DISCOVERY_TOPIC,
                        default=data.get(CONF_DISCOVERY_TOPIC, DEFAULT_DISCOVERY_TOPIC),
                    ): str,
                    vol.Required(
                        CONF_USE_SSL, default=data.get(CONF_USE_SSL, DEFAULT_USE_SSL)
                    ): bool,
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                    ): bool,
                    vol.Required(
                        CONF_KEEPALIVE,
                        default=data.get(CONF_KEEPALIVE, DEFAULT_KEEPALIVE),
                    ): int,
                }
            ),
            errors=errors,
        )

    async def _test_mqtt_connection(self, config):
        """Test MQTT connection with provided configuration."""
        try:
            self._client = WirenBoardMqttClient(
                hass=self.hass,
                host=config[CONF_HOST],
                port=config[CONF_PORT],
                username=config.get(CONF_USERNAME),
                password=config.get(CONF_PASSWORD),
                client_id=config.get(CONF_CLIENT_ID),
                use_ssl=config.get(CONF_USE_SSL),
                verify_ssl=config.get(CONF_VERIFY_SSL),
                keepalive=config.get(CONF_KEEPALIVE),
            )

            connected = await self._client.test_connection()
            if connected:
                await self._client.disconnect()
            return connected

        except Exception as ex:
            if self._client:
                await self._client.disconnect()
            return False
