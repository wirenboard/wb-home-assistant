"""Discovery system for Wiren Board devices."""

import logging
from typing import Any, Callable, Dict, List

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import META_ORDER, META_READONLY, META_TYPE
from .mqtt_client import WirenBoardMqttClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class WirenBoardDiscovery:
    """Discover Wiren Board devices via MQTT."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, mqtt_client: WirenBoardMqttClient
    ):
        self.hass = hass
        self.entry = entry
        self.mqtt_client = mqtt_client
        self._listeners: List[Callable] = []
        self._meta_cache: Dict[str, Dict[str, Any]] = {}

    async def async_setup(self):
        """Set up discovery."""
        discovery_topic = self.entry.data.get(
            "discovery_topic", "/devices/+/controls/+/meta/+"
        )

        logger.debug("Starting discovery setup for topic: %s", discovery_topic)

        # Subscribe to meta topics for device discovery
        await self.mqtt_client.subscribe(
            discovery_topic, self._sync_handle_meta_message
        )

        logger.info("Discovery setup complete for topic: %s", discovery_topic)

    async def async_teardown(self):
        """Tear down discovery."""
        discovery_topic = self.entry.data.get(
            "discovery_topic", "/devices/+/controls/+/meta/+"
        )
        await self.mqtt_client.unsubscribe(
            discovery_topic, self._sync_handle_meta_message
        )
        self._listeners.clear()
        logger.debug("Discovery teardown complete")

    async def async_rediscover(self):
        """Force rediscovery of devices."""
        self._meta_cache.clear()
        logger.info("Rediscovery triggered")

    def async_add_listener(self, listener: Callable):
        """Add a listener for device discovery."""
        self._listeners.append(listener)
        logger.debug("Added discovery listener, total: %d", len(self._listeners))

        # Notify about already discovered devices
        for cache_key, meta in self._meta_cache.items():
            if self._has_complete_meta(cache_key):
                device_id, control_id = cache_key.split("/")
                device_info = self._create_device_info(device_id, control_id, cache_key)
                # Schedule notification
                self.hass.loop.call_soon_threadsafe(
                    lambda: self.hass.async_create_task(
                        self._async_notify_listener(listener, device_info)
                    )
                )

        return lambda: self._listeners.remove(listener)

    def _sync_handle_meta_message(self, topic: str, payload: str):
        """Handle incoming meta messages from MQTT thread - SYNCHRONOUS version."""
        # This runs in MQTT thread - schedule async processing in main loop
        self.hass.loop.call_soon_threadsafe(
            lambda: self.hass.async_create_task(
                self._async_process_meta_message(topic, payload)
            )
        )

    async def _async_process_meta_message(self, topic: str, payload: str):
        """Process meta message in async context."""
        try:
            logger.debug("Discovery received meta message: %s = %s", topic, payload)

            topic_parts = topic.split("/")
            # Формат: /devices/device_id/controls/control_id/meta/meta_key
            if len(topic_parts) < 7:  # Минимум 7 частей из-за ведущего слеша
                logger.debug("Invalid topic format: %s", topic)
                return

            device_id = topic_parts[2]
            control_id = topic_parts[4]
            meta_key = topic_parts[6]

            # Update meta cache
            cache_key = f"{device_id}/{control_id}"
            if cache_key not in self._meta_cache:
                self._meta_cache[cache_key] = {}
                logger.debug("New device control discovered: %s", cache_key)

            self._meta_cache[cache_key][meta_key] = payload

            # Check if we have enough meta data to create entity
            if self._has_complete_meta(cache_key):
                device_info = self._create_device_info(device_id, control_id, cache_key)
                await self._async_notify_listeners(device_info)

        except Exception as ex:
            logger.error("Error processing meta message for topic %s: %s", topic, ex)

    async def _async_notify_listeners(self, device_info: Dict[str, Any]):
        """Notify all listeners about discovered device."""
        logger.debug(
            "Notifying %d listeners about device %s",
            len(self._listeners),
            device_info["device_id"],
        )

        if not self._listeners:
            logger.warning("No listeners registered for device discovery")
            return

        for listener in self._listeners:
            await self._async_notify_listener(listener, device_info)

    async def _async_notify_listener(
        self, listener: Callable, device_info: Dict[str, Any]
    ):
        """Notify a single listener."""
        try:
            logger.debug("Notifying listener about device %s", device_info["device_id"])
            # Call the listener directly - it's the device manager's sync method
            listener(device_info)
        except Exception as ex:
            logger.error("Error notifying listener: %s", ex)

    def _has_complete_meta(self, cache_key: str) -> bool:
        """Check if we have complete meta data for a device."""
        meta = self._meta_cache.get(cache_key, {})
        has_type = META_TYPE in meta
        has_readonly = META_READONLY in meta
        has_order = META_ORDER in meta
        return has_type and has_readonly and has_order

    def _create_device_info(
        self, device_id: str, control_id: str, cache_key: str
    ) -> Dict[str, Any]:
        """Create device information dictionary."""
        meta = self._meta_cache[cache_key]

        device_info = {
            "device_id": device_id,
            "control_id": control_id,
            "device_type": meta.get(META_TYPE),
            "readonly": meta.get(META_READONLY) == "1",
            "unit": meta.get("units"),
            "max": meta.get("max"),
            "min": meta.get("min"),
            "description": meta.get("description"),
            "topic_prefix": self.entry.data.get("topic_prefix", "/devices"),
            "type": meta.get(META_TYPE),
        }

        # Log detailed info for LED devices
        if "led" in device_id.lower():
            logger.info(
                "LED device discovered: %s/%s - type=%s, readonly=%s, meta=%s",
                device_id,
                control_id,
                meta.get(META_TYPE),
                meta.get(META_READONLY),
                meta,
            )

        return device_info
