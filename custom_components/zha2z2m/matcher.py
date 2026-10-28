"""Heuristics that pair old ZHA entities with new Zigbee2MQTT entities."""

from __future__ import annotations

import re
from typing import Any

from .const import SKIP

# Different words ZHA and Zigbee2MQTT use for the same thing.
SYNONYMS = {
    "lqi": "linkquality",
    "link_quality": "linkquality",
    "motion": "occupancy",
    "presence": "occupancy",
    "opening": "contact",
    "door": "contact",
    "window": "contact",
    "ias_zone": "contact",
    "moisture": "water_leak",
    "leak": "water_leak",
    "water": "water_leak",
    "lux": "illuminance",
    "temp": "temperature",
    "humid": "humidity",
    "summation_delivered": "energy",
    "consumption": "energy",
    "active_power": "power",
    "rms_voltage": "voltage",
    "rms_current": "current",
    "batt": "battery",
    "firmware": "update",
    "onoff": "state",
    "on_off": "state",
}

KNOWN_PAIRS = {"water_leak", "power_factor", "device_temperature", "color_temp"}

NOISE = {"zha", "zigbee2mqtt", "sensor", "binary", "the", "none", "0x"}

# Domains where a device normally has exactly one "main" entity.
PRIMARY_DOMAINS = {
    "light",
    "switch",
    "cover",
    "lock",
    "climate",
    "fan",
    "siren",
    "alarm_control_panel",
    "valve",
    "update",
}

AUTO_THRESHOLD = 26


def _tokens(*values: str | None, ignore: set[str] | None = None) -> set[str]:
    words: list[str] = []
    for value in values:
        if not value:
            continue
        words.extend(w for w in re.split(r"[\W_]+", value.lower()) if w)
    result: set[str] = set()
    for i, word in enumerate(words):
        if i + 1 < len(words):
            pair = f"{word}_{words[i + 1]}"
            if pair in SYNONYMS:
                result.add(SYNONYMS[pair])
            elif pair in KNOWN_PAIRS:
                result.add(pair)
        if word.isdigit() or re.fullmatch(r"(0x)?[0-9a-f]{16}", word):
            continue
        if word in NOISE or (ignore and word in ignore):
            continue
        result.add(SYNONYMS.get(word, word))
    return result


def old_features(entity: dict[str, Any], device_name: str) -> dict[str, Any]:
    object_id = entity["entity_id"].split(".", 1)[1]
    # The ZHA unique id looks like "00:15:8d:..:67-1-1026[-suffix]".
    uid_suffix = re.sub(r"^[0-9a-f:]{23}-?[0-9-]*", "", entity.get("unique_id") or "")
    return {
        "domain": entity["domain"],
        "device_class": entity.get("device_class") or entity.get("original_device_class"),
        "unit": entity.get("unit_of_measurement"),
        "tokens": _tokens(
            entity.get("translation_key"),
            entity.get("original_name"),
            entity.get("original_device_class"),
            object_id,
            uid_suffix,
            ignore=_tokens(device_name),
        ),
    }


def new_features(entity: dict[str, Any], device_name: str) -> dict[str, Any]:
    object_id = entity["entity_id"].split(".", 1)[1]
    # The Z2M unique id looks like "0x00158d0001234567_temperature_zigbee2mqtt".
    return {
        "domain": entity["domain"],
        "device_class": entity.get("device_class"),
        "unit": entity.get("unit_of_measurement"),
        "tokens": _tokens(
            entity.get("translation_key"),
            entity.get("original_name"),
            entity.get("device_class"),
            entity.get("unique_id"),
            object_id,
            ignore=_tokens(device_name),
        ),
    }


def score(old: dict[str, Any], new: dict[str, Any]) -> int:
    if old["domain"] != new["domain"]:
        return 0
    value = 1
    if old["device_class"] and new["device_class"]:
        value += 50 if old["device_class"] == new["device_class"] else -20
    value += 25 * len(old["tokens"] & new["tokens"])
    if old["unit"] and old["unit"] == new["unit"]:
        value += 10
    return max(value, 1)


def suggest_mapping(
    old_entities: list[dict[str, Any]],
    old_device_name: str,
    new_entities: list[dict[str, Any]],
    new_device_name: str,
) -> dict[str, str]:
    """Return {old_entity_id: new_entity_id | SKIP} using a greedy best match."""
    olds = {e["entity_id"]: old_features(e, old_device_name) for e in old_entities}
    news = {e["entity_id"]: new_features(e, new_device_name) for e in new_entities}

    def domain_count(features: dict[str, dict[str, Any]], domain: str) -> int:
        return sum(1 for f in features.values() if f["domain"] == domain)

    pairs: list[tuple[int, str, str]] = []
    for old_id, old in olds.items():
        for new_id, new in news.items():
            value = score(old, new)
            if not value:
                continue
            if (
                old["domain"] in PRIMARY_DOMAINS
                and domain_count(olds, old["domain"]) == 1
                and domain_count(news, new["domain"]) == 1
            ):
                value += 60
            pairs.append((value, old_id, new_id))

    mapping = {old_id: SKIP for old_id in olds}
    used: set[str] = set()
    for value, old_id, new_id in sorted(pairs, reverse=True):
        if value < AUTO_THRESHOLD or mapping[old_id] != SKIP or new_id in used:
            continue
        mapping[old_id] = new_id
        used.add(new_id)
    return mapping


def candidates(
    old_entity: dict[str, Any], new_entities: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """All new entities that could replace the old one (same domain)."""
    return [e for e in new_entities if e["domain"] == old_entity["domain"]]
