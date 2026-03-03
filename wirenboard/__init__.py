"""The Wiren Board integration."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS
from .device_manager import WirenBoardDeviceManager
from .mqtt_client import WirenBoardMqttClient

logger = logging.getLogger(__name__)

# Service schemas
SERVICE_REDISCOVER_SCHEMA = vol.Schema(
    {
        vol.Optional("device_filter"): cv.string,
    }
)

SERVICE_PUBLISH_SCHEMA = vol.Schema(
    {
        vol.Required("topic"): cv.string,
        vol.Required("payload"): cv.string,
        vol.Optional("retain", default=False): cv.boolean,
    }
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Wiren Board component."""
    hass.data.setdefault(DOMAIN, {})
    logger.debug("Wiren Board integration setup started")

    await _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Wiren Board from a config entry."""
    logger.debug("Setting up config entry: %s", entry.data)

    mqtt_client = WirenBoardMqttClient(
        hass=hass,
        host=entry.data["host"],
        port=entry.data["port"],
        username=entry.data.get("username"),
        password=entry.data.get("password"),
        client_id=entry.data.get("client_id"),
        use_ssl=entry.data.get("use_ssl", False),
        verify_ssl=entry.data.get("verify_ssl", True),
        keepalive=entry.data.get("keepalive", 60),
    )

    if not await mqtt_client.connect():
        logger.error("Failed to connect to MQTT broker")
        return False

    device_manager = WirenBoardDeviceManager(hass, entry, mqtt_client)
    await device_manager.async_setup()

    hass.data[DOMAIN][entry.entry_id] = {
        "mqtt_client": mqtt_client,
        "device_manager": device_manager,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    logger.info(
        "Wiren Board integration initialized successfully for %s", entry.data["host"]
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.entry_id in hass.data[DOMAIN]:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["device_manager"].async_teardown()
        await data["mqtt_client"].disconnect()

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _register_services(hass: HomeAssistant):
    """Register custom services."""

    async def rediscover_devices(call: ServiceCall):
        """Service to force rediscovery of devices."""
        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and "device_manager" in data:
                await data["device_manager"].async_rediscover()
                logger.info("Rediscovery triggered for entry %s", entry_id)
        hass.bus.async_fire("wirenboard_devices_rediscovered")

    async def publish_message(call: ServiceCall):
        """Service to publish custom MQTT message."""
        topic = call.data["topic"]
        payload = call.data["payload"]
        retain = call.data.get("retain", False)

        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and "mqtt_client" in data:
                try:
                    await data["mqtt_client"].publish(topic, str(payload), retain)
                    logger.info("Message published to %s", topic)
                except Exception as ex:
                    logger.error("Failed to publish message: %s", ex)

    async def test_discovery(call: ServiceCall):
        """Test service to list discovered devices."""
        logger.info("=== WIRENBOARD DISCOVERY TEST ===")
        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and "device_manager" in data:
                devices = data["device_manager"].get_all_devices()
                logger.info(
                    "Entry %s has %d devices:", entry_id, len(devices)
                )
                for key, device_info in devices.items():
                    logger.info("  - %s: %s", key, device_info)

    async def update_states(call: ServiceCall):
        """Service to force rediscovery and state update."""
        logger.info("Forcing update of all Wiren Board entities")
        for entry_id, data in hass.data[DOMAIN].items():
            if isinstance(data, dict) and "device_manager" in data:
                await data["device_manager"].async_rediscover()
                logger.info("Update triggered for entry %s", entry_id)

    hass.services.async_register(
        DOMAIN, "rediscover", rediscover_devices, schema=SERVICE_REDISCOVER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, "publish", publish_message, schema=SERVICE_PUBLISH_SCHEMA
    )
    hass.services.async_register(DOMAIN, "test_discovery", test_discovery)
    hass.services.async_register(DOMAIN, "update_states", update_states)

    logger.debug("Wiren Board services registered")
