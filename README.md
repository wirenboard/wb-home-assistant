# Home Assistant custom component for Wiren Board devices #


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
