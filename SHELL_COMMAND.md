# Home Assistant – shell_command integrace

Dokumentace k volání externích skriptů z Home Assistant pomocí integrace `shell_command`.

---

## Co je shell_command

`shell_command` je vestavěná HA integrace, která umožňuje volat libovolný příkaz shellu jako HA službu. Výsledek příkazu (exit code) HA zaloguje, ale návratová hodnota se do HA dál nepropaguje.

Typické použití:

- spouštění Python ETL skriptů
- volání externích nástrojů
- zápis do souborů

---

## Definice příkazů

Příkazy se definují v `configuration.yaml` pod klíčem `shell_command`. Každý příkaz dostane název, který se stane názvem HA služby.

```yaml
# configuration.yaml

shell_command:
  spust_ha_etl: "python3 /config/scripts/ha_etl.py >> /config/scripts/ha_etl.log 2>&1"
```

Po uložení a restartu HA (nebo Quick Reload) vznikne služba `shell_command.spust_ha_etl`.

### Přesměrování výstupu

| Část příkazu                    | Význam                                             |
| ------------------------------- | -------------------------------------------------- |
| `>> /config/scripts/ha_etl.log` | stdout se připisuje na konec logovacího souboru    |
| `2>&1`                          | stderr se přesměruje na stdout (vše skončí v logu) |

Bez přesměrování výstup zmizí a ladění selhání je obtížné.

---

## Volání ze šablony automatizace

Příkaz se volá jako standardní HA služba v sekci `action`.

```yaml
# automations.yaml

alias: Noční analýza vzorů
trigger:
  - platform: time
    at: "02:00:00"
action:
  - service: shell_command.spust_ha_etl
mode: single
```

### Popis polí

| Pole       | Hodnota                 | Poznámka                                    |
| ---------- | ----------------------- | ------------------------------------------- |
| `platform` | `time`                  | Trigger na konkrétní čas                    |
| `at`       | `"02:00:00"`            | Čas ve formátu HH:MM:SS                     |
| `service`  | `shell_command.<název>` | Musí odpovídat názvu z `configuration.yaml` |
| `mode`     | `single`                | Pokud právě běží, nové spuštění se přeskočí |

---

## Adresářová struktura

```
/config/
├── configuration.yaml       ← definice shell_command
├── automations.yaml         ← automatizace s time triggerem
└── scripts/
    ├── main.py              ← Python skript
    └── ha_etl.log           ← log (vytvořen automaticky při prvním spuštění)
```

Skript musí být přístupný z HA hostu. Cesta `/config/` odpovídá kořenovému adresáři HA konfigurace.

---

## Oprávnění skriptu

HA volá příkaz pod uživatelem, pod kterým běží proces Home Assistant (typicky `homeassistant`). Skript musí mít práva ke čtení vstupních souborů i zápisu do výstupního logu.

```bash
# Nastavení oprávnění (spouštěno na hostu)
chmod +x /config/scripts/ha_etl.py
chown homeassistant:homeassistant /config/scripts/ha_etl.py
```

---

## Omezení shell_command

- **Žádná návratová hodnota** – výstup skriptu se nepropaguje zpět do HA. Výsledky je nutné předávat jinak (soubor, notifikace, REST API).
- **Žádné parametry z kontextu** – nelze přímo předat hodnotu entity nebo proměnné z triggeru do příkazu.
- **Timeout** – HA čeká na dokončení příkazu. Dlouho běžící skripty mohou způsobit varování; zvažte spouštění na pozadí (`&`) nebo použití `nohup`.
- **Žádná interaktivita** – příkaz nesmí čekat na vstup z terminálu.

---

## Ladění

### Kontrola logu skriptu

```bash
tail -f /config/scripts/ha_etl.log
```

### Kontrola HA logu

V HA UI: **Nastavení → Systém → Logy**, nebo přes soubor:

```bash
tail -f /config/home-assistant.log | grep shell_command
```

### Ruční spuštění služby

V HA UI: **Vývojářské nástroje → Akce**, vybrat `shell_command.spust_ha_etl` a kliknout **Volat akci**. Vhodné pro ověření před aktivací automatizace.

### Časté příčiny selhání

| Příznak             | Pravděpodobná příčina                                               |
| ------------------- | ------------------------------------------------------------------- |
| `command not found` | `python3` není v `PATH` – použít absolutní cestu `/usr/bin/python3` |
| `Permission denied` | Skript nemá právo ke spuštění nebo čtení vstupních souborů          |
| Prázdný log         | Chybí přesměrování `>> log 2>&1`                                    |
| Skript se nespustí  | `configuration.yaml` nebyl po změně znovu načten                    |

---

## Reload konfigurace

Po každé změně `configuration.yaml` je nutný reload. Možnosti:

1. **Quick Reload** – HA UI → Vývojářské nástroje → YAML → _Reload shell command_
2. **Restart HA** – Nastavení → Systém → Restartovat

Změny v `automations.yaml` lze načíst bez restartu přes _Reload automations_.
