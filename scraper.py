"""
ASEP Feed Scraper - v5
Balanced filtering: keeps job announcements, removes clearly irrelevant content
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

# Τουλάχιστον ΜΙΑ από αυτές τις λέξεις πρέπει να υπάρχει στον τίτλο
REQUIRED_ANY = [
    "proslhps", "prokhruk", "plhrwsh", "thesewn", "theseis",
    "\u03c0\u03c1\u03cc\u03c3\u03bb\u03b7\u03c8",
    "\u03c0\u03c1\u03bf\u03c3\u03bb\u03ae\u03c8",
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be",
    "\u03c0\u03c1\u03bf\u03ba\u03b7\u03c1\u03cd\u03c3\u03c3",
    "\u03c0\u03bb\u03ae\u03c1\u03c9\u03c3\u03b7 \u03b8\u03ad\u03c3",
    "\u03b8\u03ad\u03c3\u03b5\u03b9\u03c2",
    "\u03b8\u03ad\u03c3\u03b5\u03c9\u03bd",
    "\u0399\u0394\u0391\u03a7",
    "\u0399\u0394\u039f\u03a7",
    "\u03b1\u03bd\u03b1\u03c0\u03bb\u03b7\u03c1\u03c9\u03c4",
    "1K/", "2K/", "3K/", "4K/", "5K/",
    "1\u039a/", "2\u039a/", "3\u039a/", "4\u039a/", "5\u039a/",
]

# Αν ο τίτλος περιέχει ΜΟΝΟ αυτές τις λέξεις (χωρίς required), απορρίπτεται
HARD_EXCLUDE = [
    "\u03b1\u03c0\u03cc\u03b2\u03bb\u03b7\u03c4",         # αποβλητ
    "\u03ba\u03c1\u03b1\u03c4\u03ae\u03c3\u03b5\u03b9\u03c2",  # κρατήσεις ΕΑΠ κλπ
    "\u03b4\u03b1\u03c0\u03ac\u03bd\u03b7",               # δαπάνη
    "\u03c0\u03c1\u03bf\u03bc\u03ae\u03b8\u03b5\u03b9\u03b1",  # προμήθεια
    "\u03b9\u03b8\u03b1\u03b3\u03ad\u03bd\u03b5\u03b9\u03b1",  # ιθαγένεια
    "\u03c5\u03c0\u03b5\u03c1\u03c9\u03c1\u03b9\u03b1\u03ba",  # υπερωριακ
    "\u03b1\u03bd\u03ac\u03ba\u03bb\u03b7\u03c3\u03b7",   # ανάκληση
    "\u03b1\u03ba\u03cd\u03c1\u03c9\u03c3\u03b7",         # ακύρωση
    "\u03b5\u03b9\u03c3\u03c6\u03bf\u03c1\u03ac",         # εισφορά
    "\u03b1\u03c0\u03bf\u03b4\u03bf\u03c7\u03ad\u03c2",   # αποδοχές μισθού
    "\u03bc\u03b9\u03c3\u03b8\u03bf\u03b4\u03bf\u03c3\u03af\u03b1",  # μισθοδοσία
]

CATEGORY_MAP = {
    "\u03b1\u03c3\u03b5\u03c0": "\u0391\u03a3\u0395\u03a0",
    "asep": "\u0391\u03a3\u0395\u03a0",
    "1\u03ba/": "\u0391\u03a3\u0395\u03a0", "2\u03ba/": "\u0391\u03a3\u0395\u03a0",
    "3\u03ba/": "\u0391\u03a3\u0395\u03a0", "4\u03ba/": "\u0391\u03a3\u0395\u03a0",
    "1k/": "\u0391\u03a3\u0395\u03a0", "2k/": "\u0391\u03a3\u0395\u03a0",
    "\u03bd\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03b9\u03b1\u03c4\u03c1": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03bd\u03bf\u03c3\u03b7\u03bb": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03b5\u03c3\u03c5": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03b4\u03ae\u03bc\u03bf": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03b4\u03b7\u03bc\u03bf": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03c0\u03b5\u03c1\u03b9\u03c6\u03ad\u03c1": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03c0\u03b1\u03b9\u03b4\u03b5\u03af\u03b1": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03b5\u03ba\u03c0\u03b1\u03af\u03b4": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03c3\u03c7\u03bf\u03bb": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03b1\u03bd\u03b1\u03c0\u03bb\u03b7\u03c1\u03c9\u03c4": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03b4\u03b9\u03ba\u03b1\u03c3\u03c4": "\u0394\u03b9\u03ba\u03b1\u03c3\u03c4\u03b9\u03ba\u03cc",
    "\u03c3\u03c4\u03c1\u03b1\u03c4": "\u03a3\u03c4\u03c1\u03b1\u03c4\u03cc\u03c2",
    "\u03bd\u03b1\u03c5\u03c4": "\u03a3\u03c4\u03c1\u03b1\u03c4\u03cc\u03c2",
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
    """True if title looks like a job announcement."""
    t = title.lower()
    # Hard exclude: clearly irrelevant
    for kw in HARD_EXCLUDE:
        if kw.lower() in t:
            return False
    # Must have at least one job-related keyword
    for kw in REQUIRED_ANY:
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

def deduplicate(items):
    seen = set()
    result = []
    for a in items:
        key = re.sub(r'\s+', ' ', (a.get("title") or "").lower().strip())[:80]
        if key and key not in seen:
            seen.add(key)
            result.append(a)
    return result


QUERIES = [
    "\u0391\u03a3\u0395\u03a0 \u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03b8\u03ad\u03c3\u03b5\u03c9\u03bd",
    "\u0391\u03a3\u0395\u03a0 \u03c0\u03c1\u03cc\u03c3\u03bb\u03b7\u03c8\u03b7",
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03c0\u03bb\u03ae\u03c1\u03c9\u03c3\u03b7 \u03b8\u03ad\u03c3\u03b5\u03c9\u03bd",
    "\u03c0\u03c1\u03cc\u03c3\u03bb\u03b7\u03c8\u03b7 \u0399\u0394\u0391\u03a7 \u0399\u0394\u039f\u03a7",
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03b1\u03bd\u03b1\u03c0\u03bb\u03b7\u03c1\u03c9\u03c4\u03ce\u03bd",
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03bd\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03bf \u03b8\u03ad\u03c3\u03b5\u03b9\u03c2",
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03b4\u03ae\u03bc\u03bf\u03c2 \u03b8\u03ad\u03c3\u03b5\u03b9\u03c2",
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03c0\u03b5\u03c1\u03b9\u03c6\u03ad\u03c1\u03b5\u03b9\u03b1 \u03b8\u03ad\u03c3\u03b5\u03b9\u03c2",
]

def scrape_diavgeia():
    all_items = []
    seen_ids = set()

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

            data = r.json()
            decisions = []
            if isinstance(data, list):
                decisions = data
            elif isinstance(data, dict):
                for key in ["decisions", "decisionList", "results", "items", "data"]:
                    val = data.get(key)
                    if isinstance(val, list):
                        decisions = val; break
                    elif isinstance(val, dict):
                        for sk in ["decision", "items", "list", "results"]:
                            sv = val.get(sk)
                            if isinstance(sv, list):
                                decisions = sv; break
                        if decisions: break

            accepted = 0
            for d in decisions:
                if not isinstance(d, dict):
                    continue

                title = ""
                for key in ["subject", "title", "label"]:
                    val = d.get(key)
                    if val and isinstance(val, str) and len(val.strip()) > 5:
                        title = val.strip(); break
                if not title:
                    continue

                if not is_job_announcement(title):
                    continue

                ada = d.get("ada") or d.get("protocolNumber") or ""
                uid = ada or abs(hash(title))
                if uid in seen_ids:
                    continue
                seen_ids.add(uid)

                issue_date = None
                for dk in ["issueDate", "submissionTimestamp", "publishDate", "date"]:
                    issue_date = parse_date(d.get(dk))
                    if issue_date:
                        break

                org = ""
                for ok in ["organizationLabel", "unitLabel", "signerLabel"]:
                    val = d.get(ok)
                    if val and isinstance(val, str):
                        org = val.strip(); break
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

                all_items.append({
                    "id": f"diav-{uid}",
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
                    "source": "diavgeia",
                })
                accepted += 1

            print(f"    OK accepted {accepted} / {len(decisions)}")
            time.sleep(1)

        except Exception as e:
            print(f"    x Error: {e}")
            time.sleep(1)

    return all_items


def main():
    print("=" * 50)
    print("ASEP Feed Scraper v5")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    items = deduplicate(scrape_diavgeia())

    active   = sorted([a for a in items if a["status"] == "active"],
                      key=lambda x: x.get("announced_date") or "", reverse=True)
    upcoming = sorted([a for a in items if a["status"] == "upcoming"],
                      key=lambda x: x.get("announced_date") or "", reverse=True)
    expired  = sorted([a for a in items if a["status"] == "expired"],
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
