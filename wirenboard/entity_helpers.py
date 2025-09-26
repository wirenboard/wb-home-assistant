"""Helpers for entity platform setup."""

import logging
from typing import Any, Dict, Type

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_DEVICE_DISCOVERED

logger = logging.getLogger(__name__)


async def async_setup_platform_entries(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    platform: str,
    entity_class: Type,
) -> None:
    """Set up platform entries."""
    if DOMAIN not in hass.data or config_entry.entry_id not in hass.data[DOMAIN]:
        logger.error("Wiren Board not initialized for entry %s", config_entry.entry_id)
        return

    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    device_manager = entry_data["device_manager"]

    @callback
    def async_add_entity(device_info: Dict[str, Any]):
        """Add entity when discovered."""
        if not _is_platform_match(device_info["device_type"], platform):
            return

        try:
            mqtt_client = entry_data["mqtt_client"]
            entity = entity_class(device_info, mqtt_client)
            async_add_entities([entity])
            logger.info("Added %s entity: %s", platform, entity.name)
        except Exception as ex:
            logger.error(
                "Error creating entity for device %s: %s",
                device_info.get("device_id", "unknown"),
                ex,
            )

    # Add existing devices
    for device_info in device_manager.get_all_devices().values():
        async_add_entity(device_info)

    # Listen for new devices
    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICE_DISCOVERED, async_add_entity)
    )

    logger.info("Setup complete for %s platform", platform)


def _is_platform_match(device_type: str, platform: str) -> bool:
    """Check if device type matches platform."""
    mapping = {
        "switch": "switch",
        "value": "sensor",
        "pushbutton": "button",
        "range": "number",
        "rgb": "light",
        "alarm": "binary_sensor",
    }
    return mapping.get(device_type) == platform
