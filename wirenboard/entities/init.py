"""The Wiren Board integration."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .device_manager import WirenBoardDeviceManager
from .mqtt_client import WirenBoardMqttClient

logger = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Wiren Board component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Wiren Board from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Initialize MQTT client
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

    # Connect to MQTT broker
    if not await mqtt_client.connect():
        logger.error("Failed to connect to MQTT broker")
        return False

    # Initialize device manager
    device_manager = WirenBoardDeviceManager(hass, entry, mqtt_client)
    await device_manager.async_setup()

    hass.data[DOMAIN][entry.entry_id] = {
        "mqtt_client": mqtt_client,
        "device_manager": device_manager,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await _register_services(hass, device_manager, mqtt_client)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    logger.info(
        "Wiren Board integration initialized successfully for %s", entry.data["host"]
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["device_manager"].async_teardown()
        await data["mqtt_client"].disconnect()

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _register_services(hass: HomeAssistant, device_manager, mqtt_client):
    """Register custom services."""

    async def rediscover_devices(call):
        """Service to force rediscovery of devices."""
        await device_manager.async_rediscover()

    async def publish_message(call):
        """Service to publish custom MQTT message."""
        topic = call.data.get("topic")
        payload = call.data.get("payload")
        retain = call.data.get("retain", False)

        if topic and payload is not None:
            await mqtt_client.publish(topic, str(payload), retain)

    hass.services.async_register(DOMAIN, "rediscover", rediscover_devices)
    hass.services.async_register(DOMAIN, "publish", publish_message)
