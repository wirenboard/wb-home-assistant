# Home Assistant custom component for Wiren Board devices #

## Installation ##

 * Copy folder *wirenboard* to */config/custom_components/*
 * Open web interface HA
 * Developer tools -> restart
 * Settings -> Device&Services -> Add Integration select *wirenboard*
 * Add Host/Port of your wb controller


## Mapping devices ##
| WirenBoard | -> | HomeAssistant|
| :---: | :---: |  :---: |
| switch || switch |
| value || sensor |
| pushbutton|| button |
| range|| number |
| rgb|| light |
| alarm|| binary_sensor |
