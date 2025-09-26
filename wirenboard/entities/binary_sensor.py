"""Binary sensor entity for Wiren Board."""

from homeassistant.components.binary_sensor import BinarySensorEntity

from .base import WirenBoardEntity


class WirenBoardBinarySensor(WirenBoardEntity, BinarySensorEntity):
    """Representation of a Wiren Board binary sensor."""

    def _handle_state_update(self, payload: str):
        """Handle state update for binary sensor."""
        self._state = payload

    @property
    def is_on(self) -> bool:
        return self._state == "1"
