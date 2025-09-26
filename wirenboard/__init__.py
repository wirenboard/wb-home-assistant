"""The Wiren Board integration."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS

# Initialize device manager
from .device_manager import WirenBoardDeviceManager

# Initialize MQTT client
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

SERVICE_DISCOVER_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Optional("control_id"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Wiren Board component."""
    hass.data.setdefault(DOMAIN, {})

    # Enable debug logging
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    logger.debug("Wiren Board integration setup started")

    # Register services
    await _register_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Wiren Board from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    logger.debug(f"Setting up config entry: {entry.data}")

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

    device_manager = WirenBoardDeviceManager(hass, entry, mqtt_client)
    await device_manager.async_setup()

    hass.data[DOMAIN][entry.entry_id] = {
        "mqtt_client": mqtt_client,
        "device_manager": device_manager,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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


async def _register_services(hass: HomeAssistant):
    """Register custom services."""

    async def rediscover_devices(call: ServiceCall):
        """Service to force rediscovery of devices."""
        device_filter = call.data.get("device_filter")

        # If we have active config entries, use their device managers
        if DOMAIN in hass.data:
            for entry_id, data in hass.data[DOMAIN].items():
                device_manager = data.get("device_manager")
                if device_manager:
                    await device_manager.async_rediscover()
                    logger.info(f"Rediscovery triggered for entry {entry_id}")

        hass.bus.async_fire("wirenboard_devices_rediscovered")

    async def publish_message(call: ServiceCall):
        """Service to publish custom MQTT message."""
        topic = call.data.get("topic")
        payload = call.data.get("payload")
        retain = call.data.get("retain", False)

        if not topic or payload is None:
            logger.error("Topic and payload are required")
            return

        # Publish to all connected MQTT clients
        if DOMAIN in hass.data:
            for entry_id, data in hass.data[DOMAIN].items():
                mqtt_client = data.get("mqtt_client")
                if mqtt_client:
                    try:
                        await mqtt_client.publish(topic, str(payload), retain)
                        logger.info(f"Message published to {topic}")
                    except Exception as ex:
                        logger.error(f"Failed to publish message: {ex}")

    async def discover_device(call: ServiceCall):
        """Service to manually discover a specific device."""
        device_id = call.data.get("device_id")
        control_id = call.data.get("control_id")

        logger.info(
            f"Manual discovery requested for device {device_id}, control {control_id}",
        )

        # This would trigger discovery for specific device
        # Implementation depends on your discovery mechanism

    async def test_discovery(call: ServiceCall):
        """Test service to list discovered devices."""
        logger.info("=== WIRENBOARD DISCOVERY TEST ===")

        if DOMAIN not in hass.data:
            logger.info("No Wiren Board instances found")
            return

        for entry_id, data in hass.data[DOMAIN].items():
            device_manager = data.get("device_manager")
            if device_manager:
                devices = device_manager.get_all_devices()
                logger.info(f"Entry {entry_id} has {len(devices)} devices:")
                for key, device_info in devices.items():
                    logger.info(f"  - {key}: {device_info}")

    # Register services
    hass.services.async_register(
        DOMAIN, "rediscover", rediscover_devices, schema=SERVICE_REDISCOVER_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, "publish", publish_message, schema=SERVICE_PUBLISH_SCHEMA
    )

    hass.services.async_register(
        DOMAIN,
        "discover_device",
        discover_device,
        schema=SERVICE_DISCOVER_DEVICE_SCHEMA,
    )

    hass.services.async_register(DOMAIN, "test_discovery", test_discovery)

    logger.debug("Wiren Board services registered")

    async def update_states(call: ServiceCall):
        """Service to force update of all entities."""
        logger.info("Forcing update of all Wiren Board entities")

        if DOMAIN not in hass.data:
            logger.info("No Wiren Board instances found")
            return

        for entry_id, data in hass.data[DOMAIN].items():
            device_manager = data.get("device_manager")
            if device_manager:
                # Здесь можно добавить логику принудительного обновления
                logger.info(f"Update triggered for entry {entry_id}")

        # Запустим обновление всех сущностей
        for platform in PLATFORMS:
            entities = hass.data[DOMAIN][entry_id].get(platform, [])
            for entity in entities:
                if hasattr(entity, "async_update"):
                    await entity.async_update()

    hass.services.async_register(DOMAIN, "update_states", update_states)
