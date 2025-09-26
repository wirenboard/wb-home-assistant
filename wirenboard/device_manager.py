"""Device manager for Wiren Board integration."""

import logging
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import SIGNAL_DEVICE_DISCOVERED
from .discovery import WirenBoardDiscovery
from .mqtt_client import WirenBoardMqttClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class WirenBoardDeviceManager:
    """Manage Wiren Board devices and their entities."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, mqtt_client: WirenBoardMqttClient
    ):
        self.hass = hass
        self.entry = entry
        self.mqtt_client = mqtt_client
        self.discovery = WirenBoardDiscovery(hass, entry, mqtt_client)
        self.devices: Dict[str, Dict[str, Any]] = {}
        self._unsubscribe_callbacks = []

    async def async_setup(self):
        """Set up the device manager."""
        logger.debug("Setting up device manager")
        await self.discovery.async_setup()

        # Add listener for device discovery - use sync callback
        unsubscribe = self.discovery.async_add_listener(self._sync_on_device_discovered)
        self._unsubscribe_callbacks.append(unsubscribe)

        logger.info("Device manager setup complete")

    async def async_teardown(self):
        """Tear down the device manager."""
        logger.debug("Tearing down device manager")
        for unsubscribe in self._unsubscribe_callbacks:
            if callable(unsubscribe):
                unsubscribe()
        await self.discovery.async_teardown()
        logger.info("Device manager teardown complete")

    async def async_rediscover(self):
        """Force rediscovery of devices."""
        logger.debug("Forcing rediscovery")
        await self.discovery.async_rediscover()

    def _sync_on_device_discovered(self, device_info: Dict[str, Any]):
        """Handle discovered device from MQTT thread - SYNCHRONOUS version."""
        # This runs in MQTT thread - schedule async processing in main loop
        self.hass.loop.call_soon_threadsafe(
            lambda: self.hass.async_create_task(
                self._async_process_device_discovery(device_info)
            )
        )

    async def _async_process_device_discovery(self, device_info: Dict[str, Any]):
        """Process device discovery in async context."""
        device_id = device_info["device_id"]
        control_id = device_info["control_id"]

        key = f"{device_id}_{control_id}"

        if key not in self.devices:
            self.devices[key] = device_info
            logger.info(
                "New device discovered: %s, control: %s (type: %s)",
                device_id,
                control_id,
                device_info["device_type"],
            )

            # Now we're in async context - safe to call async_dispatcher_send
            async_dispatcher_send(self.hass, SIGNAL_DEVICE_DISCOVERED, device_info)
            logger.debug("Discovery signal sent for device: %s", key)
        else:
            logger.debug("Device already known: %s", key)

    def get_device_info(
        self, device_id: str, control_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get device information."""
        key = f"{device_id}_{control_id}"
        return self.devices.get(key)

    def get_all_devices(self) -> Dict[str, Dict[str, Any]]:
        """Get all discovered devices."""
        logger.debug("Returning %d discovered devices", len(self.devices))
        return self.devices.copy()
