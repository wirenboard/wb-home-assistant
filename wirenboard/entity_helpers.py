"""Helpers for entity platform setup."""

import logging
from typing import Any, Dict, Type

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_TYPE_MAPPING, DOMAIN, SIGNAL_DEVICE_DISCOVERED

logger = logging.getLogger(__name__)


def _unique_id_for(device_id: str, control_id: str) -> str:
    """Match WirenBoardEntity's unique_id convention."""
    return f"wirenboard_{device_id}_{control_id}"


@callback
def _migrate_orphan_pre_light(
    hass: HomeAssistant, device_info: Dict[str, Any]
) -> None:
    """Remove entity_registry rows that belong to the previous platform layout.

    Before this feature, a WB-LED/WB-MDM3 dimmable output was surfaced as
    ``switch.wirenboard_<device>_<control>`` plus
    ``number.wirenboard_<device>_<control>_brightness``. Now the same output is
    published as a single ``light.wirenboard_<device>_<control>``. HA's entity
    registry keys on ``(integration, domain, unique_id)``, so the switch and
    number rows would persist as orphans and break automations that still
    reference them. Clear them before the Light is registered.
    """
    registry = er.async_get(hass)
    device_id = device_info["device_id"]
    control_id = device_info["control_id"]
    brightness_control_id = device_info.get("brightness_control_id")

    for domain in ("switch", "number", "binary_sensor"):
        old = registry.async_get_entity_id(
            domain, DOMAIN, _unique_id_for(device_id, control_id)
        )
        if old:
            logger.info("Removing orphan %s → light for %s", old, control_id)
            registry.async_remove(old)

    if brightness_control_id:
        for domain in ("number", "sensor"):
            old = registry.async_get_entity_id(
                domain,
                DOMAIN,
                _unique_id_for(device_id, brightness_control_id),
            )
            if old:
                logger.info(
                    "Removing orphan %s (brightness peer folded into light)", old
                )
                registry.async_remove(old)


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
            if (
                platform == "light"
                and device_info.get("brightness_control_id")
            ):
                _migrate_orphan_pre_light(hass, device_info)

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
    enum_options = device_info.get("enum")

    # Skip child controls of an RGB Palette (they duplicate the palette value).
    if _is_rgb_child_control(control_id):
        logger.debug(
            "Skipping RGB child control: %s:%s",
            device_info["device_id"],
            control_id,
        )
        return False

    # A range control that pairs with a sibling switch (e.g. "Channel 4 Brightness"
    # next to "Channel 4") is not surfaced on its own — it is folded into the
    # brightness of the light entity created for the switch.
    if device_info.get("is_brightness_child"):
        return False

    # A writable switch that has a "<name> Brightness" range peer becomes a
    # single dimmable Light instead of a bare Switch.
    if (
        device_type == "switch"
        and not readonly
        and device_info.get("brightness_control_id")
    ):
        return platform == "light"

    # Text controls with enum options become SELECT entities only when writable.
    # Read-only enum text controls must remain SENSOR entities to avoid exposing
    # a writable entity for a read-only WB control.
    if enum_options and device_type == "text":
        return platform == ("sensor" if readonly else "select")

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
    """Check if control is a slave of an "RGB Palette"-style control.

    The dimmer publishes duplicated Hue/Saturation/Brightness range controls
    prefixed with "RGB " alongside the combined RGB Palette; those should
    stay hidden. Other Hue/Brightness controls (e.g. "Channel 4 Brightness",
    "Hue Changing") are NOT children and must not be filtered out here.
    """
    lower = control_id.lower()
    if not lower.startswith("rgb "):
        return False
    return (
        lower.endswith(" hue")
        or lower.endswith(" saturation")
        or lower.endswith(" brightness")
    )
