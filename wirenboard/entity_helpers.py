"""Helpers for entity platform setup."""

import logging
from typing import Any, Dict, Type

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_TYPE_MAPPING, DOMAIN, SIGNAL_DEVICE_DISCOVERED

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
        # if not _is_platform_match(device_info["device_type"], platform):
        if not _is_platform_match(device_info, platform):
            return

        try:
            mqtt_client = entry_data["mqtt_client"]
            if device_info["control_id"].lower() == "Air Quality (VOC)".lower():
                device_info["unit"] = "ppb"
            elif device_info["control_id"].lower() == "Illuminance".lower():
                device_info["unit"] = "lux"
            elif device_info["control_id"].lower() == "CO2".lower():
                device_info["unit"] = "ppm"
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


def _is_platform_match(device_info: Dict[str, Any], platform: str) -> bool:
    """Check if device type matches platform with readonly consideration."""
    device_type = device_info["device_type"]
    readonly = device_info.get("readonly", False)
    control_id = device_info.get("control_id", "")

    # Skip child controls of RGB lights (Hue, Saturation, Brightness)
    # These are created by Wiren Board as separate controls but should not be separate entities
    if _is_rgb_child_control(control_id):
        logger.debug(
            "Skipping RGB child control: %s:%s",
            device_info["device_id"],
            control_id,
        )
        return False

    target_platform = DEVICE_TYPE_MAPPING.get((device_type, readonly))

    logger.debug(
        "Checking device %s:%s (readonly=%s) -> %s vs %s",
        device_info["device_id"],
        device_info["control_id"],
        readonly,
        target_platform,
        platform,
    )

    return target_platform == platform


def _is_rgb_child_control(control_id: str) -> bool:
    """Check if control is a child of an RGB control."""
    control_lower = control_id.lower()
    # Check if control ends with common RGB child control suffixes
    rgb_suffixes = [
        " hue",
        " saturation", 
        " brightness",
        " bright",
        " hue changing",  # For specific controls
    ]
    
    for suffix in rgb_suffixes:
        if control_lower.endswith(suffix):
            # Additional check: control name should have a parent part
            # e.g., "RGB Strip Hue" -> parent would be "RGB Strip"
            if len(control_id) > len(suffix):
                return True
    
    # Also check for controls that contain these keywords in the middle
    # e.g., "Channel 4 Brightness" when "Channel 4" is RGB
    if any(keyword in control_lower for keyword in [" hue ", " saturation ", " brightness ", " bright "]):
        return True
    
    return False
