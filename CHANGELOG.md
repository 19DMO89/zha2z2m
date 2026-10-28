# Changelog

Alle nennenswerten Änderungen dieses Projekts. Das Format folgt
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/), die Versionierung
[Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

## [0.1.0] - 2026-10-28

### Added
- Export aller ZHA-Geräte und -Entitäten nach `/config/zha2z2m/` (inkl. Zigbee-Netzwerk-Backup und Zigbee2MQTT-Konfigurationsvorlage)
- ZHA deaktivieren / wieder aktivieren
- Migration eines Zigbee2MQTT-Geräts: Entitäts-IDs, Namen, Bereiche, Labels, Icons, Aliase und Optionen werden übernommen, der Verlauf bleibt erhalten
- Automatische Entitäts-Zuordnung und Migration aller Geräte mit gleicher IEEE-Adresse
- Prüfung und Ersetzung alter Geräte-IDs in `automations.yaml`, `scripts.yaml`, `scenes.yaml`
- Eigene Seite in der Seitenleiste („ZHA → Z2M“, abschaltbar), Assistent über „Konfigurieren“, Dienste mit Antwortdaten
- Sensor „Ausstehende Geräte“
- Deutsch und Englisch

[Unreleased]: https://github.com/19DMO89/zha2z2m/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/19DMO89/zha2z2m/releases/tag/v0.1.0
