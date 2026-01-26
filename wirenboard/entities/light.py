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

from ..const import TOPIC_COMMAND
from .base import WirenBoardEntity

logger = logging.getLogger(__name__)


class WirenBoardLight(WirenBoardEntity, LightEntity):
    """Representation of a Wiren Board light."""

    def __init__(self, device_info: dict[str, Any], mqtt_client: Any) -> None:
        """Initialize the light."""
        super().__init__(device_info, mqtt_client)
        
        # Determine if this is an RGB light based on device type
        device_type = device_info.get("type", "")
        self._is_rgb = device_type == "rgb"
        
        # Set color mode based on device type
        if self._is_rgb:
            # Use HS mode for better UI with brightness slider
            self._attr_supported_color_modes = {ColorMode.HS}
            self._attr_color_mode = ColorMode.HS
            self._hs_color = (0.0, 0.0)  # Default: white (no hue, no saturation)
            self._brightness = 255  # Default full brightness
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        if self._is_rgb:
            # For RGB, check if state is not "0;0;0" (all off) and brightness > 0
            return self._state not in [None, "0;0;0", "0", ""] and self._brightness > 0
        return self._state == "1"

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0-255)."""
        if not self._is_rgb:
            return None
        return self._brightness

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the HS color value."""
        if not self._is_rgb:
            return None
        return self._hs_color

    def _hs_to_rgb(self, hs_color: tuple[float, float], brightness: int) -> tuple[int, int, int]:
        """Convert HS color and brightness to RGB."""
        # Convert HS to RGB (returns 0-255 range)
        rgb = color_util.color_hs_to_RGB(hs_color[0], hs_color[1])
        # Scale by brightness
        scale = brightness / 255.0
        return (
            int(rgb[0] * scale),
            int(rgb[1] * scale),
            int(rgb[2] * scale),
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if self._is_rgb:
            # Update HS color if provided
            if ATTR_HS_COLOR in kwargs:
                self._hs_color = tuple(kwargs[ATTR_HS_COLOR])
            # Support RGB color input (convert to HS)
            elif ATTR_RGB_COLOR in kwargs:
                rgb = kwargs[ATTR_RGB_COLOR]
                self._hs_color = color_util.color_RGB_to_hs(rgb[0], rgb[1], rgb[2])
            
            # Update brightness if provided
            if ATTR_BRIGHTNESS in kwargs:
                self._brightness = kwargs[ATTR_BRIGHTNESS]
            
            # If brightness is 0, set to full
            if self._brightness == 0:
                self._brightness = 255
            
            # Convert HS + brightness to RGB and send to device
            rgb = self._hs_to_rgb(self._hs_color, self._brightness)
            payload = f"{rgb[0]};{rgb[1]};{rgb[2]}"
            await self._publish_command(payload)
        else:
            # Simple on/off light
            await self._publish_command("1")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if self._is_rgb:
            await self._publish_command("0;0;0")
        else:
            await self._publish_command("0")

    async def _async_process_state_message(self, payload: str) -> None:
        """Process state message for light."""
        logger.debug("Light state update for %s: %s", self.unique_id, payload)
        self._state = payload
        self._available = True
        
        # Parse RGB values if this is an RGB light
        if self._is_rgb and payload:
            try:
                # Expected format: "R;G;B"
                parts = payload.split(";")
                if len(parts) == 3:
                    r = int(parts[0])
                    g = int(parts[1])
                    b = int(parts[2])
                    # Clamp values to valid range
                    r = max(0, min(255, r))
                    g = max(0, min(255, g))
                    b = max(0, min(255, b))
                    
                    # Calculate brightness from actual RGB values
                    # Use the maximum channel value as brightness
                    max_channel = max(r, g, b)
                    
                    if max_channel > 0:
                        # Normalize RGB to full brightness for HS conversion
                        normalized_r = int((r / max_channel) * 255)
                        normalized_g = int((g / max_channel) * 255)
                        normalized_b = int((b / max_channel) * 255)
                        
                        # Convert normalized RGB to HS
                        self._hs_color = color_util.color_RGB_to_hs(
                            normalized_r, normalized_g, normalized_b
                        )
                        self._brightness = max_channel
                    else:
                        # All channels are 0 - light is off
                        self._brightness = 0
                    
                    logger.debug(
                        "Parsed RGB: actual=(%d,%d,%d), hs_color=%s, brightness=%d",
                        r, g, b, self._hs_color, self._brightness
                    )
            except (ValueError, IndexError) as ex:
                logger.warning(
                    "Failed to parse RGB value '%s' for %s: %s",
                    payload, self.unique_id, ex
                )
        
        self.async_write_ha_state()

    async def _publish_command(self, payload: str) -> None:
        """Publish command to MQTT."""
        if self._device_info.get("readonly"):
            logger.warning("Device %s is read-only", self.unique_id)
            return

        command_topic = TOPIC_COMMAND.format(
            device=self.device_id, control=self.control_id
        )
        await self.mqtt_client.publish(command_topic, payload, False)
