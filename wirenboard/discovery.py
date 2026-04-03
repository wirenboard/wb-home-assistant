"""Discovery system for Wiren Board devices."""

import json
import logging
from typing import Any, Callable, Dict, List

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import META_ORDER, META_READONLY, META_TYPE
from .mqtt_client import WirenBoardMqttClient

logger = logging.getLogger(__name__)

DEVICE_META_TOPIC = "/devices/+/meta"


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
        self._device_meta_cache: Dict[str, Dict[str, Any]] = {}

    async def async_setup(self):
        """Set up discovery."""
        discovery_topic = self.entry.data.get(
            "discovery_topic", "/devices/+/controls/+/meta/+"
        )

        logger.debug("Starting discovery setup for topic: %s", discovery_topic)

        # Subscribe to control meta topics for device discovery
        await self.mqtt_client.subscribe(
            discovery_topic, self._sync_handle_meta_message
        )

        # Subscribe to device-level meta for titles and driver info
        await self.mqtt_client.subscribe(
            DEVICE_META_TOPIC, self._sync_handle_device_meta
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
        await self.mqtt_client.unsubscribe(
            DEVICE_META_TOPIC, self._sync_handle_device_meta
        )
        self._listeners.clear()
        logger.debug("Discovery teardown complete")

    async def async_rediscover(self):
        """Force rediscovery of devices."""
        self._meta_cache.clear()
        logger.info("Rediscovery triggered")

    def get_device_title(self, device_id: str) -> str | None:
        """Get device title from device-level meta."""
        device_meta = self._device_meta_cache.get(device_id, {})
        title = device_meta.get("title")
        if isinstance(title, dict):
            return title.get("en") or title.get("ru")
        return None

    def get_device_driver(self, device_id: str) -> str | None:
        """Get device driver from device-level meta."""
        return self._device_meta_cache.get(device_id, {}).get("driver")

    def async_add_listener(self, listener: Callable):
        """Add a listener for device discovery."""
        self._listeners.append(listener)
        logger.debug("Added discovery listener, total: %d", len(self._listeners))

        # Notify about already discovered devices
        for cache_key in self._meta_cache:
            if self._has_complete_meta(cache_key):
                device_id, control_id = cache_key.split("/")
                device_info = self._create_device_info(device_id, control_id, cache_key)
                self.hass.loop.call_soon_threadsafe(
                    lambda di=device_info: self.hass.async_create_task(
                        self._async_notify_listener(listener, di)
                    )
                )

        return lambda: self._listeners.remove(listener)

    def _sync_handle_meta_message(self, topic: str, payload: str):
        """Handle incoming control meta messages from MQTT thread."""
        self.hass.loop.call_soon_threadsafe(
            lambda: self.hass.async_create_task(
                self._async_process_meta_message(topic, payload)
            )
        )

    def _sync_handle_device_meta(self, topic: str, payload: str):
        """Handle incoming device-level meta messages from MQTT thread."""
        self.hass.loop.call_soon_threadsafe(
            lambda: self.hass.async_create_task(
                self._async_process_device_meta(topic, payload)
            )
        )

    async def _async_process_device_meta(self, topic: str, payload: str):
        """Process device-level meta (JSON with title, driver)."""
        try:
            # Topic format: /devices/{device_id}/meta
            topic_parts = topic.split("/")
            if len(topic_parts) < 4:
                return
            device_id = topic_parts[2]

            try:
                meta = json.loads(payload)
            except (json.JSONDecodeError, ValueError):
                return

            if isinstance(meta, dict):
                self._device_meta_cache[device_id] = meta
                logger.debug("Device meta for %s: %s", device_id, meta)
        except Exception as ex:
            logger.error("Error processing device meta for %s: %s", topic, ex)

    async def _async_process_meta_message(self, topic: str, payload: str):
        """Process control meta message in async context."""
        try:
            topic_parts = topic.split("/")
            # Format: /devices/device_id/controls/control_id/meta/meta_key
            if len(topic_parts) < 7:
                return

            device_id = topic_parts[2]
            control_id = topic_parts[4]
            meta_key = topic_parts[6]

            cache_key = f"{device_id}/{control_id}"
            if cache_key not in self._meta_cache:
                self._meta_cache[cache_key] = {}

            self._meta_cache[cache_key][meta_key] = payload

            if self._has_complete_meta(cache_key):
                device_info = self._create_device_info(device_id, control_id, cache_key)
                await self._async_notify_listeners(device_info)

        except Exception as ex:
            logger.error("Error processing meta message for topic %s: %s", topic, ex)

    async def _async_notify_listeners(self, device_info: Dict[str, Any]):
        """Notify all listeners about discovered device."""
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
            listener(device_info)
        except Exception as ex:
            logger.error("Error notifying listener: %s", ex)

    def _has_complete_meta(self, cache_key: str) -> bool:
        """Check if we have complete meta data for a device."""
        meta = self._meta_cache.get(cache_key, {})
        return META_TYPE in meta and META_READONLY in meta and META_ORDER in meta

    def _create_device_info(
        self, device_id: str, control_id: str, cache_key: str
    ) -> Dict[str, Any]:
        """Create device information dictionary."""
        meta = self._meta_cache[cache_key]

        return {
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
            "device_title": self.get_device_title(device_id),
            "device_driver": self.get_device_driver(device_id),
        }
