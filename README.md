# ZHA → Zigbee2MQTT Migration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/19DMO89/zha2z2m/actions/workflows/validate.yml/badge.svg)](https://github.com/19DMO89/zha2z2m/actions/workflows/validate.yml)

Home-Assistant-Integration, die beim Umstieg von **ZHA** auf **Zigbee2MQTT** hilft – ohne dass Dashboards, Automationen und Skripte kaputtgehen.

*English summary below.*

## Was macht die Integration?

1. **Export** – Alle ZHA-Geräte und -Entitäten werden nach `/config/zha2z2m/` gespeichert: Entitäts-IDs, Namen, Bereiche, Labels, Icons, Aliase, Einheiten-/Anzeigeoptionen und aktuelle Zustände. Läuft ZHA noch, werden zusätzlich die Zigbee-Netzwerkeinstellungen exportiert (`coordinator_backup.json` und `z2m_configuration_snippet.yaml`).
2. **ZHA deaktivieren** – mit Hinweis, welchen Port und welchen `adapter` du in Zigbee2MQTT eintragen musst.
3. **Geräte migrieren** – Sobald ein Gerät in Zigbee2MQTT angelernt ist, wählst du aus, welches ZHA-Gerät es früher war. Geräte mit gleicher IEEE-Adresse werden automatisch erkannt (inkl. Benachrichtigung). Für jede alte Entität wird die passende Zigbee2MQTT-Entität vorgeschlagen (Temperatur ↔ temperature, LQI ↔ linkquality, …) und kann angepasst werden. Dann wird übernommen:
   - **Entitäts-ID** (die Z2M-Entität bekommt die alte ID → Dashboards, Automationen, Skripte funktionieren weiter)
   - Gerätename, Entitätsnamen (exakter alter Anzeigename), Icon, Aliase (Sprachassistent)
   - Bereich und Labels von Gerät und Entität
   - Ausgeblendet/Deaktiviert-Status und Einheiten-/Nachkommastellen-Einstellungen
   - **Verlauf/Statistiken** bleiben unter derselben Entitäts-ID erhalten
4. **Verweise prüfen** – Automationen/Skripte, die eine **Geräte-ID** verwenden, werden aufgelistet. Optional werden alte Geräte-IDs in `automations.yaml`, `scripts.yaml` und `scenes.yaml` ersetzt (mit Backup). `domain: zha`-Geräteauslöser und `zha_event`-Auslöser werden markiert – diese müssen neu gebaut werden (z. B. mit dem `action`-Sensor/-Event von Zigbee2MQTT).

### Eigene Seite in der Seitenleiste

Nach der Einrichtung erscheint links in der Seitenleiste automatisch **„ZHA → Z2M“** (nur für Administratoren). Dort läuft die komplette Migration grafisch: Fortschritt, Export, ZHA aus/ein, neue Zigbee2MQTT-Geräte mit Auswahl „War in ZHA“, Entitäts-Zuordnung, „Alle mit gleicher IEEE migrieren“ und die Verweis-Prüfung.

Abschalten: *Integration → Konfigurieren → Einstellungen → „In der Seitenleiste anzeigen“*. Alles geht alternativ auch über den Assistenten unter **Konfigurieren**.

Zusätzlich gibt es den Sensor **„Ausstehende Geräte“** mit der Liste aller noch nicht migrierten Geräte – praktisch als Checkliste auf einem Dashboard.

## Installation

### HACS
1. HACS → ⋮ → **Benutzerdefinierte Repositories** → `https://github.com/19DMO89/zha2z2m`, Kategorie **Integration**
2. „ZHA → Zigbee2MQTT Migration“ installieren, Home Assistant neu starten
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → „ZHA → Zigbee2MQTT Migration“*

### Manuell
Ordner `custom_components/zha2z2m` nach `/config/custom_components/` kopieren und neu starten.

## Ablauf

> **Vorher ein vollständiges Home-Assistant-Backup erstellen!**

1. Seite **ZHA → Z2M** in der Seitenleiste öffnen (oder Integration → **Konfigurieren**) → **Exportieren** (solange ZHA noch läuft)
2. **2. ZHA deaktivieren**
3. Mosquitto + Zigbee2MQTT installieren und mit dem angezeigten Port/Adapter konfigurieren
4. Geräte in Zigbee2MQTT anlernen
5. **3. Ein Gerät migrieren** (oder **3b.** für alle Geräte mit gleicher IEEE-Adresse auf einmal)
6. **4. Geräte-Verweise prüfen / korrigieren**
7. Wenn alles läuft: ZHA-Integration löschen

Rückweg: **„ZHA wieder aktivieren“** (vorher Zigbee2MQTT stoppen). Die Exportdatei bleibt in jedem Fall erhalten.

### Netzwerk übernehmen (optional, fortgeschritten)
Mit `z2m_configuration_snippet.yaml` (pan_id, ext_pan_id, network_key, channel) und `coordinator_backup.json` (in das Zigbee2MQTT-Datenverzeichnis kopieren) kann Zigbee2MQTT das bestehende Zigbee-Netzwerk mit **demselben** Koordinator weiterverwenden. Viele Geräte melden sich dann ohne Neuanlernen; Batteriegeräte meist erst nach Tastendruck. Niemals beide Systeme gleichzeitig mit diesem Netzwerk betreiben!

## Dienste

| Dienst | Beschreibung |
|---|---|
| `zha2z2m.export` | Export erstellen |
| `zha2z2m.disable_zha` / `zha2z2m.enable_zha` | ZHA deaktivieren / wieder aktivieren |
| `zha2z2m.migrate_device` | Ein Z2M-Gerät migrieren (`z2m_device_id`, optional `zha_ieee`) |
| `zha2z2m.auto_migrate` | Alle Geräte mit passender IEEE-Adresse migrieren |
| `zha2z2m.replace_device_references` | Alte Geräte-IDs in YAML-Dateien ersetzen |

Alle Dienste liefern eine Antwort (Response) mit Details.

## Grenzen

- Nicht jede ZHA-Entität hat ein Gegenstück in Zigbee2MQTT (und umgekehrt) – nicht zugeordnete Entitäten werden angezeigt.
- Geräte-Auslöser (`domain: zha`) und `zha_event` lassen sich nicht automatisch übersetzen.
- Bei Energiezählern kann der Zählerstand des neuen Geräts abweichen.
- Im UI erstellte Automationen liegen in `automations.yaml` und werden unterstützt; YAML-Pakete/includes werden nur gemeldet, nicht verändert.

---

## English

A Home Assistant custom integration (HACS) that helps you move from ZHA to Zigbee2MQTT: it exports all ZHA devices/entities to a file, disables ZHA, and when you pair devices in Zigbee2MQTT it lets you pick which ZHA device each one was. The new entities then take over the old **entity ids**, names, areas, labels, icons, aliases and history, so dashboards, automations and scripts keep working. Remaining device-id references can be listed and replaced. After setup a **ZHA → Z2M** page appears in the sidebar (admins only, can be turned off in the integration settings); the same steps are also available via **Configure**.

## Versionierung

Das Projekt nutzt [Semantic Versioning](https://semver.org/lang/de/); Änderungen stehen im [CHANGELOG](CHANGELOG.md). HACS zeigt neue GitHub-Releases automatisch als Update an.

Neue Version veröffentlichen:

```bash
python scripts/bump_version.py 0.2.0      # manifest.json + const.py
# CHANGELOG.md ergänzen, committen, pushen
gh release create v0.2.0 --generate-notes
```

Der Release-Workflow prüft, dass Tag, `manifest.json` und `const.py` dieselbe Version haben.

## Lizenz
MIT
