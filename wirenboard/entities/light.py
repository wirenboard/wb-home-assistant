"""Light entity for Wiren Board."""

import logging
from typing import Any

import homeassistant.util.color as color_util
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)

from ..const import TOPIC_COMMAND, TOPIC_META_ERROR, TOPIC_STATE
from .base import WirenBoardEntity

logger = logging.getLogger(__name__)


class WirenBoardLight(WirenBoardEntity, LightEntity):
    """Representation of a Wiren Board light.

    Three shapes are supported:
    - RGB Palette (device_type "rgb") — HS color + brightness in one MQTT payload
      "R;G;B".
    - Dimmable channel — a switch control paired with a "<name> Brightness"
      range peer; on/off and brightness go through two separate topics.
    - Plain on/off switch surfaced as a Light — kept for completeness, though
      the normal switch/binary_sensor mapping usually handles this.
    """

    def __init__(self, device_info: dict[str, Any], mqtt_client: Any) -> None:
        """Initialize the light."""
        super().__init__(device_info, mqtt_client)

        device_type = device_info.get("type", "")
        self._is_rgb = device_type == "rgb"
        self._brightness_control_id: str | None = device_info.get(
            "brightness_control_id"
        )
        self._is_dimmable = self._brightness_control_id is not None
        # Device-reported range for the brightness channel — populated by
        # discovery from the peer's meta (typically 0..100 on WB devices).
        self._brightness_min = self._coerce_int(
            device_info.get("brightness_min"), 0
        )
        self._brightness_max = self._coerce_int(
            device_info.get("brightness_max"), 100
        )
        if self._brightness_max <= self._brightness_min:
            self._brightness_max = self._brightness_min + 100
        self._brightness_readonly = bool(
            device_info.get("brightness_readonly") or False
        )
        self._last_brightness_device_val = self._brightness_max
        self._brightness_error = False

        if self._is_rgb:
            self._attr_supported_color_modes = {ColorMode.HS}
            self._attr_color_mode = ColorMode.HS
            self._hs_color = (0.0, 0.0)
            self._brightness = 255
        elif self._is_dimmable:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._brightness = 0
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @property
    def available(self) -> bool:
        """Available only if both switch and brightness peer report no error."""
        if not self._available:
            return False
        return not self._brightness_error

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        if self._is_rgb:
            return self._state not in [None, "0;0;0", "0", ""] and self._brightness > 0
        return self._state == "1"

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0-255)."""
        if self._is_rgb or self._is_dimmable:
            return self._brightness
        return None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the HS color value."""
        if not self._is_rgb:
            return None
        return self._hs_color

    def _hs_to_rgb(self, hs_color: tuple[float, float], brightness: int) -> tuple[int, int, int]:
        """Convert HS color and brightness to RGB."""
        rgb = color_util.color_hs_to_RGB(hs_color[0], hs_color[1])
        scale = brightness / 255.0
        return (
            int(rgb[0] * scale),
            int(rgb[1] * scale),
            int(rgb[2] * scale),
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if self._is_rgb:
            if ATTR_HS_COLOR in kwargs:
                self._hs_color = tuple(kwargs[ATTR_HS_COLOR])
            elif ATTR_RGB_COLOR in kwargs:
                rgb = kwargs[ATTR_RGB_COLOR]
                self._hs_color = color_util.color_RGB_to_hs(rgb[0], rgb[1], rgb[2])

            if ATTR_BRIGHTNESS in kwargs:
                self._brightness = kwargs[ATTR_BRIGHTNESS]

            if self._brightness == 0:
                self._brightness = 255

            rgb = self._hs_to_rgb(self._hs_color, self._brightness)
            await self._publish_switch(f"{rgb[0]};{rgb[1]};{rgb[2]}")
            return

        if self._is_dimmable:
            if ATTR_BRIGHTNESS in kwargs:
                brightness_255 = kwargs[ATTR_BRIGHTNESS]
                pct = self._ha_to_device_brightness(brightness_255)
                self._last_brightness_device_val = pct
                await self._publish_brightness(pct)
            elif self._last_brightness_device_val == 0:
                # Brightness slider is currently at zero — restore to full when
                # the user just toggles on with no explicit brightness value.
                self._last_brightness_device_val = self._brightness_max
                await self._publish_brightness(self._brightness_max)
            await self._publish_switch("1")
            return

        await self._publish_switch("1")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if self._is_rgb:
            await self._publish_switch("0;0;0")
            return
        await self._publish_switch("0")

    async def _async_process_state_message(self, payload: str) -> None:
        """Process state message for the switch/RGB topic."""
        logger.debug("Light state update for %s: %s", self.unique_id, payload)
        self._state = payload
        self._available = True

        if self._is_rgb and payload:
            try:
                parts = payload.split(";")
                if len(parts) == 3:
                    r = max(0, min(255, int(parts[0])))
                    g = max(0, min(255, int(parts[1])))
                    b = max(0, min(255, int(parts[2])))
                    max_channel = max(r, g, b)
                    if max_channel > 0:
                        normalized_r = int((r / max_channel) * 255)
                        normalized_g = int((g / max_channel) * 255)
                        normalized_b = int((b / max_channel) * 255)
                        self._hs_color = color_util.color_RGB_to_hs(
                            normalized_r, normalized_g, normalized_b
                        )
                        self._brightness = max_channel
                    else:
                        self._brightness = 0
                    logger.debug(
                        "Parsed RGB: actual=(%d,%d,%d), hs_color=%s, brightness=%d",
                        r, g, b, self._hs_color, self._brightness,
                    )
            except (ValueError, IndexError) as ex:
                logger.warning(
                    "Failed to parse RGB value '%s' for %s: %s",
                    payload, self.unique_id, ex,
                )

        self.async_write_ha_state()

    async def _subscribe_topics(self) -> None:
        """Subscribe to state topics. For dimmables, also to the brightness peer."""
        await super()._subscribe_topics()

        if not self._is_dimmable:
            return

        brightness_state_topic = TOPIC_STATE.format(
            device=self.device_id, control=self._brightness_control_id
        )
        brightness_error_topic = TOPIC_META_ERROR.format(
            device=self.device_id, control=self._brightness_control_id
        )

        def brightness_state_received(topic: str, payload: str) -> None:
            self.hass.loop.call_soon_threadsafe(
                lambda: self.hass.async_create_task(
                    self._async_process_brightness_message(payload)
                )
            )

        def brightness_error_received(topic: str, payload: str) -> None:
            self.hass.loop.call_soon_threadsafe(
                lambda: self.hass.async_create_task(
                    self._async_process_brightness_error(payload)
                )
            )

        await self._subscribe_one(brightness_state_topic, brightness_state_received, "brightness state")
        await self._subscribe_one(brightness_error_topic, brightness_error_received, "brightness error")

    async def _subscribe_one(self, topic: str, cb, label: str) -> None:
        try:
            await self.mqtt_client.subscribe(topic, cb)
            logger.debug("Subscribed to %s topic: %s", label, topic)
            self._unsubscribe_callbacks.append(
                lambda: self.hass.async_create_task(
                    self.mqtt_client.unsubscribe(topic, cb)
                )
            )
        except Exception as ex:
            logger.error(
                "Failed to subscribe to %s topic for %s: %s",
                label, self.unique_id, ex,
            )

    async def _async_process_brightness_error(self, payload: str) -> None:
        """Reflect brightness peer's meta/error into the Light's availability."""
        if payload == "":
            self._brightness_error = False
        else:
            if not self._brightness_error:
                logger.warning(
                    "Entity %s brightness peer became unavailable: error=%s",
                    self.unique_id, payload,
                )
            self._brightness_error = True
        self.async_write_ha_state()

    async def _async_process_brightness_message(self, payload: str) -> None:
        """Process brightness state (0..device_max) and reflect in HA brightness."""
        if payload == "":
            return
        try:
            device_val = int(float(payload))
        except (TypeError, ValueError):
            logger.warning(
                "Invalid brightness payload for %s: %r", self.unique_id, payload
            )
            return
        device_val = max(self._brightness_min, min(self._brightness_max, device_val))
        self._last_brightness_device_val = device_val
        self._brightness = self._device_to_ha_brightness(device_val)
        self.async_write_ha_state()

    def _ha_to_device_brightness(self, ha_brightness: int) -> int:
        """Map HA brightness (0..255) to device range (0..max)."""
        span = self._brightness_max - self._brightness_min
        if span <= 0:
            return self._brightness_min
        scaled = round(ha_brightness / 255 * span)
        return self._brightness_min + max(0, min(span, scaled))

    def _device_to_ha_brightness(self, device_val: int) -> int:
        """Map device brightness (0..max) to HA range (0..255)."""
        span = self._brightness_max - self._brightness_min
        if span <= 0:
            return 0
        return round((device_val - self._brightness_min) / span * 255)

    async def _publish_switch(self, payload: str) -> None:
        """Publish to the primary (switch/RGB) command topic."""
        await self._publish_to(self.control_id, payload)

    async def _publish_brightness(self, device_val: int) -> None:
        """Publish to the brightness command topic (dimmable channel only)."""
        if not self._brightness_control_id:
            return
        if self._brightness_readonly:
            logger.warning(
                "Brightness peer of %s is read-only", self.unique_id
            )
            return
        await self._publish_to(self._brightness_control_id, str(device_val))

    async def _publish_to(self, control_id: str, payload: str) -> None:
        if self._device_info.get("readonly"):
            logger.warning("Device %s is read-only", self.unique_id)
            return
        command_topic = TOPIC_COMMAND.format(
            device=self.device_id, control=control_id
        )
        await self.mqtt_client.publish(command_topic, payload, False)

