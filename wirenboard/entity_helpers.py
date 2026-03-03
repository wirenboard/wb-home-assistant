"""Helpers for entity platform setup."""

import logging
from typing import Any, Dict, Type

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_TYPE_MAPPING, DOMAIN, SIGNAL_DEVICE_DISCOVERED

logger = logging.getLogger(__name__)


async def async_setup_platform_entries(
    hass: HomeAssistant,
    config_entry,
    async_add_entities: AddEntitiesCallback,
    platform: str,
    entity_class: Type,
) -> None:
    """Set up platform entries."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    device_manager = entry_data["device_manager"]
    mqtt_client = entry_data["mqtt_client"]

    @callback
    def async_add_entity(device_info: Dict[str, Any]):
        """Add entity when discovered."""
        if not _is_platform_match(device_info, platform):
            return

        try:
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
    if _is_rgb_child_control(control_id):
        logger.debug(
            "Skipping RGB child control: %s:%s",
            device_info["device_id"],
            control_id,
        )
        return False

    target_platform = DEVICE_TYPE_MAPPING.get((device_type, readonly))

    if target_platform is None and (device_type, readonly) not in DEVICE_TYPE_MAPPING:
        # Unknown device type — log warning, skip
        logger.warning(
            "Unknown device type '%s' (readonly=%s) for %s:%s, skipping",
            device_type,
            readonly,
            device_info["device_id"],
            control_id,
        )
        return False

    return target_platform == platform


def _is_rgb_child_control(control_id: str) -> bool:
    """Check if control is a child of an RGB control."""
    control_lower = control_id.lower()
    rgb_suffixes = [
        " hue",
        " saturation",
        " brightness",
        " bright",
        " hue changing",
    ]

    for suffix in rgb_suffixes:
        if control_lower.endswith(suffix) and len(control_id) > len(suffix):
            return True

    if any(
        keyword in control_lower
        for keyword in [" hue ", " saturation ", " brightness ", " bright "]
    ):
        return True

    return False
