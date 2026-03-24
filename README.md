# Maico KWL – Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![Version](https://img.shields.io/badge/version-1.0.0-blue)
![HA Compatible](https://img.shields.io/badge/Home%20Assistant-2024.1+-green)

Inoffizielle Home Assistant Custom Integration für die **Maico WS 320 KBET** Lüftungsanlage (Kontrollierte Wohnraumlüftung) via **Modbus TCP**.

> Kompatibel mit allen Maico-Geräten der WS-Serie, die über Modbus TCP angebunden werden können.

---

## Funktionsumfang

### Sensoren (read-only)

| Sensor | Einheit | Beschreibung |
|---|---|---|
| Aktuelle Lüftungsstufe | – | Aus / Feuchteschutz / Reduziert / Nenn / Intensiv |
| Drehzahl Zuluftventilator | U/min | |
| Drehzahl Abluftventilator | U/min | |
| Volumenstrom Zuluft | m³/h | |
| Volumenstrom Abluft | m³/h | |
| Restlaufzeit Gerätefilter | d | Tage bis Filterwechsel |
| Restlaufzeit Außenfilter | d | |
| Restlaufzeit Raumfilter | d | |
| Temperatur Raum | °C | |
| Temperatur Raum Extern | °C | |
| Temperatur Außenluft vor EWT | °C | |
| Temperatur Lufteintritt | °C | Außenluft Kaltseite |
| Temperatur Zuluft | °C | Frischluft nach Wärmetauscher |
| Temperatur Abluft | °C | Raumluft Warmseite |
| Temperatur Fortluft | °C | |
| Relative Feuchte Abluft | % | |
| Relative Feuchte Sensor 1–4 | % | |
| CO₂ Sensor 1–4 | ppm | |
| VOC Sensor 1–4 | ppm | |
| Betriebsstunden (je Stufe + Gesamt) | h | 32-Bit-Zähler |
| **Wärmerückgewinnung** | % | Berechneter Wirkungsgrad η |

### Binärsensoren

| Sensor | Beschreibung |
|---|---|
| Zuluftventilator läuft | |
| Abluftventilator läuft | |
| Bypass offen | Sommerbetrieb |
| Heizregister aktiv | Frostschutz |

### Steuerelemente

| Entität | Typ | Beschreibung |
|---|---|---|
| Betriebsart | Select | Aus / Manuell / Auto-Zeit / Auto-Sensor / Eco-Zuluft / Eco-Abluft |
| Lüftungsstufe (Sollwert) | Select | Aus / Feuchteschutz / Reduziert / Nenn / Intensiv |
| Jahreszeit | Select | Winter / Sommer |
| Raumtemperaturquelle | Select | Komfort-BDE / Extern / Intern / Bus |
| Sprache | Select | Deutsch / Englisch / Französisch / Italienisch |
| Solltemperatur Zuluft | Number | Zieltemperatur in °C |
| Bus-Raumtemperatur | Number | Raumtemperatur für Busübertragung (°C) |
| Bus-Relative Feuchte | Number | Feuchtewert für Busübertragung (%) |
| Bus-CO₂/Luftqualität | Number | CO₂-Wert für Busübertragung (ppm) |
| Stoßlüftung | Switch | Kurzzeitige Intensivlüftung |
| Aus-Sperre | Switch | Gerät lässt sich nicht ausschalten |
| BDE-Sperre | Switch | Bedieneinheit sperren |
| Filterwechsel bestätigen | Button | Filterzähler zurücksetzen |
| Fehler zurücksetzen | Button | Aktive Fehler quittieren |

---

## Installation

### Voraussetzungen

- Home Assistant 2024.1 oder neuer
- Maico WS 320 KBET (oder kompatibles Gerät) im lokalen Netzwerk erreichbar
- Modbus TCP aktiviert am Gerät (Standard-Port: 502, Modbus-Adresse: 10)

### Manuelle Installation

1. Dieses Repository als ZIP herunterladen oder klonen.
2. Den Ordner `custom_components/maico_kwl/` in das Verzeichnis `<config>/custom_components/` deiner Home Assistant Installation kopieren.
3. Home Assistant neu starten.

### Installation via HACS (Custom Repository)

1. HACS öffnen → **Integrationen** → drei Punkte oben rechts → **Benutzerdefinierte Repositories**.
2. URL dieses Repositories einfügen, Kategorie: **Integration**.
3. Integration suchen und installieren, anschließend HA neu starten.

---

## Einrichtung

1. In Home Assistant: **Einstellungen → Geräte & Dienste → Integration hinzufügen**.
2. Nach „Maico KWL" suchen.
3. Verbindungsdaten eingeben:

| Parameter | Standard | Beschreibung |
|---|---|---|
| IP-Adresse / Host | – | IP der Lüftungsanlage |
| Port | 502 | Modbus TCP Port |
| Modbus-Adresse (Slave-ID) | 10 | Geräteadresse |
| Abfrageintervall | 30 s | Aktualisierungsrate |

---

## Technische Details

### Modbus-Registerblöcke

Die Integration liest folgende Registerbereiche zyklisch aus:

| Bereich | Register | Inhalt |
|---|---|---|
| Grundeinstellungen | 100–109 | Konfiguration, Sprache, Temperaturquelle |
| Lüftungseinstellungen | 150–159 | Sollwerte |
| Temperatureinstellungen | 300–302 | Soll-Temperaturen |
| Fehlermeldungen | 401–404 | Aktive Fehler |
| Betriebseinstellungen | 550–554 | Betriebsart, Jahreszeit, Stufe |
| Lüftungsstatus | 650–657 | Istwerte Stufe, Drehzahl, Volumenstrom, Filter |
| Temperaturen | 700–706 | Aktuelle Temperaturmessungen |
| Sensordaten | 750–762 | Feuchte (750–754), CO₂ (755–758), VOC (759–762) |
| Schaltzustände | 800–805 | Binäre Zustände |
| Betriebsstunden | 850–859 | 32-Bit-Zähler (High/Low-Word) |
| Filterüberwachung | 900 | Filterstatus |

### Berechneter Sensor – Wärmerückgewinnung

```
η = (T_Zuluft − T_Außenluft) / (T_Abluft − T_Außenluft) × 100 %
```

Wird nicht berechnet, wenn der Temperaturunterschied < 0,5 K ist.

### Modbus-Besonderheiten

- Temperaturen: Rohwert ÷ 10 (vorzeichenbehaftet, 16-Bit Two's Complement)
- Betriebsstunden: 32-Bit (High-Word + Low-Word in aufeinanderfolgenden Registern)
- Schreiben negativer Werte: `value & 0xFFFF`
- Write-only Bus-Register: 707 (T-Raum), 763 (rF), 764 (CO₂/LQ)

---

## Unterstützte Geräte

Getestet mit:
- **Maico WS 320 KBET**

Möglicherweise kompatibel mit anderen Maico-Geräten der WS-Serie, sofern die Modbus-Register übereinstimmen.

---

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](LICENSE). Es ist ein privates, inoffizielles Projekt und steht in keiner Verbindung zur Maico Ventilatoren GmbH & Co. KG.
