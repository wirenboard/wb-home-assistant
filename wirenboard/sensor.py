"""Platform for sensor integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entities.sensor import WirenBoardSensor
from .entity_helpers import async_setup_platform_entries


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wiren Board sensors from a config entry."""
    await async_setup_platform_entries(
        hass, config_entry, async_add_entities, "sensor", WirenBoardSensor
    )
