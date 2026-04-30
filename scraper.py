"""
ASEP Feed Scraper - v7
- Searches Diavgeia by ASEP organization UID
- Strict title-based filtering for job announcements
"""

import json
import requests
from datetime import datetime
import re
import time

OUTPUT_FILE = "data.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ─────────────────────────────────────────────
# Λέξεις που ΠΡΕΠΕΙ να υπάρχουν στον τίτλο
# (τουλάχιστον μία)
# ─────────────────────────────────────────────
TITLE_REQUIRED = [
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be",      # προκήρυξ
    "\u03c0\u03c1\u03bf\u03ba\u03b7\u03c1\u03cd\u03c3\u03c3", # προκηρύσσ
    "\u03c0\u03c1\u03cc\u03c3\u03bb\u03b7\u03c8",             # πρόσληψ
    "\u03c0\u03c1\u03bf\u03c3\u03bb\u03ae\u03c8",             # προσλήψ
    "\u03c0\u03bb\u03ae\u03c1\u03c9\u03c3\u03b7 \u03b8\u03ad\u03c3",  # πλήρωση θέσ
    "\u03c0\u03bb\u03ae\u03c1\u03c9\u03c3\u03b7 \u03ba\u03b5\u03bd\u03ce\u03bd",  # πλήρωση κενών
    "\u0399\u0394\u0391\u03a7", "\u0399\u0394\u039f\u03a7",
    "\u03b1\u03bd\u03b1\u03c0\u03bb\u03b7\u03c1\u03c9\u03c4",  # αναπληρωτ
    "1K/", "2K/", "3K/", "4K/", "5K/",
    "1\u039a/", "2\u039a/", "3\u039a/", "4\u039a/", "5\u039a/",
]

# ─────────────────────────────────────────────
# Λέξεις που ΑΠΟΚΛΕΙΟΥΝ (ξεκάθαρα άσχετα)
# ─────────────────────────────────────────────
TITLE_EXCLUDE = [
    "\u03b5\u03bd\u03c4\u03bf\u03bb\u03ae \u03c0\u03bb\u03b7\u03c1\u03c9\u03bc",   # εντολή πληρωμ
    "\u03c0\u03bb\u03b7\u03c1\u03c9\u03bc\u03ae\u03c2",      # πληρωμής (payment)
    "\u03c0\u03bb\u03b7\u03c1\u03c9\u03bc\u03ce\u03bd",      # πληρωμών
    "\u03b1\u03ba\u03af\u03bd\u03b7\u03c4",                   # ακίνητ
    "\u03bc\u03af\u03c3\u03b8\u03c9\u03c3",                   # μίσθωσ
    "\u03b1\u03c0\u03cc\u03b2\u03bb\u03b7\u03c4",             # αποβλητ
    "\u03b5\u03b9\u03c3\u03c6\u03bf\u03c1\u03ac",             # εισφορά
    "\u03b4\u03b1\u03c0\u03ac\u03bd\u03b7",                   # δαπάνη
    "\u03c0\u03c1\u03bf\u03bc\u03ae\u03b8\u03b5\u03b9\u03b1", # προμήθεια
    "\u03bc\u03b9\u03c3\u03b8\u03bf\u03b4\u03bf\u03c3\u03af\u03b1",  # μισθοδοσία
    "\u03b9\u03b8\u03b1\u03b3\u03ad\u03bd\u03b5\u03b9\u03b1", # ιθαγένεια
    "\u03c5\u03c0\u03b5\u03c1\u03c9\u03c1\u03b9\u03b1\u03ba", # υπερωριακ
    "\u03b1\u03bd\u03ac\u03ba\u03bb\u03b7\u03c3\u03b7",       # ανάκληση
    "\u03b1\u03ba\u03cd\u03c1\u03c9\u03c3\u03b7",             # ακύρωση
    "\u03c3\u03c5\u03b3\u03ba\u03c1\u03cc\u03c4\u03b7\u03c3\u03b7 \u03b5\u03c0\u03b9\u03c4\u03c1\u03bf\u03c0",  # συγκρότηση επιτροπ
    "\u03c0\u03b1\u03c1\u03ac\u03c4\u03b1\u03c3\u03b7",       # παράταση
    "\u03b1\u03bd\u03b1\u03c3\u03c4\u03bf\u03bb\u03ae",       # αναστολή
    "\u03c4\u03c1\u03bf\u03c0\u03bf\u03c0\u03bf\u03af\u03b7\u03c3\u03b7",  # τροποποίηση
    "\u03b1\u03c0\u03bf\u03b6\u03b7\u03bc\u03af\u03c9\u03c3",  # αποζημίωσ
    "\u03b5\u03ba\u03c0\u03c1\u03bf\u03c3\u03ce\u03c0\u03b7\u03c3\u03b7",  # εκπροσώπηση
]

CATEGORY_MAP = {
    "\u03b1\u03c3\u03b5\u03c0": "\u0391\u03a3\u0395\u03a0",
    "asep": "\u0391\u03a3\u0395\u03a0",
    "1\u03ba/": "\u0391\u03a3\u0395\u03a0", "2\u03ba/": "\u0391\u03a3\u0395\u03a0",
    "3\u03ba/": "\u0391\u03a3\u0395\u03a0", "4\u03ba/": "\u0391\u03a3\u0395\u03a0",
    "\u03bd\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03b9\u03b1\u03c4\u03c1": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03bd\u03bf\u03c3\u03b7\u03bb": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03b4\u03ae\u03bc\u03bf": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03b4\u03b7\u03bc\u03bf": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03c0\u03b5\u03c1\u03b9\u03c6\u03ad\u03c1": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03c0\u03b1\u03b9\u03b4\u03b5\u03af\u03b1": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03b5\u03ba\u03c0\u03b1\u03af\u03b4": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03c3\u03c7\u03bf\u03bb": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03b1\u03bd\u03b1\u03c0\u03bb\u03b7\u03c1\u03c9\u03c4": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03b4\u03b9\u03ba\u03b1\u03c3\u03c4": "\u0394\u03b9\u03ba\u03b1\u03c3\u03c4\u03b9\u03ba\u03cc",
    "\u03c3\u03c4\u03c1\u03b1\u03c4": "\u03a3\u03c4\u03c1\u03b1\u03c4\u03cc\u03c2",
    "\u03c4\u03c1\u03ac\u03c0\u03b5\u03b6": "\u03a4\u03c1\u03ac\u03c0\u03b5\u03b6\u03b5\u03c2",
}

def detect_category(text):
    t = (text or "").lower()
    for kw, cat in CATEGORY_MAP.items():
        if kw in t:
            return cat
    return "\u0394\u03b7\u03bc\u03cc\u03c3\u03b9\u03bf"

def detect_status(announced_date):
    now = datetime.now()
    try:
        if announced_date:
            a = datetime.strptime(announced_date[:10], "%Y-%m-%d")
            if a.date() > now.date():
                return "upcoming"
        return "active"
    except Exception:
        return "active"

def is_job_announcement(title):
    """True only if title is a job announcement."""
    t = title.lower().strip()
    # Must NOT contain excluded words
    for kw in TITLE_EXCLUDE:
        if kw.lower() in t:
            return False
    # Must contain at least one required word
    for kw in TITLE_REQUIRED:
        if kw.lower() in t:
            return True
    return False

def parse_date(val):
    if not val:
        return None
    if isinstance(val, str) and len(val) >= 10:
        return val[:10]
    if isinstance(val, (int, float)) and val > 1e9:
        try:
            return datetime.fromtimestamp(int(val) / 1000).strftime("%Y-%m-%d")
        except Exception:
            return None
    return None

def extract_decisions(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["decisions", "decisionList", "results", "items", "data"]:
            val = data.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                for sk in ["decision", "items", "list", "results"]:
                    sv = val.get(sk)
                    if isinstance(sv, list):
                        return sv
    return []

def deduplicate(items):
    seen = set()
    result = []
    for a in items:
        key = re.sub(r'\s+', ' ', (a.get("title") or "").lower().strip())[:80]
        if key and key not in seen:
            seen.add(key)
            result.append(a)
    return result

def make_item(d, source_label):
    """Build a standardized item dict from a Diavgeia decision."""
    title = ""
    for key in ["subject", "title", "label"]:
        val = d.get(key)
        if val and isinstance(val, str) and len(val.strip()) > 5:
            title = val.strip()
            break
    if not title:
        return None

    if not is_job_announcement(title):
        return None

    ada = d.get("ada") or d.get("protocolNumber") or ""
    issue_date = None
    for dk in ["issueDate", "submissionTimestamp", "publishDate", "date"]:
        issue_date = parse_date(d.get(dk))
        if issue_date:
            break

    org = ""
    for ok in ["organizationLabel", "unitLabel", "signerLabel"]:
        val = d.get(ok)
        if val and isinstance(val, str):
            org = val.strip()
            break
    if not org:
        org = "\u0394\u03b7\u03bc\u03cc\u03c3\u03b9\u03bf\u03c2 \u03a6\u03bf\u03c1\u03ad\u03b1\u03c2"

    link = f"https://diavgeia.gov.gr/decision/view/{ada}" if ada else ""

    pos_m = re.search(r'(\d[\d\.]*)\s*\u03b8\u03ad\u03c3', title, re.I)
    positions = None
    if pos_m:
        try:
            positions = int(pos_m.group(1).replace(".", ""))
        except Exception:
            pass

    tags = ["\u0394\u03b9\u03b1\u03cd\u03b3\u03b5\u03b9\u03b1"]
    for t in ["\u03a0\u0395","\u03a4\u0395","\u0394\u0395","\u03a5\u0395",
              "\u0399\u0394\u0391\u03a7","\u0399\u0394\u039f\u03a7",
              "\u039c\u03cc\u03bd\u03b9\u03bc\u03bf","\u0391\u03bd\u03b1\u03c0\u03bb\u03b7\u03c1\u03c9\u03c4\u03ad\u03c2"]:
        if t.lower() in title.lower():
            tags.append(t)

    return {
        "id": f"diav-{ada or abs(hash(title))}",
        "title": title,
        "organization": org,
        "category": detect_category(title + " " + org),
        "status": detect_status(issue_date),
        "announced_date": issue_date,
        "deadline": None,
        "positions": positions,
        "fek": None,
        "tags": tags,
        "url": link,
        "source": source_label,
    }


# ─────────────────────────────────────────────
# Source A: Search by ΑΣΕΠ organization in Diavgeia
# ─────────────────────────────────────────────
def scrape_asep_org():
    """Fetch decisions issued BY ASEP organization directly."""
    items = []
    seen_ids = set()

    # Try to find ASEP's organization UID
    # ASEP UID in Diavgeia is typically searched via organization search
    asep_uids = []
    try:
        print("  -> Finding ASEP organization in Diavgeia...")
        r = requests.get(
            "https://diavgeia.gov.gr/opendata/organizations.json",
            params={"q": "\u0391\u03a3\u0395\u03a0", "size": 10},
            headers=HEADERS,
            timeout=15
        )
        if r.status_code == 200:
            data = r.json()
            orgs = data if isinstance(data, list) else data.get("organizations", [])
            for org in orgs:
                if not isinstance(org, dict):
                    continue
                label = (org.get("label") or org.get("latinName") or "").upper()
                if "ASEP" in label or "\u0391\u03a3\u0395\u03a0" in label:
                    uid = org.get("uid") or org.get("code") or org.get("id")
                    if uid:
                        asep_uids.append(str(uid))
                        print(f"    Found ASEP org UID: {uid} ({label})")
    except Exception as e:
        print(f"    x Org search error: {e}")

    # Search decisions by ASEP org UID
    for uid in asep_uids[:2]:
        try:
            print(f"  -> Fetching ASEP decisions (org {uid})...")
            r = requests.get(
                "https://diavgeia.gov.gr/opendata/search.json",
                params={
                    "organization": uid,
                    "size": 40,
                    "sort": "recent",
                },
                headers=HEADERS,
                timeout=20
            )
            if r.status_code != 200:
                print(f"    x HTTP {r.status_code}")
                continue

            decisions = extract_decisions(r.json())
            print(f"    -> {len(decisions)} decisions from ASEP org")

            for d in decisions:
                if not isinstance(d, dict):
                    continue
                item = make_item(d, "asep_diavgeia")
                if not item:
                    continue
                uid_key = item["id"]
                if uid_key in seen_ids:
                    continue
                seen_ids.add(uid_key)
                items.append(item)

            print(f"    OK accepted {len(items)} job announcements from ASEP org")
            time.sleep(1)
        except Exception as e:
            print(f"    x Error: {e}")

    return items, seen_ids


# ─────────────────────────────────────────────
# Source B: Keyword search queries
# ─────────────────────────────────────────────
QUERIES = [
    "\u0391\u03a3\u0395\u03a0 \u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7",
    "\u0391\u03a3\u0395\u03a0 \u03c0\u03c1\u03cc\u03c3\u03bb\u03b7\u03c8\u03b7",
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03c0\u03bb\u03ae\u03c1\u03c9\u03c3\u03b7 \u03b8\u03ad\u03c3\u03b5\u03c9\u03bd",
    "\u03c0\u03c1\u03cc\u03c3\u03bb\u03b7\u03c8\u03b7 \u0399\u0394\u0391\u03a7 \u0399\u0394\u039f\u03a7",
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03b1\u03bd\u03b1\u03c0\u03bb\u03b7\u03c1\u03c9\u03c4\u03ce\u03bd",
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03bd\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03bf",
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03b4\u03ae\u03bc\u03bf\u03c2",
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03c0\u03b5\u03c1\u03b9\u03c6\u03ad\u03c1\u03b5\u03b9\u03b1",
]

def scrape_keyword_queries(existing_ids):
    items = []
    seen_ids = set(existing_ids)

    for query in QUERIES:
        try:
            print(f"  -> {query[:45]}...")
            r = requests.get(
                "https://diavgeia.gov.gr/opendata/search.json",
                params={"q": query, "size": 20, "sort": "recent"},
                headers=HEADERS,
                timeout=20
            )
            if r.status_code != 200:
                print(f"    x HTTP {r.status_code}")
                time.sleep(1)
                continue

            decisions = extract_decisions(r.json())
            accepted = 0

            for d in decisions:
                if not isinstance(d, dict):
                    continue
                item = make_item(d, "diavgeia")
                if not item:
                    continue
                uid_key = item["id"]
                if uid_key in seen_ids:
                    continue
                seen_ids.add(uid_key)
                items.append(item)
                accepted += 1

            print(f"    OK accepted {accepted} / {len(decisions)}")
            time.sleep(1)

        except Exception as e:
            print(f"    x Error: {e}")
            time.sleep(1)

    return items


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    print("=" * 50)
    print("ASEP Feed Scraper v7")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    print("\n[1/2] ASEP organization search...")
    org_items, seen_ids = scrape_asep_org()

    print(f"\n[2/2] Keyword queries (skip {len(seen_ids)} already found)...")
    kw_items = scrape_keyword_queries(seen_ids)

    all_items = deduplicate(org_items + kw_items)

    active   = sorted([a for a in all_items if a["status"] == "active"],
                      key=lambda x: x.get("announced_date") or "", reverse=True)
    upcoming = sorted([a for a in all_items if a["status"] == "upcoming"],
                      key=lambda x: x.get("announced_date") or "", reverse=True)
    expired  = sorted([a for a in all_items if a["status"] == "expired"],
                      key=lambda x: x.get("announced_date") or "", reverse=True)

    all_items = active + upcoming + expired

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "last_updated": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "total": len(all_items),
            "announcements": all_items,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"OK Saved {len(all_items)} job announcements")
    print(f"   Active: {len(active)} | Upcoming: {len(upcoming)} | Expired: {len(expired)}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
