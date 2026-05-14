"""Diagnostics support for Wiren Board integration."""

from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    device_manager = entry_data.get("device_manager")
    mqtt_client = entry_data.get("mqtt_client")

    devices_info = {}
    if device_manager:
        for device_id, device_info in device_manager.get_all_devices().items():
            devices_info[device_id] = {
                "device_type": device_info.get("device_type"),
                "readonly": device_info.get("readonly"),
                "enum_options": len(device_info.get("enum", [])) if device_info.get("enum") else 0,
                "description": device_info.get("description"),
            }

    return {
        "config_entry": {
            "host": config_entry.data.get("host"),
            "port": config_entry.data.get("port"),
            "use_ssl": config_entry.data.get("use_ssl"),
            "topic_prefix": config_entry.data.get("topic_prefix"),
        },
        "mqtt_client": {
            "connected": mqtt_client.connected if mqtt_client else False,
        },
        "devices": devices_info,
    }
