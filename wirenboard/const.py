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
    Platform.TEXT,
]

# MQTT topics
TOPIC_STATE = "/devices/{device}/controls/{control}"
TOPIC_COMMAND = "/devices/{device}/controls/{control}/on"
TOPIC_META = "/devices/{device}/controls/{control}/meta/{meta_key}"
TOPIC_META_ERROR = "/devices/{device}/controls/{control}/meta/error"

# Meta keys
META_TYPE = "type"
META_ORDER = "order"
META_READONLY = "readonly"
META_UNIT = "units"
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

# Extended device type mapping with readonly handling
# (device_type, readonly) -> Platform | None
DEVICE_TYPE_MAPPING = {
    # Core types
    ("switch", True): Platform.BINARY_SENSOR,
    ("switch", False): Platform.SWITCH,
    ("value", True): Platform.SENSOR,
    ("value", False): Platform.SENSOR,
    ("pushbutton", True): None,  # Skip readonly buttons
    ("pushbutton", False): Platform.BUTTON,
    ("range", True): Platform.SENSOR,
    ("range", False): Platform.NUMBER,
    ("rgb", True): Platform.SENSOR,
    ("rgb", False): Platform.LIGHT,
    ("text", True): Platform.SENSOR,
    ("text", False): Platform.TEXT,
    ("alarm", True): Platform.BINARY_SENSOR,
    ("alarm", False): Platform.BINARY_SENSOR,
    # Deprecated but active WB types (all map to SENSOR)
    ("temperature", True): Platform.SENSOR,
    ("temperature", False): Platform.SENSOR,
    ("rel_humidity", True): Platform.SENSOR,
    ("rel_humidity", False): Platform.SENSOR,
    ("power", True): Platform.SENSOR,
    ("power", False): Platform.SENSOR,
    ("power_consumption", True): Platform.SENSOR,
    ("power_consumption", False): Platform.SENSOR,
    ("voltage", True): Platform.SENSOR,
    ("voltage", False): Platform.SENSOR,
    ("current", True): Platform.SENSOR,
    ("current", False): Platform.SENSOR,
    ("lux", True): Platform.SENSOR,
    ("lux", False): Platform.SENSOR,
    ("ppm", True): Platform.SENSOR,
    ("ppm", False): Platform.SENSOR,
    ("ppb", True): Platform.SENSOR,
    ("ppb", False): Platform.SENSOR,
    ("concentration", True): Platform.SENSOR,
    ("concentration", False): Platform.SENSOR,
    ("sound_level", True): Platform.SENSOR,
    ("sound_level", False): Platform.SENSOR,
    ("atmospheric_pressure", True): Platform.SENSOR,
    ("atmospheric_pressure", False): Platform.SENSOR,
    ("pressure", True): Platform.SENSOR,
    ("pressure", False): Platform.SENSOR,
    ("rainfall", True): Platform.SENSOR,
    ("rainfall", False): Platform.SENSOR,
    ("wind_speed", True): Platform.SENSOR,
    ("wind_speed", False): Platform.SENSOR,
    ("water_flow", True): Platform.SENSOR,
    ("water_flow", False): Platform.SENSOR,
    ("water_consumption", True): Platform.SENSOR,
    ("water_consumption", False): Platform.SENSOR,
    ("resistance", True): Platform.SENSOR,
    ("resistance", False): Platform.SENSOR,
    ("heat_power", True): Platform.SENSOR,
    ("heat_power", False): Platform.SENSOR,
    ("heat_energy", True): Platform.SENSOR,
    ("heat_energy", False): Platform.SENSOR,
}

# Signals
SIGNAL_DEVICE_DISCOVERED = "wirenboard_device_discovered"
