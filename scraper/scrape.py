#!/usr/bin/env python3
"""
HD2 Damage Calculator — Data Scraper

Usage:
  python scrape.py                     # full scrape of all enemies + weapons
  python scrape.py --enemies           # scrape enemies only
  python scrape.py --weapons           # scrape weapons only
  python scrape.py --only CQC          # scrape items whose name contains "CQC"
  python scrape.py --only "Bile Titan" # single targeted scrape
  python scrape.py --verbose           # show per-item parse details

--only and --enemies/--weapons MERGE results into existing JSON so the
rest of the data is preserved.

Requires: pip install requests beautifulsoup4
Outputs:  data/enemies.json, data/weapons.json, ../damage-calc.html
"""

import json, re, sys, time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────

BASE    = "https://helldivers.wiki.gg"
DELAY   = 0.8   # seconds between requests — be polite
VERBOSE        = "--verbose" in sys.argv or "-v" in sys.argv
ENEMIES_ONLY   = "--enemies"  in sys.argv
WEAPONS_ONLY   = "--weapons"  in sys.argv
# --only PATTERN  filters by case-insensitive substring match on name
_only_idx = next((i for i, a in enumerate(sys.argv) if a == '--only'), None)
ONLY_PATTERN   = sys.argv[_only_idx + 1].lower() if _only_idx and _only_idx + 1 < len(sys.argv) else None

# ── Armor tier name → numeric value ──────────────────────────────────────────

AP_MAP = {
    "unarmored": 0, "unarmored i": 0, "none": 0,
    "light":     1, "light i":     1,
    "light ii":  2,
    "medium":    3, "medium i":    3,
    "heavy":     4, "heavy i":     4,
    "anti-tank i":  5, "tank i":  5, "at i":  5,
    "anti-tank ii": 6, "tank ii": 6, "at ii": 6,
    "anti-tank iii":7, "tank iii":7, "at iii":7,
}

# ── Enemy pages to scrape ─────────────────────────────────────────────────────

ENEMY_PAGES = [
    # (display name, faction, wiki path)

    # ── Automatons ────────────────────────────────────────────────────────────
    ("War Strider",                  "bots",   "/wiki/War_Strider"),
    ("Factory Strider",              "bots",   "/wiki/Factory_Strider"),
    # Hulk is a container page with no anatomy table — skip it; variants below have their own
    ("Hulk Bruiser",                 "bots",   "/wiki/Hulk_Bruiser"),
    ("Hulk Scorcher",                "bots",   "/wiki/Hulk_Scorcher"),
    ("Hulk Obliterator",             "bots",   "/wiki/Hulk_Obliterator"),
    ("Hulk Firebomber",              "bots",   "/wiki/Hulk_Firebomber"),
    ("Devastator",                   "bots",   "/wiki/Devastator"),
    ("Heavy Devastator",             "bots",   "/wiki/Heavy_Devastator"),
    ("Rocket Devastator",            "bots",   "/wiki/Rocket_Devastator"),
    ("Annihilator Tank",             "bots",   "/wiki/Annihilator_Tank"),
    ("Shredder Tank",                "bots",   "/wiki/Shredder_Tank"),
    ("Barrager Tank",                "bots",   "/wiki/Barrager_Tank"),
    ("Berserker",                    "bots",   "/wiki/Berserker"),
    ("Marauder",                     "bots",   "/wiki/Marauder"),
    ("Gunship",                      "bots",   "/wiki/Gunship"),
    ("Scout Strider",                "bots",   "/wiki/Scout_Strider"),
    ("Reinforced Scout Strider",     "bots",   "/wiki/Reinforced_Scout_Strider"),
    ("Dropship",                     "bots",   "/wiki/Dropship"),
    ("Trooper",                      "bots",   "/wiki/Trooper"),
    ("Brawler",                      "bots",   "/wiki/Brawler"),
    ("Commissar",                    "bots",   "/wiki/Commissar"),
    ("MG Raider",                    "bots",   "/wiki/MG_Raider"),
    ("Rocket Raider",                "bots",   "/wiki/Rocket_Raider"),
    # Jet Brigade
    ("Assault Raider",               "bots",   "/wiki/Assault_Raider"),
    ("Jet Brigade Commissar",        "bots",   "/wiki/Jet_Brigade_Commissar"),
    ("Jet Brigade Trooper",          "bots",   "/wiki/Jet_Brigade_Trooper"),
    ("Jet Brigade MG Raider",        "bots",   "/wiki/Jet_Brigade_MG_Raider"),
    ("Jet Brigade Devastator",       "bots",   "/wiki/Jet_Brigade_Devastator"),
    ("Jet Brigade Hulk Scorcher",    "bots",   "/wiki/Jet_Brigade_Hulk_Scorcher"),
    ("Jet Brigade Hulk Bruiser",     "bots",   "/wiki/Jet_Brigade_Hulk_Bruiser"),
    # Incineration Corps
    ("Pyro Trooper",                 "bots",   "/wiki/Pyro_Trooper"),
    ("Incendiary Rocket Raider",     "bots",   "/wiki/Incendiary_Rocket_Raider"),
    ("Incendiary MG Devastator",     "bots",   "/wiki/Incendiary_MG_Devastator"),
    ("Conflagration Devastator",     "bots",   "/wiki/Conflagration_Devastator"),
    # Cyborg Legion
    ("Radical",                      "bots",   "/wiki/Radical"),
    ("Agitator",                     "bots",   "/wiki/Agitator"),
    ("Vox Engine",                   "bots",   "/wiki/Vox_Engine"),

    # ── Terminids ────────────────────────────────────────────────────────────
    ("Bile Titan",                   "bugs",   "/wiki/Bile_Titan"),
    ("Charger",                      "bugs",   "/wiki/Charger"),
    ("Charger Behemoth",             "bugs",   "/wiki/Charger_Behemoth"),
    ("Impaler",                      "bugs",   "/wiki/Impaler"),
    ("Hive Guard",                   "bugs",   "/wiki/Hive_Guard"),
    ("Brood Commander",              "bugs",   "/wiki/Brood_Commander"),
    ("Alpha Commander",              "bugs",   "/wiki/Alpha_Commander"),
    ("Shrieker",                     "bugs",   "/wiki/Shrieker"),
    ("Stalker",                      "bugs",   "/wiki/Stalker"),
    ("Nursing Spewer",               "bugs",   "/wiki/Nursing_Spewer"),
    ("Bile Spewer",                  "bugs",   "/wiki/Bile_Spewer"),
    ("Warrior",                      "bugs",   "/wiki/Warrior"),
    ("Alpha Warrior",                "bugs",   "/wiki/Alpha_Warrior"),
    ("Bile Warrior",                 "bugs",   "/wiki/Bile_Warrior"),
    ("Hunter",                       "bugs",   "/wiki/Hunter"),
    ("Pouncer",                      "bugs",   "/wiki/Pouncer"),
    ("Scavenger",                    "bugs",   "/wiki/Scavenger"),
    ("Bile Spitter",                 "bugs",   "/wiki/Bile_Spitter"),
    ("Hive Lord",                    "bugs",   "/wiki/Hive_Lord"),
    ("Spore Charger",                "bugs",   "/wiki/Spore_Charger"),
    ("Dragonroach",                  "bugs",   "/wiki/Dragonroach"),
    ("Predator Hunter",              "bugs",   "/wiki/Predator_Hunter"),
    ("Predator Stalker",             "bugs",   "/wiki/Predator_Stalker"),
    # Spore Burst variants
    ("Spore Burst Scavenger",        "bugs",   "/wiki/Spore_Burst_Scavenger"),
    ("Spore Burst Hunter",           "bugs",   "/wiki/Spore_Burst_Hunter"),
    ("Spore Burst Warrior",          "bugs",   "/wiki/Spore_Burst_Warrior"),
    ("Spore Burst Bile Titan",       "bugs",   "/wiki/Spore_Burst_Bile_Titan"),
    # Rupture variants
    ("Rupture Warrior",              "bugs",   "/wiki/Rupture_Warrior"),
    ("Rupture Spewer",               "bugs",   "/wiki/Rupture_Spewer"),
    ("Rupture Charger",              "bugs",   "/wiki/Rupture_Charger"),

    # ── Illuminate ───────────────────────────────────────────────────────────
    ("Harvester",                    "squids", "/wiki/Harvester"),
    ("Warp Ship",                    "squids", "/wiki/Warp_Ship"),
    ("Grounded Warp Ship",           "squids", "/wiki/Grounded_Warp_Ship"),
    ("Elevated Overseer",            "squids", "/wiki/Elevated_Overseer"),
    ("Crescent Overseer",            "squids", "/wiki/Crescent_Overseer"),
    ("Overseer",                     "squids", "/wiki/Overseer"),
    ("Voteless",                     "squids", "/wiki/Voteless"),
    ("Watcher",                      "squids", "/wiki/Watcher"),
    ("Fleshmob",                     "squids", "/wiki/Fleshmob"),
    ("Stingray",                     "squids", "/wiki/Stingray"),
    ("Leviathan",                    "squids", "/wiki/Leviathan"),
    ("Illuminate Overship",          "squids", "/wiki/Illuminate_Overship"),
    ("Veracitor",                    "squids", "/wiki/Veracitor"),
    ("Gatekeeper",                   "squids", "/wiki/Gatekeeper"),
    ("Obtruder",                     "squids", "/wiki/Obtruder"),
]

# ── Weapon pages to scrape ────────────────────────────────────────────────────

WEAPON_PAGES = [
    # (display name, category, wiki path)

    # ── Support Weapons ───────────────────────────────────────────────────────
    ("APW-1 Anti-Materiel Rifle",        "Support", "/wiki/APW-1_Anti-Materiel_Rifle"),
    ("AC-8 Autocannon",                  "Support", "/wiki/AC-8_Autocannon"),
    ("GR-8 Recoilless Rifle",            "Support", "/wiki/GR-8_Recoilless_Rifle"),
    ("LAS-99 Quasar Cannon",             "Support", "/wiki/LAS-99_Quasar_Cannon"),
    ("RS-422 Railgun",                   "Support", "/wiki/RS-422_Railgun"),
    ("MG-206 Heavy Machine Gun",         "Support", "/wiki/MG-206_Heavy_Machine_Gun"),
    ("MG-43 Machine Gun",                "Support", "/wiki/MG-43_Machine_Gun"),
    ("M-105 Stalwart",                   "Support", "/wiki/M-105_Stalwart"),
    ("MLS-4X Commando",                  "Support", "/wiki/MLS-4X_Commando"),
    ("EAT-17 Expendable Anti-Tank",      "Support", "/wiki/EAT-17_Expendable_Anti-Tank"),
    ("GL-21 Grenade Launcher",           "Support", "/wiki/GL-21_Grenade_Launcher"),
    ("GL-28 Belt-Fed Grenade Launcher",  "Support", "/wiki/GL-28_Belt-Fed_Grenade_Launcher"),
    ("GL-52 De-Escalator",               "Support", "/wiki/GL-52_De-Escalator"),
    ("RL-77 Airburst Rocket Launcher",   "Support", "/wiki/RL-77_Airburst_Rocket_Launcher"),
    ("FAF-14 Spear",                     "Support", "/wiki/FAF-14_Spear"),
    ("StA-X3 W.A.S.P. Launcher",         "Support", "/wiki/StA-X3_W.A.S.P._Launcher"),
    ("MS-11 Solo Silo",                  "Support", "/wiki/MS-11_Solo_Silo"),
    ("EAT-411 Leveller",                 "Support", "/wiki/EAT-411_Leveller"),
    ("EAT-700 Expendable Napalm",        "Support", "/wiki/EAT-700_Expendable_Napalm"),
    ("S-11 Speargun",                    "Support", "/wiki/S-11_Speargun"),
    ("LAS-98 Laser Cannon",              "Support", "/wiki/LAS-98_Laser_Cannon"),
    ("ARC-3 Arc Thrower",                "Support", "/wiki/ARC-3_Arc_Thrower"),
    ("FLAM-40 Flamethrower",             "Support", "/wiki/FLAM-40_Flamethrower"),
    ("TX-41 Sterilizer",                 "Support", "/wiki/TX-41_Sterilizer"),
    ("B/FLAM-80 Cremator",               "Support", "/wiki/B/FLAM-80_Cremator"),
    ("M-1000 Maxigun",                   "Support", "/wiki/M-1000_Maxigun"),
    ("MGX-42 Bullet Storm",              "Support", "/wiki/MGX-42_Bullet_Storm"),
    ("SG-88 Break-Action Shotgun",       "Support", "/wiki/SG-88_Break-Action_Shotgun"),
    ("PLAS-45 Epoch",                    "Support", "/wiki/PLAS-45_Epoch"),
    ("B/MD C4 Pack",                     "Support", "/wiki/B/MD_C4_Pack"),
    ("CQC-9 Defoliation Tool",           "Support", "/wiki/CQC-9_Defoliation_Tool"),
    ("CQC-20 Breaching Hammer",          "Support", "/wiki/CQC-20_Breaching_Hammer"),


    # ── Primary Weapons ───────────────────────────────────────────────────────
    # Assault Rifles
    ("AR-23 Liberator",                  "Primary", "/wiki/AR-23_Liberator"),
    ("AR-23C Liberator Concussive",      "Primary", "/wiki/AR-23C_Liberator_Concussive"),
    ("AR-23A Liberator Carbine",         "Primary", "/wiki/AR-23A_Liberator_Carbine"),
    ("AR-23P Liberator Penetrator",      "Primary", "/wiki/AR-23P_Liberator_Penetrator"),
    ("AR-32 Pacifier",                   "Primary", "/wiki/AR-32_Pacifier"),
    ("AR-2 Coyote",                      "Primary", "/wiki/AR-2_Coyote"),
    ("AR-61 Tenderizer",                 "Primary", "/wiki/AR-61_Tenderizer"),
    ("AR-59 Suppressor",                 "Primary", "/wiki/AR-59_Suppressor"),
    ("AR/GL-21 One-Two",                 "Primary", "/wiki/AR/GL-21_One-Two"),
    ("MA5C Assault Rifle",               "Primary", "/wiki/MA5C_Assault_Rifle"),
    ("StA-52 Assault Rifle",             "Primary", "/wiki/StA-52_Assault_Rifle"),
    # Battle Rifles
    ("BR-14 Adjudicator",                "Primary", "/wiki/BR-14_Adjudicator"),
    ("JAR-5 Dominator",                  "Primary", "/wiki/JAR-5_Dominator"),
    # Marksman Rifles
    ("R-2 Amendment",                    "Primary", "/wiki/R-2_Amendment"),
    ("R-2124 Constitution",              "Primary", "/wiki/R-2124_Constitution"),
    ("R-6 Deadeye",                      "Primary", "/wiki/R-6_Deadeye"),
    ("R-63 Diligence",                   "Primary", "/wiki/R-63_Diligence"),
    ("R-63CS Diligence Counter Sniper",  "Primary", "/wiki/R-63CS_Diligence_Counter_Sniper"),
    ("R-36 Eruptor",                     "Primary", "/wiki/R-36_Eruptor"),
    ("R-72 Censor",                      "Primary", "/wiki/R-72_Censor"),
    # SMGs
    ("MP-98 Knight",                     "Primary", "/wiki/MP-98_Knight"),
    ("StA-11 SMG",                       "Primary", "/wiki/StA-11_SMG"),
    ("M7S SMG",                          "Primary", "/wiki/M7S_SMG"),
    ("SMG-32 Reprimand",                 "Primary", "/wiki/SMG-32_Reprimand"),
    ("SMG-37 Defender",                  "Primary", "/wiki/SMG-37_Defender"),
    ("SMG-72 Pummeler",                  "Primary", "/wiki/SMG-72_Pummeler"),
    ("SMG/FLAM-34 Stoker",               "Primary", "/wiki/SMG/FLAM-34_Stoker"),
    ("SMG-203 Gallant",                  "Primary", "/wiki/SMG-203_Gallant"),
    # Shotguns
    ("SG-8 Punisher",                    "Primary", "/wiki/SG-8_Punisher"),
    ("SG-8P Punisher Plasma",            "Primary", "/wiki/SG-8P_Punisher_Plasma"),
    ("SG-8S Slugger",                    "Primary", "/wiki/SG-8S_Slugger"),
    ("SG-20 Halt",                       "Primary", "/wiki/SG-20_Halt"),
    ("SG-97 Sweeper",                    "Primary", "/wiki/SG-97_Sweeper"),
    ("SG-225 Breaker",                   "Primary", "/wiki/SG-225_Breaker"),
    ("SG-225SP Breaker Spray&Pray",      "Primary", "/wiki/SG-225SP_Breaker_Spray%26Pray"),
    ("SG-225IE Breaker Incendiary",      "Primary", "/wiki/SG-225IE_Breaker_Incendiary"),
    ("SG-451 Cookout",                   "Primary", "/wiki/SG-451_Cookout"),
    ("DBS-2 Double Freedom",             "Primary", "/wiki/DBS-2_Double_Freedom"),
    ("M90A Shotgun",                     "Primary", "/wiki/M90A_Shotgun"),
    # Crossbow / Special
    ("CB-9 Exploding Crossbow",          "Primary", "/wiki/CB-9_Exploding_Crossbow"),
    # Plasma
    ("PLAS-1 Scorcher",                  "Primary", "/wiki/PLAS-1_Scorcher"),
    ("PLAS-39 Accelerator Rifle",        "Primary", "/wiki/PLAS-39_Accelerator_Rifle"),
    ("PLAS-101 Purifier",                "Primary", "/wiki/PLAS-101_Purifier"),
    # Arc
    ("ARC-12 Blitzer",                   "Primary", "/wiki/ARC-12_Blitzer"),
    # Laser
    ("LAS-5 Scythe",                     "Primary", "/wiki/LAS-5_Scythe"),
    ("LAS-13 Trident",                   "Primary", "/wiki/LAS-13_Trident"),
    ("LAS-16 Sickle",                    "Primary", "/wiki/LAS-16_Sickle"),
    ("LAS-17 Double-Edge Sickle",        "Primary", "/wiki/LAS-17_Double-Edge_Sickle"),
    # Flamethrower
    ("FLAM-66 Torcher",                  "Primary", "/wiki/FLAM-66_Torcher"),
    # Variable
    ("VG-70 Variable",                   "Primary", "/wiki/VG-70_Variable"),

    # ── Secondary Weapons ─────────────────────────────────────────────────────
    # Pistols
    ("P-2 Peacemaker",                   "Secondary", "/wiki/P-2_Peacemaker"),
    ("P-4 Senator",                      "Secondary", "/wiki/P-4_Senator"),
    ("P-19 Redeemer",                    "Secondary", "/wiki/P-19_Redeemer"),
    ("P-33 Missile Pistol",              "Secondary", "/wiki/P-33_Missile_Pistol"),
    ("P-35 Re-Educator",                 "Secondary", "/wiki/P-35_Re-Educator"),
    ("P-69 Veto",                        "Secondary", "/wiki/P-69_Veto"),
    ("P-72 Crisper",                     "Secondary", "/wiki/P-72_Crisper"),
    ("P-92 Warrant",                     "Secondary", "/wiki/P-92_Warrant"),
    ("P-113 Verdict",                    "Secondary", "/wiki/P-113_Verdict"),
    ("M6C/SOCOM Pistol",                 "Secondary", "/wiki/M6C/SOCOM_Pistol"),
    # Shotgun secondary
    ("SG-22 Bushwhacker",                "Secondary", "/wiki/SG-22_Bushwhacker"),
    # Laser secondary
    ("LAS-7 Dagger",                     "Secondary", "/wiki/LAS-7_Dagger"),
    ("LAS-58 Talon",                     "Secondary", "/wiki/LAS-58_Talon"),
    # Plasma secondary
    ("PLAS-15 Loyalist",                 "Secondary", "/wiki/PLAS-15_Loyalist"),
    # Grenade pistol
    ("GP-20 Ultimatum",                  "Secondary", "/wiki/GP-20_Ultimatum"),
    ("GP-31 Grenade Pistol",             "Secondary", "/wiki/GP-31_Grenade_Pistol"),
    # Melee
    ("CQC-2 Saber",                      "Secondary", "/wiki/CQC-2_Saber"),
    ("CQC-5 Combat Hatchet",             "Secondary", "/wiki/CQC-5_Combat_Hatchet"),
    ("CQC-19 Stun Lance",                "Secondary", "/wiki/CQC-19_Stun_Lance"),
    ("CQC-30 Stun Baton",                "Secondary", "/wiki/CQC-30_Stun_Baton"),
    ("CQC-42 Machete",                   "Secondary", "/wiki/CQC-42_Machete"),
    # ── Throwables ────────────────────────────────────────────────────────────
    ("G-6 Frag",                         "Throwable", "/wiki/G-6_Frag"),
    ("G-7 Pineapple",                    "Throwable", "/wiki/G-7_Pineapple"),
    ("G-10 Incendiary",                  "Throwable", "/wiki/G-10_Incendiary"),
    ("G-12 High Explosive",              "Throwable", "/wiki/G-12_High_Explosive"),
    ("G-13 Incendiary Impact",           "Throwable", "/wiki/G-13_Incendiary_Impact"),
    ("G-16 Impact",                      "Throwable", "/wiki/G-16_Impact"),
    ("G-31 Arc",                         "Throwable", "/wiki/G-31_Arc"),
    ("G-48 Giga Grenade",                "Throwable", "/wiki/G-48_Giga_Grenade"),
    ("G-50 Seeker",                      "Throwable", "/wiki/G-50_Seeker"),
    ("G-109 Urchin",                     "Throwable", "/wiki/G-109_Urchin"),
    ("G-123 Thermite",                   "Throwable", "/wiki/G-123_Thermite"),
    ("G-142 Pyrotech",                   "Throwable", "/wiki/G-142_Pyrotech"),
    ("G-4 Gas",                          "Throwable", "/wiki/G-4_Gas"),
    ("TED-63 Dynamite",                  "Throwable", "/wiki/TED-63_Dynamite"),
]

# ── HTTP utilities ────────────────────────────────────────────────────────────

_session   = requests.Session()
_session.headers["User-Agent"] = "HD2-damage-calc/1.0 (personal project; contact via github)"
_last_req  = 0.0

def fetch(path):
    global _last_req
    elapsed = time.time() - _last_req
    if elapsed < DELAY:
        time.sleep(DELAY - elapsed)
    url = path if path.startswith("http") else BASE + path
    try:
        r = _session.get(url, timeout=20)
        r.raise_for_status()
        _last_req = time.time()
        return r.text
    except Exception as e:
        print(f"    ✗ fetch failed ({url}): {e}")
        return None

# ── Normalization helpers ─────────────────────────────────────────────────────

def normalize_av(text):
    """'Heavy (AV4)' → 4,  'Medium' → 3,  'AV3' → 3,  'AP6' → 6"""
    t = text.strip()
    # Parenthetical: "(AV4)" or "(AP4)"
    m = re.search(r'\([AaPp][Vv]?\s*(\d+)\)', t)
    if m:
        return int(m.group(1))
    # Plain "AP6" or "AV4"
    m = re.search(r'\b[AaPp][Vv]?\s*(\d+)\b', t)
    if m:
        return int(m.group(1))
    # Name lookup
    key = re.sub(r'\s+', ' ', t).lower().strip()
    v = AP_MAP.get(key)
    if v is not None:
        return v
    # Partial match — try stripping extra words
    for k, v in AP_MAP.items():
        if key.startswith(k):
            return v
    return -1  # unknown

def parse_int(text):
    """'3,500' → 3500,  '—' → 0,  'Main pool' → -1 (sentinel)"""
    t = re.sub(r'[,\s]', '', text.strip())
    if not t or t in ('—', '-', 'n/a'):
        return 0
    if not t[0].isdigit():
        return -1
    try:
        return int(t)
    except ValueError:
        return 0

def parse_pct(text):
    """'80%' → 80,  '—' → 0,  '95%/100%' → 95  (take first value)"""
    t = text.split('/')[0].strip().rstrip('%').strip()
    if not t or t in ('—', '-'):
        return 0
    try:
        return int(t)
    except ValueError:
        return 0

def make_id(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

# ── Enemy anatomy parser ──────────────────────────────────────────────────────

def parse_enemy(html, name, faction, wiki_path):
    soup = BeautifulSoup(html, 'html.parser')

    for table in soup.find_all('table'):
        # Find the header row
        header_cells = table.find_all('th')
        if not header_cells:
            continue
        # Strip footnote reference numbers (e.g. "Health1" → "Health", "AV2" → "AV")
        headers = [re.sub(r'\d+$', '', c.get_text(strip=True)) for c in header_cells]

        if 'Part Name' not in headers or 'Health' not in headers:
            continue

        # Column index map (lowercased, footnote digits already stripped)
        col = {h.lower().strip(): i for i, h in enumerate(headers)}

        parts = []
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            if len(cells) < 3:
                continue

            def cell(key, default=''):
                idx = col.get(key)
                if idx is None or idx >= len(cells):
                    return default
                return cells[idx].get_text(separator=' ', strip=True)

            pname = cell('part name')
            if not pname or pname == 'Part Name':
                continue

            health_raw = cell('health', '0')
            health = parse_int(health_raw)
            av = normalize_av(cell('av', ''))
            if av < 0:
                av = 4  # default heavy if unknown — conservative
                if VERBOSE:
                    print(f"      ⚠ unknown AV for {pname} in {name}, defaulting to 4")

            parts.append({
                "name":             pname,
                "health":           health,
                "health_is_main":   health == -1,
                "av":               av,
                "fatal":            cell('fatal?', 'no').lower().startswith('y'),
                "overflow_pct":     parse_pct(cell('% to main', '0')),
                "overflow_cap":     cell('overflow cap?', 'no').lower().startswith('y'),
                "durable_pct":      parse_pct(cell('durable', '0')),
                "exdr":             parse_pct(cell('exdr', '0')),
            })

        if parts:
            if VERBOSE:
                print(f"    ✓ {len(parts)} parts parsed")
            return {
                "id":       make_id(name),
                "name":     name,
                "faction":  faction,
                "wiki_url": BASE + wiki_path,
                "parts":    parts,
            }

    print(f"    ⚠ no anatomy table found")
    return None

# ── Weapon parser ─────────────────────────────────────────────────────────────
# Wiki uses tables with class "attack-data-table-projectile" / "attack-data-table-explosion".
# Each table is one attack component. Rows are section-headers (1 cell) or key-value (2 cells).
# Projectile damage:  Damage section → 'Standard' row  → "450 Ballistic"
# Projectile durable: Damage section → 'vs. Durable'   → "225 Ballistic"
# Explosion damage:   Damage section → 'Inner Radius'  → "150 Explosion"
# Explosion durable:  Damage section → 'Inner Durable' → "150 Explosion"
# AP:                 Penetration section → 'Direct'   → "Heavy" / "Anti-Tank II"
# Linking: projectile table has 'Explosion On Impact' row → name of explosion table

_DMG_VAL_RE = re.compile(
    r'^(\d[\d,]*)\s+(Ballistic|Explosion|Fire|Arc|Gas|Laser(?:\s+Continuous)?|Impact|Damage|Melee)$',
    re.I
)

# attack-data-table-* classes that hold a primary attack component (not weapon stats or status)
_PRIMARY_TABLE_TYPES = {
    'attack-data-table-projectile': 'Projectile',
    'attack-data-table-beam':       'Beam',
    'attack-data-table-arc':        'Arc',
    'attack-data-table-spray':      'Spray',
    'attack-data-table-melee':      'Melee',
    'attack-data-table-damage':     'Damage',
}
_SKIP_TABLE_TYPES = {'attack-data-table-weapon', 'attack-data-table-status'}

def parse_weapon(html, name, category, wiki_path):
    soup = BeautifulSoup(html, 'html.parser')
    modes = _parse_attack_tables(soup)
    if modes:
        if VERBOSE:
            print(f"    ✓ {len(modes)} mode(s), "
                  f"{sum(len(m['components']) for m in modes)} component(s)")
        return {
            "id":       make_id(name),
            "name":     name,
            "category": category,
            "wiki_url": BASE + wiki_path,
            "modes":    modes,
        }
    print(f"    ⚠ could not parse weapon stats")
    return None

def _parse_attack_tables(soup):
    """
    Find all attack-data-table-* tables (projectile, beam, arc, spray, explosion),
    parse each into a component dict, then group into modes.
    """
    primary_tables = {}  # table_name → {comp_label, sections, linked_explosion}
    expl_tables    = {}  # table_name → sections

    for t in soup.find_all('table'):
        classes = t.get('class', [])

        # Skip weapon-stats and status-effect tables
        if any(c in _SKIP_TABLE_TYPES for c in classes):
            continue

        is_expl    = 'attack-data-table-explosion' in classes
        comp_label = next((_PRIMARY_TABLE_TYPES[c] for c in classes if c in _PRIMARY_TABLE_TYPES), None)

        if not is_expl and comp_label is None:
            continue

        rows = t.find_all('tr')
        if not rows:
            continue

        # First row = table name
        first_cells = rows[0].find_all(['th', 'td'])
        table_name  = first_cells[0].get_text(strip=True) if first_cells else ''

        # Parse key-value rows, tracking sections
        sections         = {}   # section_name (lower) → {key: value}
        current_section  = 'general'
        linked_explosion = None

        for row in rows[1:]:
            cells = row.find_all(['th', 'td'])
            if len(cells) == 1:
                current_section = cells[0].get_text(strip=True).lower()
                sections.setdefault(current_section, {})
            elif len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                val = cells[1].get_text(' ', strip=True)
                sections.setdefault(current_section, {})[key] = val
                if key == 'Explosion On Impact':
                    linked_explosion = val  # e.g. "85mm HEAT GRENADE_P_IE"

        if is_expl:
            expl_tables[table_name] = sections
        else:
            primary_tables[table_name] = {
                'comp_label':      comp_label,
                'sections':        sections,
                'linked_explosion': linked_explosion,
            }

    if not primary_tables and not expl_tables:
        return None

    # Build modes from primary (non-explosion) tables, linking in explosion components
    modes = []
    for prim_name, prim_entry in primary_tables.items():
        prim_comp = _extract_component(prim_entry['sections'], is_explosion=False)
        if not prim_comp:
            continue
        prim_comp['name'] = prim_entry['comp_label']  # use actual type as component name

        components = [prim_comp]

        linked = prim_entry.get('linked_explosion')
        if linked:
            # Table names use spaces; the link value may use underscores
            expl_secs = (expl_tables.get(linked)
                         or expl_tables.get(linked.replace('_', ' ')))
            if expl_secs:
                expl_comp = _extract_component(expl_secs, is_explosion=True)
                if expl_comp:
                    components.append(expl_comp)

        # Strip trailing type designators: " P", " B", "_S_dm", "_dm", etc.
        mode_name = re.sub(r'(?:\s+[A-Z]|_(?:[A-Z]+_)?dm)\s*$', '', prim_name).strip()
        if len(primary_tables) == 1:
            mode_name = 'Default'

        modes.append({"name": mode_name, "components": components})

    # Handle pure-explosion weapons (no linked primary table)
    linked_expl_names = {
        (e.get('linked_explosion') or '').replace('_', ' ')
        for e in primary_tables.values()
    }
    for expl_name, expl_secs in expl_tables.items():
        if expl_name not in linked_expl_names and expl_name.replace('_', ' ') not in linked_expl_names:
            expl_comp = _extract_component(expl_secs, is_explosion=True)
            if expl_comp:
                mode_name = re.sub(r'\s+P\s*IE\s*$', '', expl_name, flags=re.I).strip()
                if len(expl_tables) == 1:
                    mode_name = 'Default'
                modes.append({"name": mode_name, "components": [expl_comp]})

    return modes if modes else None

def _extract_component(sections, is_explosion):
    """Extract a damage component dict from a parsed section dict."""
    damage_sec = sections.get('damage', {})
    pen_sec    = sections.get('penetration', {})

    # ── Damage value ──────────────────────────────────────────────────────────
    std_damage = None
    std_type   = None

    if is_explosion:
        candidates = ['Inner Radius', 'Direct', 'Standard']
    else:
        candidates = ['Standard', 'Direct', 'Projectile']

    for key in candidates:
        m = _DMG_VAL_RE.match(damage_sec.get(key, ''))
        if m:
            std_damage = int(m.group(1).replace(',', ''))
            std_type   = m.group(2).lower()
            break

    if std_damage is None:
        # Fallback: any value in damage section that looks like a damage value,
        # skipping outer-radius fall-off rows and durable rows
        for key, val in damage_sec.items():
            if 'outer' in key.lower() or 'durable' in key.lower():
                continue
            m = _DMG_VAL_RE.match(val)
            if m:
                std_damage = int(m.group(1).replace(',', ''))
                std_type   = m.group(2).lower()
                break

    if std_damage is None:
        return None

    # ── Durable damage ────────────────────────────────────────────────────────
    durable = None
    if is_explosion:
        dur_candidates = ['Inner Durable', 'vs. Durable', 'Durable']
    else:
        dur_candidates = ['vs. Durable', 'Direct Durable', 'Durable']

    for key in dur_candidates:
        m = _DMG_VAL_RE.match(damage_sec.get(key, ''))
        if m:
            durable = int(m.group(1).replace(',', ''))
            break

    if durable is None:
        durable = std_damage // 2   # default: 50%

    # ── Armor Penetration ─────────────────────────────────────────────────────
    ap = 0
    for key in ['Direct', 'AoE', 'Splash', 'Projectile']:
        val = pen_sec.get(key, '')
        av  = normalize_av(val)
        if av >= 0:
            ap = av
            break

    return {
        "name":           "Explosion" if is_explosion else "Projectile",
        "damage":         std_damage,
        "durable_damage": durable,
        "type":           std_type,
        "ap":             ap,
    }

# ── HTML updater ──────────────────────────────────────────────────────────────

_DATA_RE = re.compile(
    r'// DATA_BEGIN\n[\s\S]*?// DATA_END',
    re.M
)

def update_html(weapons, enemies):
    html_path = Path(__file__).parent.parent / 'damage-calc.html'
    if not html_path.exists():
        print(f"  ⚠ damage-calc.html not found at {html_path} — skipping HTML update")
        print(f"    Create it first, then re-run the scraper.")
        return

    src = html_path.read_text(encoding='utf-8')
    new_block = (
        "// DATA_BEGIN\n"
        f"const WEAPONS = {json.dumps(weapons, indent=2)};\n"
        f"const ENEMIES = {json.dumps(enemies, indent=2)};\n"
        "// DATA_END"
    )

    if not _DATA_RE.search(src):
        print(f"  ⚠ DATA_BEGIN/END markers not found in damage-calc.html — skipping HTML update")
        return

    updated = _DATA_RE.sub(new_block, src)
    html_path.write_text(updated, encoding='utf-8')
    print(f"  → damage-calc.html updated ({len(weapons)} weapons, {len(enemies)} enemies)")

# ── Main ──────────────────────────────────────────────────────────────────────

def _load_json(path):
    """Load a JSON list from disk, returning {} keyed by 'id', or empty dict."""
    if path.exists():
        return {item['id']: item for item in json.loads(path.read_text(encoding='utf-8'))}
    return {}

def _save_json(path, items):
    path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding='utf-8')

def main():
    data_dir = Path(__file__).parent / 'data'
    data_dir.mkdir(exist_ok=True)

    targeted = ONLY_PATTERN or ENEMIES_ONLY or WEAPONS_ONLY

    def matches(name):
        if ONLY_PATTERN:
            return ONLY_PATTERN in name.lower()
        return True

    enemies_path = data_dir / 'enemies.json'
    weapons_path = data_dir / 'weapons.json'

    # In targeted mode, load existing data so we can merge
    existing_enemies = _load_json(enemies_path) if targeted else {}
    existing_weapons = _load_json(weapons_path) if targeted else {}

    # ── Enemies ───────────────────────────────────────────────────────────────
    if not WEAPONS_ONLY:
        enemy_list = [(n, f, p) for n, f, p in ENEMY_PAGES if matches(n)]
        print("=" * 50)
        print(f"Scraping enemies ({len(enemy_list)})...")
        print("=" * 50)
        new_enemies = {}
        for name, faction, path in enemy_list:
            print(f"  {name}")
            html = fetch(path)
            if html:
                e = parse_enemy(html, name, faction, path)
                if e:
                    new_enemies[e['id']] = e

        if targeted:
            existing_enemies.update(new_enemies)
            all_enemies = list(existing_enemies.values())
        else:
            all_enemies = list(new_enemies.values())

        _save_json(enemies_path, all_enemies)
        print(f"\n  ✓ {len(new_enemies)}/{len(enemy_list)} scraped → {enemies_path}\n")
    else:
        all_enemies = list(existing_enemies.values()) or list(_load_json(enemies_path).values())

    # ── Weapons ───────────────────────────────────────────────────────────────
    if not ENEMIES_ONLY:
        weapon_list = [(n, c, p) for n, c, p in WEAPON_PAGES if matches(n)]
        print("=" * 50)
        print(f"Scraping weapons ({len(weapon_list)})...")
        print("=" * 50)
        new_weapons = {}
        failed = []
        for name, category, path in weapon_list:
            print(f"  {name}")
            html = fetch(path)
            if html:
                w = parse_weapon(html, name, category, path)
                if w:
                    new_weapons[w['id']] = w
                else:
                    failed.append(name)
            else:
                failed.append(name)

        if targeted:
            existing_weapons.update(new_weapons)
            all_weapons = list(existing_weapons.values())
        else:
            all_weapons = list(new_weapons.values())

        # Merge manual overrides
        overrides_path = data_dir / 'weapons_manual.json'
        if overrides_path.exists():
            overrides = json.loads(overrides_path.read_text(encoding='utf-8'))
            override_map = {w['id']: w for w in overrides}
            all_weapons = [override_map.get(w['id'], w) for w in all_weapons]
            scraped_ids = {w['id'] for w in all_weapons}
            for o in overrides:
                if o['id'] not in scraped_ids:
                    all_weapons.append(o)
            print(f"  ✓ Applied {len(overrides)} manual override(s)")

        _save_json(weapons_path, all_weapons)
        print(f"\n  ✓ {len(new_weapons)}/{len(weapon_list)} weapons → {weapons_path}")
        if failed:
            print(f"  ⚠ Failed: {', '.join(failed)}")
            print(f"    Tip: re-run with --verbose to see details.")
    else:
        all_weapons = list(existing_weapons.values()) or list(_load_json(weapons_path).values())

    # ── Update HTML ───────────────────────────────────────────────────────────
    print("\nUpdating damage-calc.html...")
    update_html(all_weapons, all_enemies)
    print("\nDone.")

if __name__ == '__main__':
    main()
