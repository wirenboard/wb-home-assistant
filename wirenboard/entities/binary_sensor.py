"""Binary sensor entity for Wiren Board."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .base import WirenBoardEntity


class WirenBoardBinarySensor(WirenBoardEntity, BinarySensorEntity):
    """Representation of a Wiren Board binary sensor."""

    def __init__(self, device_info, mqtt_client):
        """Initialize binary sensor."""
        super().__init__(device_info, mqtt_client)

        # alarm type → PROBLEM device class
        if device_info.get("device_type") == "alarm":
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    def _handle_state_update(self, payload: str):
        """Handle state update for binary sensor."""
        self._state = payload

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if self._state is None:
            return None
        return self._state == "1"
