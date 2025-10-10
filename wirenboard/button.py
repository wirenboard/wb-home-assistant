"""Platform for button integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entities.button import WirenBoardButton
from .entity_helpers import async_setup_platform_entries


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wiren Board buttons from a config entry."""
    await async_setup_platform_entries(
        hass, config_entry, async_add_entities, "button", WirenBoardButton
    )
