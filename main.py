"""
Tento skript načte data z HA databáze recorder.db (nebo JSON) a připraví kompaktní prompt pro LLM.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Konfigurace ────────────────────────────────────────────────────────────────

DB_PATH   = Path("/config/.storage/home-assistant_v2.db")  # cesta na HA hostu
JSON_PATH = Path("ha_monitoring_data.json")                 # Syntenická data - fallback pro dev
OUTPUT    = Path("ha_prompt.txt")

DAYS_BACK = 14          # kolik dní historie budeme analyzovat
MAX_EVENTS = 600        # horní limit tokenů – při překročení aplikujeme sampling

# Entity, které nás zajímají (ostatní ignorujeme)
RELEVANT_ENTITIES = {
    "binary_sensor.motion_bedroom",
    "binary_sensor.door_contact_front",
    "device_tracker.phone_owner",
    "switch.smart_plug_coffee",
    "switch.smart_plug_tv",
    "switch.smart_plug_kettle",
    "switch.smart_plug_lamp",
    "fan.philips_air_cleaner",
    "vacuum.roomba",
    "camera.front_door",
}

# ── Načtení dat ────────────────────────────────────────────────────────────────

def load_from_db(db_path: Path, days_back: int) -> list[dict]:
    """Načte události přímo z HA recorder.db."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT entity_id, state, last_changed
        FROM states
        WHERE last_changed >= ?
          AND entity_id IN ({})
        ORDER BY last_changed
    """.format(",".join("?" * len(RELEVANT_ENTITIES))),
        [cutoff] + list(RELEVANT_ENTITIES)
    ).fetchall()
    conn.close()
    return [{"e": r[0], "s": r[1], "t": r[2][:19] + "Z"} for r in rows]


def load_from_json(json_path: Path) -> list[dict]:
    """Načte ze syntetického JSON (dev/testování)."""
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    return [
        {"e": ev["entity_id"], "s": ev["state"], "t": ev["last_changed"][:19] + "Z"}
        for ev in raw
        if ev["entity_id"] in RELEVANT_ENTITIES
    ]

# ── Čištění ────────────────────────────────────────────────────────────────────

def clean(events: list[dict]) -> list[dict]:
    """
    Odstraní:
    - duplicitní po sobě jdoucí stavy stejné entity (HA někdy ukládá
      identický stav dvakrát při restartu)
    - stavy 'unavailable' a 'unknown'
    """
    filtered = [e for e in events if e["s"] not in ("unavailable", "unknown")]
    deduped = []
    last: dict[str, str] = {}
    for ev in filtered:
        if last.get(ev["e"]) != ev["s"]:
            deduped.append(ev)
            last[ev["e"]] = ev["s"]
    return deduped


def sample(events: list[dict], max_events: int) -> list[dict]:
    """
    Pokud je událostí víc než MAX_EVENTS, rovnoměrně vzorkuje,
    aby se prompt vešel do rozumného počtu tokenů.
    Zachovává chronologické pořadí.
    """
    if len(events) <= max_events:
        return events
    step = len(events) / max_events
    return [events[int(i * step)] for i in range(max_events)]

# ── Sestavení promptu ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Jsi analytik chytré domácnosti. Dostaneš chronologický log událostí \
ze smart zařízení za posledních 14 dní. Každý záznam má tři pole:
  t = timestamp (UTC ISO 8601)
  e = entity_id zařízení
  s = nový stav

Tvůj úkol:
1. Identifikuj opakující se vzory chování (čas, sekvence, korelace mezi zařízeními).
2. Rozliš pracovní dny od víkendů.
3. Pro každý zjištěný vzor navrhni automatizaci v Home Assistant YAML formátu.
4. Každou automatizaci opatři:
   - alias (česky)
   - trigger
   - condition (pokud je potřeba)
   - action
   - krátkým komentářem proč ji doporučuješ

Odpověz jako JSON objekt se dvěma klíči:
  "patterns": seznam zjištěných vzorů (text)
  "automations": seznam YAML řetězců

Nevypisuj nic jiného než tento JSON objekt."""


def build_prompt(events: list[dict]) -> str:
    data_json = json.dumps(events, ensure_ascii=False, separators=(",", ":"))
    return f"{SYSTEM_PROMPT}\n\nDATA:\n{data_json}"

# ── Hlavní tok ─────────────────────────────────────────────────────────────────

def main():
    # Načtení – preferuje živou DB, fallback na JSON
    if DB_PATH.exists():
        print(f"Načítám z DB: {DB_PATH}")
        events = load_from_db(DB_PATH, DAYS_BACK)
    elif JSON_PATH.exists():
        print(f"DB nenalezena, načítám z JSON: {JSON_PATH}")
        events = load_from_json(JSON_PATH)
    else:
        raise FileNotFoundError("Nenalezena ani DB ani JSON.")

    print(f"  načteno:    {len(events)} událostí")
    events = clean(events)
    print(f"  po čištění: {len(events)} událostí")
    events = sample(events, MAX_EVENTS)
    print(f"  po vzorkování: {len(events)} událostí")

    prompt = build_prompt(events)
    OUTPUT.write_text(prompt, encoding="utf-8")

    tokens_est = len(prompt) // 4
    print(f"\nPrompt uložen → {OUTPUT}  (~{tokens_est} tokenů)")
    print("\nUkázka prvních 3 událostí v promptu:")
    for ev in events[:3]:
        print(f"  {ev}")

if __name__ == "__main__":
    main()