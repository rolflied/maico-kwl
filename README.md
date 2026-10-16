# Maico KWL – Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![Version](https://img.shields.io/badge/version-0.2.1-blue)
![HA Compatible](https://img.shields.io/badge/Home%20Assistant-2026.9+-green)

Unofficial Home Assistant custom integration for **Maico WS/WR ventilation units** (controlled
residential ventilation, e.g. WS 320 KBET) via **Modbus TCP**.

The integration uses the shared Modbus connections Home Assistant introduced in **2026.9**
(`modbus.async_get_unit`). The unit accepts only one Modbus TCP connection; all integrations that
use the shared API for the same unit share that one connection.

---

## Entities

All register addresses refer to the Maico document *KWL Steuerung Modbus Parameterbeschreibung
RTU/TCP*. Entities marked *optional* belong to parts that are not fitted to every unit; they start
**enabled only if the unit reports a value for them during setup** (otherwise disabled, you can
enable them in the entity settings).

### Fan

| Entity | Registers | Description |
|---|---|---|
| Ventilation (`fan`) | 550, 554, 650 | Speed = ventilation level 1–4 (humidity protection, reduced, nominal, intensive; 25/50/75/100 %). Setting a speed switches to *manual*. Preset modes = operating modes. *Turn off* sets the operating mode *off*, *turn on* restores the last mode. |

### Sensors

| Entity | Register | Unit | Notes |
|---|---|---|---|
| Current ventilation level | 650 | enum | |
| Supply / exhaust fan speed | 651, 652 | rpm | |
| Supply / exhaust airflow | 653, 654 | m³/h | |
| Device / outdoor / room filter remaining | 655–657 | d | outdoor/room *optional* |
| Room temperature | 700 | °C | |
| External room temperature | 701 | °C | enabled if room temperature source = external |
| Outdoor air before ground heat exchanger | 702 | °C | ZP1, disabled by default |
| Air intake / supply / extract / exhaust air temperature | 703–706 | °C | |
| Extract air humidity | 750 | % | |
| Humidity sensor 1–4 | 751–754 | % | *optional* |
| CO₂ sensor 1–4 | 755–758 | ppm | *optional* |
| VOC sensor 1–4 | 759–762 | ppm | *optional* |
| EnOcean CO₂ / humidity / VOC ID0–7 | 350–373 | ppm / % | *optional* |
| Active faults | 401/402 | count | attributes `active` (decoded bits) and `code` |
| Active notices | 403/404 | count | attributes `active` and `code` |
| Brine pump, three-way damper, zone damper | 806–808 | enum | ZP1, disabled by default |
| Operating hours humidity protection / reduced / nominal / intensive / total | 850–859 | h | 32 bit |
| Operating hours reheating relay, brine pump, dampers, switch contact | 860–869 | h | ZP1, disabled by default |
| Heat recovery efficiency | 703–705 | % | calculated, see below |
| Heat recovery power | 653, 703, 704 | W | calculated, see below |
| Clock deviation | 100–105 | s | unit clock minus HA clock, disabled by default |

### Binary sensors

| Entity | Register | Notes |
|---|---|---|
| Supply fan / exhaust fan | 800, 801 | running |
| Summer bypass | 802 | open |
| PTC heater | 803 | |
| Base board switch contact | 804 | diagnostic |
| Reheating relay | 805 | ZP1, disabled by default |
| Fault | 401/402 | problem, on while any fault bit is set |
| Device / outdoor / room filter change due | 403/404 bit 9–11 | problem |
| Frost protection | 403/404 bit 6 | |
| Humidity protection | 403/404 bit 13 | |

### Controls

| Entity | Type | Register | Notes |
|---|---|---|---|
| Operating mode | select | 550 | off, manual, auto (time), auto (sensor), eco supply air, eco exhaust air |
| Ventilation level | select | 554 | only followed in *manual* mode |
| Season | select | 552 | winter / summer |
| Room temperature source | select | 109 | comfort control panel, external, internal, bus |
| Device language | select | 108 | |
| Room temperature setpoint | number | 553 | 18–25 °C, 0.5 °C steps |
| Room temperature offset | number | 300 | −3…3 °C |
| Minimum supply air temperature (cooling) | number | 301 | 8–29 °C |
| Maximum room temperature | number | 302 | 18–30 °C |
| Airflow reduced / nominal / intensive | number | 154–156 | 80–300 m³/h (the unit type may allow less) |
| Ventilation level duration | number | 153 | 5–90 min |
| Filter interval device / outdoor / room | number | 150–152 | months |
| Allowed filter pressure difference | number | 900 | 10–200 % |
| Room temperature / humidity / air quality (bus) | number | 707, 763, 764 | write-only, see *Bus inputs* |
| Boost ventilation | switch | 551 | |
| Lock off level | switch | 106 | |
| Lock control panel | switch | 107 | |
| Device / outdoor / room filter changed | button | 157–159 | restarts the filter interval |
| Reset faults | button | 405 | |
| Sync clock | button | 100–105 | writes HA's local time in one request |

### Repairs and diagnostics

- A **repair issue** appears while the unit reports a fault (listing the decoded fault bits) and
  while it asks for a filter change. Both disappear on their own once the unit stops reporting them.
- **Download diagnostics** on the device page returns all raw registers, the decoded fault and
  notice bits, the unit clock and the register blocks the unit does not support.

---

## Bus inputs

Registers 707 (room temperature), 763 (humidity) and 764 (air quality, ppm) let Home Assistant
supply sensor values to the unit. The unit uses them only for **10 minutes** after the last write.

- Set a value with the *(bus)* number entities, **or**
- choose source entities under **Settings → Devices & services → Maico KWL → Configure**. The value
  is sent on every change; °F and ppb are converted.

Every known value is written again every **5 minutes**. The room temperature is only used by the
unit if *Room temperature source* is set to *Bus*.

---

## Installation

### Requirements

- Home Assistant **2026.9** or newer.
- Maico unit with Modbus TCP enabled (firmware **V1.1.1** or newer), default port 502,
  default Modbus address 10.
- No other program connected to the unit's Modbus TCP port (it accepts only one connection).

### HACS (custom repository)

1. HACS → three dots → **Custom repositories** → add this repository, category **Integration**.
2. Install *Maico KWL* and restart Home Assistant.

### Manual

Copy `custom_components/maico_kwl/` into `<config>/custom_components/` and restart Home Assistant.

## Configuration

**Settings → Devices & services → Add integration → Maico KWL**, then enter host, port and Modbus
address. Setup reads a few registers and refuses devices whose values do not match a Maico KWL.

- **Reconfigure** (menu of the entry) changes host, port and Modbus address.
- **Configure** changes the host/IP address (the unit is tested first), the update interval (5–300 s, default 30 s) and sets the bus input sources.

---

## Technical notes

### Modbus

- All registers are holding registers, read with FC 03 in 12 blocks per poll. A block the unit
  rejects as *illegal address/function* is skipped until the next reload; its entities are
  unavailable.
- **Writes use FC 16 (Write Multiple Registers).** According to the Maico documentation this is the
  only write function the unit accepts over TCP (FC 06 is for RTU only).
- 32-bit values are High-Word first.
- Before anything is written, every poll checks that the identifying registers (108, 109, 550–554)
  hold values a Maico KWL can have. A foreign device at the configured address is never written to.

### Deviations from the Maico documentation

| Registers | Documentation | Integration | Why |
|---|---|---|---|
| 750–754 humidity | ×10 | unscaled % | live units report e.g. 54 for 54 % |
| 755–762 CO₂/VOC | ×10 | unscaled ppm | live unit reports e.g. 548 ppm |
| 350–373 EnOcean | ×10 / 0–1000 | unscaled | by analogy, not checked on a unit |
| 301 min. supply temperature | "step 1 = 0.1 °C" | whole °C | range 8–29, live units report e.g. 14 |
| 401–404 bit fields | "Bitfeld" only | decoded | bit meanings from the Maico Geniovent list, which uses the same control |

### Calculated values

- **Heat recovery efficiency** η = (T<sub>supply</sub> − T<sub>intake</sub>) /
  (T<sub>extract</sub> − T<sub>intake</sub>) × 100 %, clamped to 0–100 %. Not shown while the
  summer bypass is open or the extract/intake difference is below 3 K.
- **Heat recovery power** P = 0.335 Wh/(m³·K) × supply airflow × (T<sub>supply</sub> −
  T<sub>intake</sub>); negative while the unit cools the supply air. Not shown while the bypass is
  open. For energy (kWh) use an *Integral* helper on this sensor.

---

## Upgrading from 0.1.x

- Existing entities are migrated to new unique IDs automatically: **entity IDs, names you set and
  history stay**. The update interval moves from the entry data to the options.
- **Select and enum states are now language-independent slugs** (e.g. `manual`, `nominal`,
  `summer`) and are translated in the UI. Automations or templates that compare against the old
  German texts (`Manuell`, `Nenn`, `Sommer`, …) must be changed to the slugs.
- Fan speeds now use the unit `rpm` (was `U/min`); Home Assistant may ask once how to handle the
  statistics of these two sensors.
- New: fan entity, fault/notice decoding, repair issues, filter binary sensors, EnOcean and ZP1
  registers, operating hours 860–869, heat recovery power, clock sync, bus input feeding, options
  and reconfigure flows, diagnostics.

## Icon

The integration ships its own icon (`custom_components/maico_kwl/brand/`), shown by Home Assistant
2026.9+ on the integrations page and in HACS. It is a neutral cross-flow heat exchanger symbol, not
the Maico logo.

## Development

```bash
pip install -r requirements_test.txt ruff
ruff check custom_components tests && ruff format --check custom_components tests
pytest
```

The tests run against Home Assistant with an in-memory Modbus unit
(`modbus_connection.mock`).

## Supported devices

Tested with the **Maico WS 320 KBET**. Other Maico WS/WR units with the same control and Modbus
TCP should work.
