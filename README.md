# ✈️ Hamburg Airport Arrivals – Home Assistant Integration

Eine Custom Integration für Home Assistant, die die offizielle Open API des Flughafen Hamburgs abfragt und Ankunftsdaten als Sensoren bereitstellt.

***

## Features

- **Echtzeit-Landedaten** direkt aus der offiziellen Hamburg Airport Open API v2
- **Konfigurierbares Zeitfenster**: Anzahl vergangener und zukünftiger Landungen frei einstellbar
- **Automatischer Refresh** in konfigurierbarem Intervall (1–60 Minuten)
- **Vollständige HA-Integration**: Config Flow, Options Flow, DataUpdateCoordinator
- **Verspätungserkennung**: Automatischer Vergleich von Plan- und Erwartungszeit
- **Moderne Lovelace-Karte** mit HTML-Template-Card

***

## Voraussetzungen

- Home Assistant ≥ 2026.2
- API-Schlüssel vom Hamburg Airport Developer Portal
- [`html-template-card`](https://github.com/PiotrMachowski/Home-Assistant-Lovelace-HTML-Jinja2-Template-card) (für die Lovelace-Karte)

***

## Installation

### 1. API-Schlüssel besorgen

1. Auf [portal.api.hamburg-airport.de](https://portal.api.hamburg-airport.de) registrieren
2. Neue Applikation anlegen
3. Den generierten `Ocp-Apim-Subscription-Key` kopieren

### 2. Integration installieren

```bash
cp -r custom_components/hamburg_airport /config/custom_components/
```

Home Assistant neu starten.

### 3. Integration einrichten

**Einstellungen → Geräte & Dienste → Integration hinzufügen → "Hamburg Airport Arrivals"**

API-Schlüssel eingeben – er wird automatisch validiert.

### 4. HTML-Template-Card installieren (für Lovelace)

```bash
mkdir -p /config/www
curl -L -o /config/www/html-template-card.js \
  "https://raw.githubusercontent.com/PiotrMachowski/Home-Assistant-Lovelace-HTML-Jinja2-Template-card/master/html-template-card.js"
```

In `configuration.yaml` eintragen:

```yaml
lovelace:
  resources:
    - url: /local/html-template-card.js
      type: module
```

***

## Konfiguration

Über **Einstellungen → Geräte & Dienste → Hamburg Airport → Konfigurieren** stehen folgende Optionen zur Verfügung:

| Option | Standard | Bereich | Beschreibung |
|--------|----------|---------|--------------|
| Aktualisierungsintervall | 5 Min | 1–60 | Wie oft die API abgefragt wird |
| Vergangene Landungen | 2 | 0–10 | Anzahl bereits gelandeter Flüge im Zeitfenster |
| Kommende Landungen | 2 | 1–10 | Anzahl zukünftiger Flüge im Zeitfenster |

Nach dem Speichern wird die Integration automatisch neu geladen.

***

## Dateistruktur

```
custom_components/hamburg_airport/
├── __init__.py              # Coordinator & Setup-Logik
├── config_flow.py           # UI-Setup + Options-Flow
├── const.py                 # Konstanten & API-URL
├── sensor.py                # Sensor-Entities
├── manifest.json            # HA-Metadaten
└── translations/
    ├── de.json              # Deutsche UI-Texte
    └── en.json              # Englische UI-Texte
```

***

## Sensoren

### Nächste Landung

| Entity | Beschreibung | Beispiel |
|--------|-------------|---------|
| `sensor.hamburg_airport_nachste_landung_flugnummer` | Flugnummer | `LH 2084` |
| `sensor.hamburg_airport_nachste_landung_herkunft` | Herkunftsflughafen | `München` |
| `sensor.hamburg_airport_nachste_landung_iata_code` | IATA-Code Herkunft | `MUC` |
| `sensor.hamburg_airport_nachste_landung_planzeit` | Geplante Ankunftszeit | `22:05` |
| `sensor.hamburg_airport_nachste_landung_erwartete_zeit` | Erwartete Ankunftszeit | `22:18` |
| `sensor.hamburg_airport_nachste_landung_terminal` | Terminal | `2` |
| `sensor.hamburg_airport_nachste_landung_status` | Flugstatus | API-Statusfeld |

### Zeitfenster-Sensor

`sensor.hamburg_airport_landungen_zeitfenster` enthält alle Flüge im konfigurierten Fenster als Attribute:

| Attribut | Beschreibung |
|----------|-------------|
| `past_N_number` | Flugnummer des N-ten vergangenen Flugs |
| `past_N_origin` | Herkunft des N-ten vergangenen Flugs |
| `past_N_planned` | Planzeit des N-ten vergangenen Flugs |
| `past_N_expected` | Erwartete Zeit des N-ten vergangenen Flugs |
| `past_N_terminal` | Terminal des N-ten vergangenen Flugs |
| `future_N_number` | Flugnummer des N-ten kommenden Flugs |
| `future_N_origin` | Herkunft des N-ten kommenden Flugs |
| `future_N_planned` | Planzeit des N-ten kommenden Flugs |
| `future_N_expected` | Erwartete Zeit des N-ten kommenden Flugs |
| `future_N_terminal` | Terminal des N-ten kommenden Flugs |
| `window_past` | Anzahl konfigurierter vergangener Flüge |
| `window_future` | Anzahl konfigurierter kommender Flüge |

***

## Lovelace-Karte

Die mitgelieferte Karte nutzt `html-template-card` und passt sich automatisch an die konfigurierten Fenstergrößen an – keine Anpassung nötig wenn die Optionen geändert werden.

**Visuelles Design:**
- Vergangene Flüge: ausgegraut
- Trennlinie „── jetzt ──"
- Nächste Landung: grün hervorgehoben, Verspätungshinweis „▲ verspätet" in Orange
- Kommende Flüge: nummerierte Badges in Primärfarbe

```yaml
type: custom:html-template-card
ignore_line_breaks: true
content: |
  {% set s = 'sensor.hamburg_airport_landungen_zeitfenster' %}
  {% set wp = state_attr(s, 'window_past') | int(0) %}
  {% set wf = state_attr(s, 'window_future') | int(0) %}
  # ... (vollständiger Code siehe lovelace-card.yaml)
```

Die vollständige Karten-Konfiguration befindet sich in [`lovelace-card.yaml`](lovelace-card.yaml).

***

## Automation: Verspätungswarnung

```yaml
automation:
  - alias: "HAM: Verspätungswarnung nächste Landung"
    trigger:
      - platform: state
        entity_id: sensor.hamburg_airport_nachste_landung_erwartete_zeit
    condition:
      - condition: template
        value_template: >
          {% set planned  = states('sensor.hamburg_airport_nachste_landung_planzeit') %}
          {% set expected = states('sensor.hamburg_airport_nachste_landung_erwartete_zeit') %}
          {{ planned not in ['unknown','unavailable','']
             and expected not in ['unknown','unavailable','']
             and expected != planned }}
    action:
      - service: notify.notify
        data:
          title: "✈️ Verspätung am HAM"
          message: >
            Flug {{ states('sensor.hamburg_airport_nachste_landung_flugnummer') }}
            aus {{ states('sensor.hamburg_airport_nachste_landung_herkunft') }}
            (Plan: {{ states('sensor.hamburg_airport_nachste_landung_planzeit') }},
             Erwartet: {{ states('sensor.hamburg_airport_nachste_landung_erwartete_zeit') }})
```

***

## API-Details

| Eigenschaft | Wert |
|-------------|------|
| Endpoint | `GET https://rest.api.hamburg-airport.de/v2/flights/arrivals` |
| Authentifizierung | Header `Ocp-Apim-Subscription-Key` |
| Datenfenster | ±72 Stunden (gestern/heute/morgen) |
| Abfragemethode | Pull (Home Assistant fragt aktiv an) |
| Portal | [portal.api.hamburg-airport.de](https://portal.api.hamburg-airport.de) |

### Fehlerbehandlung

| HTTP-Status | Verhalten |
|-------------|-----------|
| `200` | Daten werden verarbeitet |
| `401` | `UpdateFailed: Ungültiger API-Schlüssel` |
| `403` | `UpdateFailed: Zugriff verweigert` |
| Netzwerkfehler | `UpdateFailed: Verbindungsfehler` |
| Ungültiges JSON | `UpdateFailed: Ungültiges JSON` |

***

## Technische Hinweise

- Die Zeitzone `Europe/Berlin` wird für alle Zeitvergleiche verwendet
- Flüge werden nach `expectedArrivalTime` sortiert, Fallback auf `plannedArrivalTime`
- `window_past` und `window_future` Attribute ermöglichen dynamische Lovelace-Karten ohne manuelle Anpassung
- Bei Options-Änderung wird die Integration automatisch neu geladen (`async_update_options`)

***

## Lizenz

MIT License – siehe [LICENSE](LICENSE)
