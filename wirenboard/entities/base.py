"""Base entity for Wiren Board devices."""

import logging
from typing import Any, Dict

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from ..const import TOPIC_META_ERROR, TOPIC_STATE
from ..mqtt_client import SIGNAL_MQTT_DISCONNECTED, WirenBoardMqttClient

logger = logging.getLogger(__name__)


class WirenBoardEntity(Entity):
    """Base class for Wiren Board entities."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, device_info: Dict[str, Any], mqtt_client: WirenBoardMqttClient
    ) -> None:
        """Initialize the entity."""
        self._device_info = device_info
        self.mqtt_client = mqtt_client
        self._state = None
        self._available = False
        self._unsubscribe_callbacks = []

        device_title = device_info.get("device_title") or device_info["device_id"]
        device_driver = device_info.get("device_driver")

        self._attr_device_info = DeviceInfo(
            identifiers={("wirenboard", device_info["device_id"])},
            name=device_title,
            manufacturer="Wiren Board",
            model=device_driver or "Wiren Board Device",
        )

        self._attr_unique_id = (
            f"wirenboard_{device_info['device_id']}_{device_info['control_id']}"
        )

        logger.debug("Initializing entity: %s", self.unique_id)

    @property
    def device_id(self) -> str:
        return self._device_info["device_id"]

    @property
    def control_id(self) -> str:
        return self._device_info["control_id"]

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        description = self._device_info.get("description")
        if description:
            return description
        return f"{self.device_id} {self.control_id}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    async def async_added_to_hass(self):
        """Subscribe to MQTT topics when entity is added to HA."""
        logger.debug("Entity added to HA: %s", self.unique_id)
        await self._subscribe_topics()

        # Listen for MQTT disconnect signal
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_MQTT_DISCONNECTED,
                self._handle_mqtt_disconnected,
            )
        )

    @callback
    def _handle_mqtt_disconnected(self):
        """Mark entity unavailable on MQTT disconnect."""
        if self._available:
            self._available = False
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Unsubscribe from MQTT topics."""
        logger.debug("Entity removed from HA: %s", self.unique_id)
        for unsubscribe in self._unsubscribe_callbacks:
            if callable(unsubscribe):
                unsubscribe()
        self._unsubscribe_callbacks.clear()

    async def _subscribe_topics(self):
        """Subscribe to state and error MQTT topics."""
        state_topic = TOPIC_STATE.format(
            device=self.device_id, control=self.control_id
        )
        error_topic = TOPIC_META_ERROR.format(
            device=self.device_id, control=self.control_id
        )

        def state_message_received(topic: str, payload: str):
            """Handle incoming state messages from MQTT thread."""
            self.hass.loop.call_soon_threadsafe(
                lambda: self.hass.async_create_task(
                    self._async_process_state_message(payload)
                )
            )

        def error_message_received(topic: str, payload: str):
            """Handle incoming error messages from MQTT thread."""
            self.hass.loop.call_soon_threadsafe(
                lambda: self.hass.async_create_task(
                    self._async_process_error_message(payload)
                )
            )

        try:
            await self.mqtt_client.subscribe(state_topic, state_message_received)
            logger.debug("Subscribed to state topic: %s", state_topic)

            await self.mqtt_client.subscribe(error_topic, error_message_received)
            logger.debug("Subscribed to error topic: %s", error_topic)

            self._unsubscribe_callbacks.append(
                lambda: self.hass.async_create_task(
                    self.mqtt_client.unsubscribe(state_topic, state_message_received)
                )
            )
            self._unsubscribe_callbacks.append(
                lambda: self.hass.async_create_task(
                    self.mqtt_client.unsubscribe(error_topic, error_message_received)
                )
            )
        except Exception as ex:
            logger.error(
                "Failed to subscribe to topics for entity %s: %s",
                self.unique_id, ex,
            )

    def _handle_state_update(self, payload: str):
        """Handle state update - should be overridden by subclasses."""
        self._state = payload

    async def _async_process_state_message(self, payload: str):
        """Process state message in async context."""
        logger.debug("State update for %s: %s", self.unique_id, payload)
        self._handle_state_update(payload)
        self._available = True
        self.async_write_ha_state()

    async def _async_process_error_message(self, payload: str):
        """Process meta/error message per WB convention.

        Empty string = no error (available).
        "r" = read error, "w" = write error, "p" = period miss.
        Combinations like "rw" are possible.
        """
        if payload == "":
            # No error — available (state will be updated by state topic)
            if not self._available:
                self._available = True
                self.async_write_ha_state()
        else:
            # Error present — mark unavailable
            if self._available:
                logger.warning(
                    "Entity %s became unavailable: error=%s", self.unique_id, payload
                )
                self._available = False
                self.async_write_ha_state()
