"""MQTT client for Wiren Board integration."""

import asyncio
import logging
import re
import ssl
import uuid
from typing import Callable, Dict, List, Optional

import paho.mqtt.client as mqtt

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

logger = logging.getLogger(__name__)

SIGNAL_MQTT_CONNECTED = f"{DOMAIN}_mqtt_connected"
SIGNAL_MQTT_DISCONNECTED = f"{DOMAIN}_mqtt_disconnected"


def _is_wildcard(pattern: str) -> bool:
    """Check if pattern contains MQTT wildcards."""
    return "+" in pattern or "#" in pattern


def _compile_wildcard(pattern: str) -> re.Pattern:
    """Compile MQTT wildcard pattern to regex."""
    regex = re.escape(pattern).replace(r"\+", "[^/]+").replace(r"\#", ".+") + "$"
    return re.compile(regex)


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
        keepalive: int = 120,
    ):
        self.hass = hass
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id or f"ha_wirenboard_{uuid.uuid4().hex[:8]}"
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl
        self.keepalive = keepalive

        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self._shutting_down = False
        self._connect_event = asyncio.Event()

        # Separate exact topic callbacks (O(1) lookup) from wildcard callbacks
        self._exact_callbacks: Dict[str, List[Callable]] = {}
        self._wildcard_callbacks: List[tuple[str, re.Pattern, List[Callable]]] = []
        # All subscriptions for re-subscribe on reconnect
        self._subscriptions: set[str] = set()

    async def connect(self) -> bool:
        """Connect to MQTT broker."""
        try:
            self.client = mqtt.Client(
                client_id=self.client_id, protocol=mqtt.MQTTv311
            )

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

            # Let paho handle reconnection internally (in its own thread)
            self.client.reconnect_delay_set(min_delay=1, max_delay=60)

            self._connect_event.clear()
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
        self._shutting_down = True
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False

    async def subscribe(self, pattern: str, callback: Callable):
        """Subscribe to MQTT topic pattern."""
        if not self.connected or not self.client:
            raise RuntimeError("MQTT client not connected")

        is_new = pattern not in self._subscriptions

        if _is_wildcard(pattern):
            # Wildcard pattern — store separately
            existing = None
            for entry in self._wildcard_callbacks:
                if entry[0] == pattern:
                    existing = entry
                    break
            if existing:
                existing[2].append(callback)
            else:
                compiled = _compile_wildcard(pattern)
                self._wildcard_callbacks.append((pattern, compiled, [callback]))
        else:
            # Exact topic — O(1) dict lookup
            if pattern not in self._exact_callbacks:
                self._exact_callbacks[pattern] = []
            self._exact_callbacks[pattern].append(callback)

        if is_new:
            self._subscriptions.add(pattern)
            self.client.subscribe(pattern)

    async def unsubscribe(self, pattern: str, callback: Callable):
        """Unsubscribe from MQTT topic pattern."""
        if _is_wildcard(pattern):
            for i, entry in enumerate(self._wildcard_callbacks):
                if entry[0] == pattern and callback in entry[2]:
                    entry[2].remove(callback)
                    if not entry[2]:
                        self._wildcard_callbacks.pop(i)
                        self._subscriptions.discard(pattern)
                        if self.client:
                            self.client.unsubscribe(pattern)
                    break
        else:
            if pattern in self._exact_callbacks:
                if callback in self._exact_callbacks[pattern]:
                    self._exact_callbacks[pattern].remove(callback)
                if not self._exact_callbacks[pattern]:
                    del self._exact_callbacks[pattern]
                    self._subscriptions.discard(pattern)
                    if self.client:
                        self.client.unsubscribe(pattern)

    async def publish(self, topic: str, payload: str, retain: bool = False):
        """Publish message to MQTT topic."""
        if not self.connected or not self.client:
            raise RuntimeError("MQTT client not connected")

        self.client.publish(topic, payload, retain=retain)

    def _on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection from paho thread.

        This runs in paho's network thread — must be fast.
        """
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker at %s:%s", self.host, self.port)

            # Re-subscribe to all tracked topics (paho thread — safe)
            for pattern in self._subscriptions:
                client.subscribe(pattern)

            # Notify HA async
            self.hass.loop.call_soon_threadsafe(
                lambda: self.hass.async_create_task(self._async_on_connect())
            )
        else:
            self.connected = False
            logger.error("MQTT connection failed with code: %s", rc)

        self._connect_event.set()

    def _on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection from paho thread.

        paho's loop_start() with reconnect_delay_set() will auto-reconnect.
        """
        was_connected = self.connected
        self.connected = False
        self._connect_event.clear()

        if was_connected and not self._shutting_down:
            logger.warning("Disconnected from MQTT broker (rc=%s), auto-reconnecting", rc)
            self.hass.loop.call_soon_threadsafe(
                lambda: self.hass.async_create_task(self._async_on_disconnect())
            )

    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages from paho thread.

        Optimized: O(1) dict lookup for exact topics, regex only for wildcards.
        """
        topic = msg.topic
        payload = msg.payload.decode()

        matched_callbacks = []

        # O(1) exact topic lookup
        exact = self._exact_callbacks.get(topic)
        if exact:
            matched_callbacks.extend(exact)

        # Only iterate wildcard patterns (typically 2-3)
        for _, compiled_re, callbacks in self._wildcard_callbacks:
            if compiled_re.match(topic):
                matched_callbacks.extend(callbacks)

        if not matched_callbacks:
            return

        for callback in matched_callbacks:
            try:
                callback(topic, payload)
            except Exception as ex:
                logger.error("Error in MQTT callback for %s: %s", topic, ex)

    async def _async_on_connect(self):
        """Notify HA about MQTT connection in async context."""
        async_dispatcher_send(self.hass, SIGNAL_MQTT_CONNECTED)

    async def _async_on_disconnect(self):
        """Notify HA about MQTT disconnection in async context."""
        async_dispatcher_send(self.hass, SIGNAL_MQTT_DISCONNECTED)

    async def test_connection(self) -> bool:
        """Test MQTT connection by connecting and disconnecting."""
        connected = await self.connect()
        if connected:
            await self.disconnect()
        return connected
