# Home Assistant custom component for Wiren Board devices #


## Requirements ##

Home Assistant **2025.6 or newer**. The integration maps reactive energy controls
(`kvarh`) to `SensorDeviceClass.REACTIVE_ENERGY`, which was added in that release.

## Installation ##

The integration is installed as a custom Home Assistant component. It is assumed that Home Assistant is installed according to the [instructions](https://wiki.wirenboard.com/wiki/Home_Assistant).

*   Copy the `wirenboard` folder to the `/mnt/data/.docker-compose/home-assistant/config/home-assistant/custom_components/` directory.
*   Open the Home Assistant web interface.
*   Restart Home Assistant: navigate to **Developer Tools** -> **Restart**.
*   Add the integration: Go to **Settings** -> **Devices & Services** -> **Add Integration** and select `wirenboard`.
*   The Host/Port fields are pre-filled with default values for connecting to the controller. Change them only if necessary.


## Mapping devices ##
| WirenBoard | -> | HomeAssistant|
| :---: | :---: |  :---: |
| switch || switch |
| value || sensor |
| pushbutton|| button |
| range|| number |
| rgb|| light |
| alarm|| binary_sensor |
| text|| text |

### Dimmable channels (WB-LED, WB-MDM3) ###

When a writable `switch` control has a paired brightness `range` control on
the same device — either `<name>` + `<name> Brightness` (as in WB-LED white
channels) or `KN` + `Channel N` (as in WB-MDM3) — they are surfaced as a
single dimmable `light` entity. The paired range does **not** appear as a
separate `number`; its value is exposed as the light's brightness.

Read-only text controls with an `enum` remain a `sensor`; writable ones
become a `select`. Controls that belong to the RGB Palette group
(`RGB Strip`, `RGB Strip Hue/Saturation/Brightness`) are hidden — the RGB
light owns them.
