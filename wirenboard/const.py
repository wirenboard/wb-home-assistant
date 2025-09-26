"""Constants for Wiren Board integration."""

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)

DOMAIN = "wirenboard"

# Platforms
PLATFORMS = [
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.LIGHT,
    Platform.BINARY_SENSOR,
]

# MQTT topics
TOPIC_STATE = "/devices/{device}/controls/{control}"
TOPIC_COMMAND = "/devices/{device}/controls/{control}/on"
TOPIC_META = "/devices/{device}/controls/{control}/meta/{meta_key}"

# Meta keys
META_TYPE = "type"
META_READONLY = "readonly"
META_UNIT = "unit"
META_MAX = "max"
META_MIN = "min"
META_DESCRIPTION = "description"

# Configuration
CONF_TOPIC_PREFIX = "topic_prefix"
CONF_DISCOVERY_TOPIC = "discovery_topic"
CONF_USE_SSL = "use_ssl"
CONF_VERIFY_SSL = "verify_ssl"
CONF_KEEPALIVE = "keepalive"
CONF_CLIENT_ID = "client_id"

# Default values
DEFAULT_TOPIC_PREFIX = "/devices"
DEFAULT_DISCOVERY_TOPIC = "/devices/+/controls/+/meta/+"
DEFAULT_PORT = 1883
DEFAULT_CLIENT_ID = "homeassistant_wirenboard"
DEFAULT_KEEPALIVE = 60
DEFAULT_USE_SSL = False
DEFAULT_VERIFY_SSL = True

# Signals
SIGNAL_DEVICE_DISCOVERED = "wirenboard_device_discovered"
