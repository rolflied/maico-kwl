"""Konstanten für die Maico KWL Integration."""

DOMAIN = "maico_kwl"
DEFAULT_NAME = "Maico KWL"
DEFAULT_PORT = 502
DEFAULT_SLAVE = 10
DEFAULT_SCAN_INTERVAL = 30

CONF_SLAVE = "slave"
CONF_SCAN_INTERVAL = "scan_interval"

# Modbus-Registerblöcke die gelesen werden (Start-Adresse, Anzahl)
REGISTER_BLOCKS = [
    (100, 10),   # 100-109: Grundeinstellungen
    (150, 10),   # 150-159: Lüftungseinstellungen
    (300, 3),    # 300-302: Temperatureinstellungen
    (401, 4),    # 401-404: Fehlermeldungen
    (550, 5),    # 550-554: Betriebseinstellungen
    (650, 8),    # 650-657: Lüftungsstatus (aktuell)
    (700, 7),    # 700-706: Aktuelle Temperaturen
    (750, 13),   # 750-762: Sensordaten (Feuchte, CO2, VOC)
    (800, 6),    # 800-805: Schaltzustände
    (850, 10),   # 850-859: Betriebsstunden
    (900, 1),    # 900: Filterüberwachung
]

# Betriebsarten für Register 550
OPERATING_MODES = [
    "Aus",
    "Manuell",
    "Auto-Zeit",
    "Auto-Sensor",
    "Eco-Zuluft",
    "Eco-Abluft",
]

# Lüftungsstufen für Register 554 (Sollwert) und 650 (Istwert)
FAN_LEVELS = [
    "Aus",
    "Feuchteschutz",
    "Reduziert",
    "Nenn",
    "Intensiv",
]

# Jahreszeiten für Register 552
SEASONS = ["Winter", "Sommer"]

# Sprachen für Register 108
LANGUAGES = ["Deutsch", "Englisch", "Französisch", "Italienisch"]

# Raumtemperaturquelle für Register 109
ROOM_TEMP_SOURCES = ["Komfort-BDE", "Extern", "Intern", "Bus"]
