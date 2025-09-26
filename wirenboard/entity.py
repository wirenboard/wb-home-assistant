from abc import ABC
import logging

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

logger = logging.getLogger(__name__)


class ExternalMQTTEntity(Entity, ABC):
    """Base class for entity in External MQTT."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        control_id: str,
        device_info: DeviceInfo,
    ):
        self.hass = hass
        self.device_id = device_id
        self.control_id = control_id
        self._device_info = device_info
        self._state = None
        self._attributes = {}
        self._available = False

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    @property
    def available(self) -> bool:
        return self._available

    @property
    def unique_id(self) -> str:
        return f"{self.device_id}_{self.control_id}"

    @property
    def name(self) -> str:
        return f"{self.device_id} {self.control_id}"

    async def async_added_to_hass(self):
        """Add in HA."""
        await self._subscribe_topics()

    async def _subscribe_topics(self):
        """Subscribe MQTT topics."""
        state_topic = f"device/{self.device_id}/controls/{self.control_id}"

        # @callback
        def state_message_received(msg):
            """Process incomming message."""
            self._state = msg.payload
            self._available = True
            self.async_write_ha_state()

        await mqtt.async_subscribe(self.hass, state_topic, state_message_received)


class ExternalMQTTSwitch(ExternalMQTTEntity):
    """Switch Entity."""

    @property
    def is_on(self) -> bool:
        return self._state == "1"

    async def async_turn_on(self, **kwargs):
        """Turn on."""
        await self._publish_command("1")

    async def async_turn_off(self, **kwargs):
        """Turn off."""
        await self._publish_command("0")

    async def _publish_command(self, payload: str):
        """Send command."""
        command_topic = f"device/{self.device_id}/controls/{self.control_id}/on"
        await mqtt.async_publish(self.hass, command_topic, payload)


class ExternalMQTTSensor(ExternalMQTTEntity):
    """Sensor entity."""

    @property
    def state(self):
        return self._state


class ExternalMQTTButton(ExternalMQTTEntity):
    """Button Entity."""

    async def async_press(self, **kwargs):
        """Press button."""
        command_topic = f"device/{self.device_id}/controls/{self.control_id}/on"
        await mqtt.async_publish(self.hass, command_topic, "1")


def create_entity(
    hass: HomeAssistant,
    device_id: str,
    control_id: str,
    device_info: DeviceInfo,
    entity_type: str,
    readonly: bool,
):
    """Fabric for create entity."""
    entity_classes = {
        "switch": ExternalMQTTSwitch,
        "value": ExternalMQTTSensor,
        "pushbutton": ExternalMQTTButton,
    }

    entity_class = entity_classes.get(entity_type)
    if entity_class:
        return entity_class(hass, device_id, control_id, device_info)

    return None
