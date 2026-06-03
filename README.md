# HA LLM Prompt Builder

Nástroj, který přemění historii chytrého domu na hotový prompt pro velký jazykový model — a z odpovědi dostanete YAML automatizace přímo použitelné v Home Assistant.

---

## K čemu to slouží

Home Assistant shromažďuje obrovské množství dat ze senzorů, spínačů a dalších zařízení. Sama o sobě jsou to jen čísla a stavy. Tento skript je přetaví do strukturovaného promptu, který pošlete LLM (ChatGPT, Claude, Gemini…) a zpět dostanete:

- popis vzorů chování obyvatel (kdy vstávají, kdy odcházejí, co se zapíná po sobě)
- hotové Home Assistant automatizace ve YAML formátu s vysvětlením

---

## Co přesně skript dělá

1. **Načte historii** — přímo z `recorder.db` (SQLite databáze Home Assistantu) nebo ze záložního JSON souboru pro lokální vývoj
2. **Vyfiltruje relevantní entity** — zajímají nás jen vybrané senzory a přepínače (pohybový senzor, dveřní kontakt, tracker telefonu, smart zástrčky, ventilátor, vysavač, kamera)
3. **Vyčistí data** — odstraní stavy `unavailable` / `unknown` a duplicitní záznamy, které HA někdy vytváří při restartu
4. **Ořízne objem** — pokud je událostí víc než 600, rovnoměrně je vzorkuje, aby prompt zůstal v rozumném počtu tokenů
5. **Sestaví prompt** — připojí systémovou instrukci pro LLM a serializuje data jako kompaktní JSON
6. **Uloží výstup** do souboru `ha_prompt.txt`, který stačí zkopírovat do chatbota či poslat na LLM API

---

## Proč takto

### Přímý přístup k databázi

Home Assistant ukládá celou historii v SQLite. Přímý SQL dotaz je rychlejší a přesnější než REST API — nevyžaduje běžící instanci HA a nevyžaduje autentizaci.

### JSON fallback

Při vývoji nebo testování mimo HA server stačí mít soubor `ha_monitoring_data.json` se syntetickými daty — skript automaticky přepne.

### Sampling místo zkrácení

Při překročení limitu událostí skript zachová rovnoměrný průřez celou časovou osou místo prostého ořezání. LLM tak vidí vzory z celých 14 dní, ne jen ze začátku nebo konce.

### Kompaktní formát

Každá událost je uložena jako `{"e":..., "s":..., "t":...}` místo plného JSON s atributy. Šetří to přibližně 60–70 % tokenů bez ztráty informace potřebné pro analýzu vzorů.

---

## Konfigurace

Editujte konstanty na začátku `main.py`:

| Proměnná            | Výchozí                                 | Popis                                                           |
| ------------------- | --------------------------------------- | --------------------------------------------------------------- |
| `DB_PATH`           | `/config/.storage/home-assistant_v2.db` | Cesta k databázi HA                                             |
| `JSON_PATH`         | `ha_monitoring_data.json`               | Záložní JSON pro dev                                            |
| `OUTPUT`            | `ha_prompt.txt`                         | Název souboru, do kterého se uloží prompt                       |
| `DAYS_BACK`         | `14`                                    | Kolik dní historie zpracováváme                                 |
| `MAX_EVENTS`        | `600`                                   | Maximální počet událostí v promptu                              |
| `RELEVANT_ENTITIES` | viz kód                                 | Množina identifikátorů entit, které jsou relevantní pro analýzu |

---

## Jak spustit

### Požadavky

- Python 3.10+
- žádné externí závislosti (pouze standardní knihovna)

### Spuštění

**Na HA hostu** (přímý přístup k databázi):

```bash
python main.py
```

**Automatické spouštění z Home Assistant** (doporučeno pro pravidelnou analýzu):

Skript lze volat jako HA službu pomocí integrace `shell_command` a spouštět ho automatizací — například každou noc před analýzou. Stačí přidat příkaz do `configuration.yaml` a vytvořit automatizaci s time triggerem. Podrobný postup, včetně nastavení oprávnění, logování a ladění, najdete v [SHELL_COMMAND.md](SHELL_COMMAND.md).

**Lokální vývoj** (JSON fallback):

```bash
# Ujistěte se, že ha_monitoring_data.json existuje vedle main.py
python main.py
```

### Výstup

Skript vytiskne přehled a uloží soubor:

```
Načítám z DB: /config/.storage/home-assistant_v2.db
  načteno:       1 243 událostí
  po čištění:      987 událostí
  po vzorkování:   600 událostí

Prompt uložen → ha_prompt.txt  (~8 400 tokenů)
```

Obsah `ha_prompt.txt` pak vložte do libovolného LLM chatu. Odpověď bude JSON s klíči `patterns` (popsané vzory) a `automations` (YAML automatizace).
