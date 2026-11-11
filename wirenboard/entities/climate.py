"""Climate entity for a wb-scenarios thermostat."""

import logging
import math
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError

from ..const import TOPIC_COMMAND, TOPIC_META_ERROR, TOPIC_STATE
from .base import WirenBoardEntity

logger = logging.getLogger(__name__)


class WirenBoardClimate(WirenBoardEntity, ClimateEntity):
    """A thermostat backed by four controls of one scenario device."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, device_info: dict[str, Any], mqtt_client: Any) -> None:
        super().__init__(device_info, mqtt_client)
        self._values: dict[str, str] = {}
        self._errors: dict[str, str] = {}
        self._attr_min_temp = self._number(device_info.get("min"), 5.0)
        self._attr_max_temp = self._number(device_info.get("max"), 35.0)
        step = self._number(device_info.get("precision"), 0.1)
        self._attr_target_temperature_step = step if step > 0 else 0.1

    @staticmethod
    def _number(value: Any, default: float | None) -> float | None:
        try:
            number = float(value)
            return number if math.isfinite(number) else default
        except (TypeError, ValueError):
            return default

    @property
    def name(self) -> str | None:
        """Use the scenario device title as the climate entity name."""
        return None

    @property
    def available(self) -> bool:
        """Require the MQTT connection and all essential control values."""
        return (
            self._available
            and not any(self._errors.values())
            and all(
                control in self._values
                for control in (
                    "rule_enabled", "target_temperature",
                    "current_temperature", "actuator_status",
                )
            )
        )

    @property
    def current_temperature(self) -> float | None:
        return self._number(self._values.get("current_temperature"), None)

    @property
    def target_temperature(self) -> float | None:
        return self._number(self._values.get("target_temperature"), None)

    @property
    def hvac_mode(self) -> HVACMode | None:
        value = self._values.get("rule_enabled")
        if value is None:
            return None
        return HVACMode.HEAT if value == "1" else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        if self.hvac_mode is None:
            return None
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        value = self._values.get("actuator_status")
        if value is None:
            return None
        return HVACAction.HEATING if value == "1" else HVACAction.IDLE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode not in self.hvac_modes:
            raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
        await self._publish("rule_enabled", "1" if hvac_mode == HVACMode.HEAT else "0")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        value = self._number(temperature, None)
        if value is None or not self.min_temp <= value <= self.max_temp:
            raise HomeAssistantError(f"Temperature is outside {self.min_temp}..{self.max_temp} C")
        await self._publish("target_temperature", str(value))

    async def _publish(self, control: str, payload: str) -> None:
        topic = TOPIC_COMMAND.format(device=self.device_id, control=control)
        await self.mqtt_client.publish(topic, payload, False)

    async def _subscribe_topics(self) -> None:
        """Subscribe to all thermostat values and their error flags."""
        for control in (
            "rule_enabled", "target_temperature", "current_temperature",
            "actuator_status",
        ):
            for is_error, template in ((False, TOPIC_STATE), (True, TOPIC_META_ERROR)):
                topic = template.format(device=self.device_id, control=control)

                def received(topic: str, payload: str, control=control, is_error=is_error) -> None:
                    self.hass.loop.call_soon_threadsafe(
                        lambda: self.hass.async_create_task(
                            self._process_control(control, payload, is_error)
                        )
                    )

                await self.mqtt_client.subscribe(topic, received)
                self._unsubscribe_callbacks.append(
                    lambda topic=topic, received=received: self.hass.async_create_task(
                        self.mqtt_client.unsubscribe(topic, received)
                    )
                )

    async def _process_control(self, control: str, payload: str, is_error: bool) -> None:
        if is_error:
            self._errors[control] = payload
        elif payload != "":
            self._values[control] = payload
            self._available = True
        self.async_write_ha_state()
