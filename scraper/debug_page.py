#!/usr/bin/env python3
"""
Run: python debug_page.py
Dumps attack-data table structure for specific wiki pages to help fix the scraper.
Edit PAGES_TO_DEBUG to check different weapons/enemies.
"""
import re
import time
import requests
from bs4 import BeautifulSoup

# ── Pages to debug — edit this list and run: python debug_page.py ─────────────
PAGES_TO_DEBUG = [
    ("https://helldivers.wiki.gg/wiki/CQC-72_Entrenchment_Tool", "CQC-72 Entrenchment Tool (Support)"),
    ("https://helldivers.wiki.gg/wiki/CQC-73_Entrenchment_Tool", "CQC-73 Entrenchment Tool (Secondary)"),
]

for URL, label in PAGES_TO_DEBUG:
    time.sleep(0.5)
    r = requests.get(URL, headers={"User-Agent": "HD2-debug/1.0"}, timeout=20)
    soup = BeautifulSoup(r.text, 'html.parser')

    print("=" * 60)
    print(f"{label}  —  {URL}")
    print()

    # Dump ALL attack-data tables
    print("Full dump of all attack-data tables:")
    found = False
    for t in soup.find_all('table'):
        classes = t.get('class', [])
        if any('attack-data-table' in c for c in classes):
            found = True
            print(f"\n  === class={classes} ===")
            for row in t.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                print(f"    {[c.get_text(' ', strip=True)[:60] for c in cells]}")
    if not found:
        print("  (none found — showing all table classes)")
        for i, t in enumerate(soup.find_all('table')):
            rows = t.find_all('tr')
            print(f"  Table {i}: class={t.get('class',[])}  rows={len(rows)}")
            for row in rows[:2]:
                cells = row.find_all(['th','td'])
                print(f"    {[c.get_text(' ',strip=True)[:40] for c in cells]}")
    print()
