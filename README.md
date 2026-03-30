# Maico KWL – Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![Version](https://img.shields.io/badge/version-1.0.0-blue)
![HA Compatible](https://img.shields.io/badge/Home%20Assistant-2024.1+-green)

Unofficial Home Assistant custom integration for the **Maico WS 320 KBET** ventilation unit (controlled residential ventilation) via **Modbus TCP**.

> Compatible with all Maico WS series devices that support Modbus TCP connectivity.

---

## Features

### Sensors (read-only)

| Sensor | Unit | Description |
|---|---|---|
| Current ventilation level | – | Off / Humidity protection / Reduced / Nominal / Intensive |
| Supply fan speed | RPM | |
| Exhaust fan speed | RPM | |
| Supply air flow rate | m³/h | |
| Exhaust air flow rate | m³/h | |
| Device filter remaining life | d | Days until filter replacement |
| Outdoor filter remaining life | d | |
| Room filter remaining life | d | |
| Room temperature | °C | |
| Room temperature (external) | °C | |
| Outdoor air temperature (before EWT) | °C | |
| Air inlet temperature | °C | Outdoor air cold side |
| Supply air temperature | °C | Fresh air after heat exchanger |
| Exhaust air temperature | °C | Room air warm side |
| Discharge air temperature | °C | |
| Exhaust air relative humidity | % | |
| Relative humidity sensor 1–4 | % | |
| CO₂ sensor 1–4 | ppm | |
| VOC sensor 1–4 | ppm | |
| Operating hours (per level + total) | h | 32-bit counter |
| **Heat recovery** | % | Calculated efficiency η |

### Binary Sensors

| Sensor | Description |
|---|---|
| Supply fan running | |
| Exhaust fan running | |
| Bypass open | Summer operation |
| Heater active | Frost protection |

### Controls

| Entity | Type | Description |
|---|---|---|
| Operating mode | Select | Off / Manual / Auto-Time / Auto-Sensor / Eco-Supply / Eco-Exhaust |
| Ventilation level (setpoint) | Select | Off / Humidity protection / Reduced / Nominal / Intensive |
| Season | Select | Winter / Summer |
| Room temperature source | Select | Comfort panel / External / Internal / Bus |
| Language | Select | German / English / French / Italian |
| Supply air target temperature | Number | Target temperature in °C |
| Bus room temperature | Number | Room temperature for bus transmission (°C) |
| Bus relative humidity | Number | Humidity value for bus transmission (%) |
| Bus CO₂/air quality | Number | CO₂ value for bus transmission (ppm) |
| Burst ventilation | Switch | Short-term intensive ventilation |
| Off lock | Switch | Prevents the device from being turned off |
| Control panel lock | Switch | Lock the control panel |
| Confirm filter change | Button | Reset filter counter |
| Reset error | Button | Acknowledge active errors |

---

## Installation

### Prerequisites

- Home Assistant 2024.1 or newer
- Maico WS 320 KBET (or compatible device) reachable on the local network
- Modbus TCP enabled on the device (default port: 502, Modbus address: 10)

### Manual Installation

1. Download or clone this repository as ZIP.
2. Copy the `custom_components/maico_kwl/` folder into the `<config>/custom_components/` directory of your Home Assistant installation.
3. Restart Home Assistant.

### Installation via HACS (Custom Repository)

1. Open HACS → **Integrations** → three dots in the top right → **Custom repositories**.
2. Paste this repository's URL, category: **Integration**.
3. Search for and install the integration, then restart HA.

---

## Configuration

1. In Home Assistant: **Settings → Devices & Services → Add Integration**.
2. Search for "Maico KWL".
3. Enter connection details:

| Parameter | Default | Description |
|---|---|---|
| IP address / Host | – | IP of the ventilation unit |
| Port | 502 | Modbus TCP port |
| Modbus address (Slave ID) | 10 | Device address |
| Update interval | 30 s | Polling rate |

---

## Technical Details

### Modbus Register Blocks

The integration cyclically reads the following register ranges:

| Range | Registers | Content |
|---|---|---|
| Basic settings | 100–109 | Configuration, language, temperature source |
| Ventilation settings | 150–159 | Setpoints |
| Temperature settings | 300–302 | Target temperatures |
| Error messages | 401–404 | Active errors |
| Operating settings | 550–554 | Operating mode, season, level |
| Ventilation status | 650–657 | Actual values: level, speed, flow rate, filter |
| Temperatures | 700–706 | Current temperature readings |
| Sensor data | 750–762 | Humidity (750–754), CO₂ (755–758), VOC (759–762) |
| Switching states | 800–805 | Binary states |
| Operating hours | 850–859 | 32-bit counters (high/low word) |
| Filter monitoring | 900 | Filter status |

### Calculated Sensor – Heat Recovery

```
η = (T_supply − T_outdoor) / (T_exhaust − T_outdoor) × 100 %
```

Not calculated when the temperature difference is < 0.5 K.

### Modbus Specifics

- Temperatures: raw value ÷ 10 (signed, 16-bit two's complement)
- Operating hours: 32-bit (high word + low word in consecutive registers)
- Writing negative values: `value & 0xFFFF`
- Write-only bus registers: 707 (room temp), 763 (rel. humidity), 764 (CO₂/air quality)

---

## Supported Devices

Tested with:
- **Maico WS 320 KBET**

Potentially compatible with other Maico WS series devices, provided the Modbus registers match.

---

## License

This project is licensed under the [MIT License](LICENSE). It is a private, unofficial project and is not affiliated with Maico Ventilatoren GmbH & Co. KG.
