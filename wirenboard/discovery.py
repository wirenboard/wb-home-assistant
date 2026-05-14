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
        self._notified_devices: set = set()
        self._pending_notifications: Dict[str, Any] = {}

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
            topic_parts = topic.split("/")
            # Формат: /devices/device_id/controls/control_id/meta/meta_key
            if len(topic_parts) < 7:  # Минимум 7 частей из-за ведущего слеша
                return

            device_id = topic_parts[2]
            control_id = topic_parts[4]
            meta_key = topic_parts[6]

            # Update meta cache
            cache_key = f"{device_id}/{control_id}"
            is_new_device = cache_key not in self._meta_cache
            if is_new_device:
                self._meta_cache[cache_key] = {}

            self._meta_cache[cache_key][meta_key] = payload

            # Log enum meta reception
            if meta_key == "enum":
                logger.info("📨 RECEIVED ENUM META: %s:%s = %s", device_id, control_id, payload)

            # Check if we have enough meta data to create entity
            if self._has_complete_meta(cache_key):
                logger.info("📤 COMPLETE META for %s:%s, creating device_info", device_id, control_id)
                device_info = self._create_device_info(device_id, control_id, cache_key)

                # For text controls, delay first notification to allow enum to arrive
                device_type = self._meta_cache[cache_key].get(META_TYPE)
                if device_type == "text" and cache_key not in self._notified_devices:
                    # Schedule delayed notification for text controls
                    self._pending_notifications[cache_key] = device_info
                    self.hass.loop.call_later(
                        0.05,  # 50ms delay to wait for enum
                        lambda: self.hass.async_create_task(
                            self._async_send_pending_notification(cache_key)
                        )
                    )
                else:
                    # Non-text controls or updates to already-notified controls notify immediately
                    self._notified_devices.add(cache_key)
                    logger.info("📤 NOTIFYING LISTENERS for %s:%s with enum=%s", device_id, control_id, device_info.get("enum"))
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
            # Call the listener directly - it's the device manager's sync method
            listener(device_info)
        except Exception as ex:
            logger.error("Error notifying listener: %s", ex)

    async def _async_send_pending_notification(self, cache_key: str):
        """Send a pending notification after delay for text controls."""
        if cache_key not in self._pending_notifications:
            return

        # Get the latest device info (may have been updated with enum)
        device_info = self._pending_notifications.pop(cache_key)

        # Re-create device_info in case enum arrived during the delay
        if "/" in cache_key:
            device_id, control_id = cache_key.split("/")
            device_info = self._create_device_info(device_id, control_id, cache_key)

        self._notified_devices.add(cache_key)
        logger.info("📤 NOTIFYING LISTENERS for %s with enum=%s (delayed)", cache_key, device_info.get("enum"))
        await self._async_notify_listeners(device_info)

    def _has_complete_meta(self, cache_key: str) -> bool:
        """Check if we have complete meta data for a device."""
        meta = self._meta_cache.get(cache_key, {})
        has_type = META_TYPE in meta
        has_readonly = META_READONLY in meta
        has_order = META_ORDER in meta

        # Basic metadata required (type, readonly, order)
        return has_type and has_readonly and has_order

    def _create_device_info(
        self, device_id: str, control_id: str, cache_key: str
    ) -> Dict[str, Any]:
        """Create device information dictionary."""
        import json

        meta = self._meta_cache[cache_key]

        # Parse enum if present
        enum_str = meta.get("enum")
        enum_options = None
        if enum_str:
            try:
                enum_data = json.loads(enum_str)
                # enum_data is like {"blink": 0, "breathe": 1, ...}
                # We need list of keys as options
                enum_options = list(enum_data.keys())
                logger.info("✓ ENUM FOUND for %s/%s: %s", device_id, control_id, enum_options)
            except (json.JSONDecodeError, ValueError):
                logger.warning("Failed to parse enum for %s/%s: %s", device_id, control_id, enum_str)
        elif control_id in ["effect", "color_power_on_behavior"]:
            # Debug: log what meta we have for expected enum controls
            logger.info("⚠ NO ENUM META for %s/%s, meta keys: %s", device_id, control_id, list(meta.keys()))

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
            "enum": enum_options,
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
