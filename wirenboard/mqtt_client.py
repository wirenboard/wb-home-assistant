"""MQTT client for Wiren Board integration."""

import asyncio
import logging
import re
import ssl
from typing import Callable, Dict, List, Optional

import paho.mqtt.client as mqtt

from homeassistant.core import HomeAssistant

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def mqtt_topic_matches(subscription: str, topic: str) -> bool:
    """Check if a topic matches a subscription with wildcards."""
    regex = subscription.replace("+", "[^/]+").replace("#", ".+") + "$"
    return bool(re.match(regex, topic))


class WirenBoardMqttClient:
    """MQTT client for communicating with Wiren Board."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: Optional[str] = None,
        use_ssl: bool = False,
        verify_ssl: bool = True,
        keepalive: int = 60,
    ):
        self.hass = hass
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl
        self.keepalive = keepalive

        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self._connect_event = asyncio.Event()
        self._message_callbacks: Dict[str, List[Callable]] = {}

    async def connect(self) -> bool:
        """Connect to MQTT broker."""
        try:
            self.client = mqtt.Client(protocol=mqtt.MQTTv311)

            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)

            if self.use_ssl:
                ssl_context = ssl.create_default_context()
                if not self.verify_ssl:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE
                self.client.tls_set_context(ssl_context)

            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message

            self.client.connect_async(self.host, self.port, self.keepalive)
            self.client.loop_start()

            try:
                await asyncio.wait_for(self._connect_event.wait(), timeout=10.0)
                return self.connected
            except asyncio.TimeoutError:
                logger.error("MQTT connection timeout")
                return False

        except Exception as ex:
            logger.error("Failed to connect to MQTT broker: %s", ex)
            return False

    async def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False

    async def subscribe(self, pattern: str, callback: Callable):
        """Subscribe to MQTT topic pattern."""
        if not self.connected or not self.client:
            raise RuntimeError("MQTT client not connected")

        if pattern not in self._message_callbacks:
            self._message_callbacks[pattern] = []
            self.client.subscribe(pattern)

        self._message_callbacks[pattern].append(callback)

    async def unsubscribe(self, pattern: str, callback: Callable):
        """Unsubscribe from MQTT topic pattern."""
        if pattern in self._message_callbacks:
            if callback in self._message_callbacks[pattern]:
                self._message_callbacks[pattern].remove(callback)

            if not self._message_callbacks[pattern]:
                del self._message_callbacks[pattern]
                if self.client:
                    self.client.unsubscribe(pattern)

    async def publish(self, topic: str, payload: str, retain: bool = False):
        """Publish message to MQTT topic."""
        if not self.connected or not self.client:
            raise RuntimeError("MQTT client not connected")

        self.client.publish(topic, payload, retain=retain)

    def publish_sync(self, topic: str, payload: str, retain: bool = False):
        """Publish message to MQTT topic."""
        if not self.connected or not self.client:
            raise RuntimeError("MQTT client not connected")

        self.client.publish(topic, payload, retain=retain)

    def _on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        # Schedule in event loop
        self.hass.loop.call_soon_threadsafe(
            lambda: self.hass.async_create_task(self._async_on_connect(rc))
        )

    def _on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        # Schedule in event loop
        self.hass.loop.call_soon_threadsafe(
            lambda: self.hass.async_create_task(self._async_on_disconnect(rc))
        )

    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages."""
        # Direct call to callback - it will handle thread safety
        topic = msg.topic
        payload = msg.payload.decode()
        logger.debug("MQTT message received: %s = %s", topic, payload)

        matched_callbacks = []
        for pattern, callbacks in list(self._message_callbacks.items()):
            if mqtt_topic_matches(pattern, topic):
                logger.debug("Pattern %s matches topic %s", pattern, topic)
                matched_callbacks.extend(callbacks)
        if not matched_callbacks:
            logger.debug("No callbacks found for topic: %s", topic)
            logger.debug("Available patterns: %s", list(self._message_callbacks.keys()))
            return
        for callback in matched_callbacks:
            # Call the callback directly - it's responsible for thread safety
            try:
                callback(topic, payload)
            except Exception as ex:
                logger.error("Error in MQTT callback: %s", ex)

    async def _async_on_connect(self, rc):
        """Handle MQTT connection in async context."""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker at %s:%s", self.host, self.port)
        else:
            self.connected = False
            logger.error("MQTT connection failed with code: %s", rc)

        self._connect_event.set()

    async def _async_on_disconnect(self, rc):
        """Handle MQTT disconnection in async context."""
        self.connected = False
        logger.warning("Disconnected from MQTT broker")
        self._connect_event.clear()

    async def test_connection(
        self,
    ):
        return True

    def _async_on_message(self, topic: str, payload: str):
        """Handle incoming MQTT message in async context."""
        logger.debug("Looking for callbacks for topic: %s", topic)
        logger.debug("Available patterns: %s", list(self._message_callbacks.keys()))

        matched_callbacks = []

        # Find all patterns that match this topic
        for pattern, callbacks in self._message_callbacks.items():
            if mqtt_topic_matches(pattern, topic):
                logger.debug("Pattern %s matches topic %s", pattern, topic)
                matched_callbacks.extend(callbacks)

        if not matched_callbacks:
            logger.debug("No callbacks found for topic: %s", topic)
            return

        logger.debug(
            "Processing message for topic %s with %d callbacks",
            topic,
            len(matched_callbacks),
        )

        # Execute all matching callbacks
        for callback in matched_callbacks:
            asyncio.create_task(self._execute_callback(callback, topic, payload))

    async def _execute_callback(self, callback: Callable, topic: str, payload: str):
        """Execute a callback safely."""
        try:
            logger.debug("Executing callback for topic: %s", topic)
            if asyncio.iscoroutinefunction(callback):
                await callback(topic, payload)
            else:
                # Для синхронных функций используем executor
                await self.hass.async_add_executor_job(callback, topic, payload)
            logger.debug("Callback executed successfully for topic: %s", topic)
        except Exception as ex:
            logger.error("Error in MQTT message callback for topic %s: %s", topic, ex)
