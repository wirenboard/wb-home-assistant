"""Diagnostics for Wiren Board integration."""

from typing import Any, Dict
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    if DOMAIN not in hass.data or config_entry.entry_id not in hass.data[DOMAIN]:
        return {"error": "Integration not initialized"}

    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    device_manager = entry_data.get("device_manager")
    mqtt_client = entry_data.get("mqtt_client")

    devices = {}
    if device_manager:
        for device_id, device_info in device_manager.get_all_devices().items():
            devices[device_id] = {
                "device_id": device_info.get("device_id"),
                "control_id": device_info.get("control_id"),
                "device_type": device_info.get("device_type"),
                "readonly": device_info.get("readonly"),
                "has_enum": bool(device_info.get("enum")),
                "enum_options_count": len(device_info.get("enum", [])),
            }

    mqtt_status = "disconnected"
    if mqtt_client and mqtt_client._client:
        mqtt_status = "connected" if mqtt_client._client.is_connected() else "disconnected"

    return {
        "config_entry": {
            "entry_id": config_entry.entry_id,
            "title": config_entry.title,
            "data": {
                "host": config_entry.data.get("host"),
                "port": config_entry.data.get("port"),
                "topic_prefix": config_entry.data.get("topic_prefix", "/devices"),
            },
        },
        "mqtt_client": {
            "status": mqtt_status,
            "subscribed_topics_count": len(mqtt_client._subscriptions) if mqtt_client else 0,
        },
        "discovered_devices": {
            "total": len(devices),
            "devices": devices,
        },
    }
