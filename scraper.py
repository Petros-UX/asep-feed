"""
ASEP Feed Scraper - v3
=======================
Sources:
  - Diavgeia OpenData API (main source - works!)
  - et.gr eFEK (FEK search)
  - asep.gr direct page attempts
"""

import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time

OUTPUT_FILE = "data.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

CATEGORY_MAP = {
    "\u03b1\u03c3\u03b5\u03c0": "\u0391\u03a3\u0395\u03a0",
    "asep": "\u0391\u03a3\u0395\u03a0",
    "\u03bd\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03b9\u03b1\u03c4\u03c1": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03bd\u03bf\u03c3\u03b7\u03bb": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03b5\u03c3\u03c5": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03b3\u03bd\u03b1": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03b4\u03ae\u03bc\u03bf": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03b4\u03b7\u03bc\u03bf": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03c0\u03b5\u03c1\u03b9\u03c6\u03ad\u03c1": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03ba\u03bf\u03b9\u03bd\u03bf\u03c4": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03c0\u03b1\u03b9\u03b4\u03b5\u03af\u03b1": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03b5\u03ba\u03c0\u03b1\u03af\u03b4": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03c3\u03c7\u03bf\u03bb": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03b1\u03bd\u03b1\u03c0\u03bb\u03b7\u03c1\u03c9\u03c4": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03b4\u03b9\u03ba\u03b1\u03c3\u03c4": "\u0394\u03b9\u03ba\u03b1\u03c3\u03c4\u03b9\u03ba\u03cc",
    "\u03c0\u03c1\u03c9\u03c4\u03bf\u03b4\u03b9\u03ba": "\u0394\u03b9\u03ba\u03b1\u03c3\u03c4\u03b9\u03ba\u03cc",
    "\u03c3\u03c4\u03c1\u03b1\u03c4": "\u03a3\u03c4\u03c1\u03b1\u03c4\u03cc\u03c2",
    "\u03bd\u03b1\u03c5\u03c4": "\u03a3\u03c4\u03c1\u03b1\u03c4\u03cc\u03c2",
    "\u03b1\u03b5\u03c1\u03bf\u03c0\u03bf\u03c1": "\u03a3\u03c4\u03c1\u03b1\u03c4\u03cc\u03c2",
    "\u03c4\u03c1\u03ac\u03c0\u03b5\u03b6": "\u03a4\u03c1\u03ac\u03c0\u03b5\u03b6\u03b5\u03c2",
}

def detect_category(text):
    t = (text or "").lower()
    for kw, cat in CATEGORY_MAP.items():
        if kw in t:
            return cat
    return "\u0386\u03bb\u03bb\u03bf"

def detect_status(announced_date, deadline):
    now = datetime.now()
    try:
        if deadline:
            d = datetime.strptime(deadline[:10], "%Y-%m-%d")
            if d.date() < now.date():
                return "expired"
        if announced_date:
            a = datetime.strptime(announced_date[:10], "%Y-%m-%d")
            if a.date() > now.date():
                return "upcoming"
        return "active"
    except Exception:
        return "active"

def parse_epoch(val):
    """Convert epoch ms to date string."""
    try:
        return datetime.fromtimestamp(int(val) / 1000).strftime("%Y-%m-%d")
    except Exception:
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


# ─────────────────────────────────────────────
# Source 1: Diavgeia API
# ─────────────────────────────────────────────
DIAVGEIA_QUERIES = [
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03c0\u03bb\u03ae\u03c1\u03c9\u03c3\u03b7 \u03b8\u03ad\u03c3\u03b5\u03c9\u03bd",
    "\u03c0\u03c1\u03cc\u03c3\u03bb\u03b7\u03c8\u03b7 \u03bc\u03cc\u03bd\u03b9\u03bc\u03bf\u03c5 \u03c0\u03c1\u03bf\u03c3\u03c9\u03c0\u03b9\u03ba\u03bf\u03cd \u03b4\u03b7\u03bc\u03cc\u03c3\u03b9\u03bf",
    "\u0391\u03a3\u0395\u03a0 \u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7",
    "\u03c0\u03c1\u03cc\u03c3\u03bb\u03b7\u03c8\u03b7 \u0399\u0394\u0391\u03a7 \u0399\u0394\u039f\u03a7",
    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03b5\u03ba\u03c0\u03b1\u03b9\u03b4\u03b5\u03c5\u03c4\u03b9\u03ba\u03ce\u03bd",
]

def scrape_diavgeia():
    all_items = []

    for query in DIAVGEIA_QUERIES:
        try:
            print(f"  -> Diavgeia query: {query[:40]}...")
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

            # Extract decisions list from any response structure
            decisions = []
            if isinstance(data, list):
                decisions = data
            elif isinstance(data, dict):
                for key in ["decisions", "decisionList", "results", "items", "data"]:
                    val = data.get(key)
                    if isinstance(val, list):
                        decisions = val
                        break
                    elif isinstance(val, dict):
                        for sk in ["decision", "items", "list", "results"]:
                            sv = val.get(sk)
                            if isinstance(sv, list):
                                decisions = sv
                                break
                        if decisions:
                            break

            print(f"    -> {len(decisions)} decisions found")

            for d in decisions:
                if not isinstance(d, dict):
                    continue

                # Get title - try all possible fields
                title = ""
                for key in ["subject", "title", "decisionTypeName", "label", "description"]:
                    val = d.get(key)
                    if val and isinstance(val, str) and len(val.strip()) > 5:
                        title = val.strip()
                        break
                if not title:
                    continue

                # Get date
                issue_date = None
                for dk in ["issueDate", "submissionTimestamp", "publishDate", "date", "protocolDate"]:
                    val = d.get(dk)
                    if not val:
                        continue
                    if isinstance(val, str) and len(val) >= 10:
                        issue_date = val[:10]
                        break
                    elif isinstance(val, (int, float)) and val > 1000000000:
                        issue_date = parse_epoch(val)
                        break

                # Get organization
                org = ""
                for ok in ["organizationLabel", "unitLabel", "signerLabel", "issuerLabel", "organization"]:
                    val = d.get(ok)
                    if val and isinstance(val, str):
                        org = val.strip()
                        break
                if not org:
                    org = "\u0394\u03b7\u03bc\u03cc\u03c3\u03b9\u03bf\u03c2 \u03a6\u03bf\u03c1\u03ad\u03b1\u03c2"

                ada = d.get("ada") or d.get("protocolNumber") or ""
                link = f"https://diavgeia.gov.gr/decision/view/{ada}" if ada else ""

                # Extract positions from title
                pos_m = re.search(r'(\d[\d\.]*)\s*\u03b8\u03ad\u03c3', title, re.I)
                positions = None
                if pos_m:
                    try:
                        positions = int(pos_m.group(1).replace(".", ""))
                    except Exception:
                        pass

                # Build tags
                tags = ["\u0394\u03b9\u03b1\u03cd\u03b3\u03b5\u03b9\u03b1"]
                for t in ["\u03a0\u0395", "\u03a4\u0395", "\u0394\u0395", "\u03a5\u0395",
                          "\u0399\u0394\u0391\u03a7", "\u0399\u0394\u039f\u03a7", "\u039c\u03cc\u03bd\u03b9\u03bc\u03bf"]:
                    if t.lower() in title.lower():
                        tags.append(t)

                all_items.append({
                    "id": f"diav-{ada or abs(hash(title))}",
                    "title": title,
                    "organization": org,
                    "category": detect_category(title + " " + org),
                    "status": detect_status(issue_date, None),
                    "announced_date": issue_date,
                    "deadline": None,
                    "positions": positions,
                    "fek": None,
                    "tags": tags,
                    "url": link,
                    "source": "diavgeia",
                })

            print(f"    OK {len(all_items)} total so far")
            time.sleep(1)

        except Exception as e:
            print(f"    x Error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)

    return all_items


# ─────────────────────────────────────────────
# Source 2: et.gr eFEK (FEK Online)
# ─────────────────────────────────────────────
def scrape_efek():
    items = []
    try:
        print("  -> et.gr eFEK search...")
        url = "https://www.et.gr/api/efetirida/search"
        params = {
            "q": "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7",
            "type": "G",
            "size": 20,
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            results = data if isinstance(data, list) else data.get("results", [])
            for item in results[:20]:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("subject") or ""
                if len(title) < 10:
                    continue
                date_str = item.get("date") or item.get("issueDate") or ""
                fek = item.get("fek") or item.get("fekNumber") or ""
                link = item.get("url") or item.get("link") or ""

                items.append({
                    "id": f"efek-{abs(hash(title))}",
                    "title": title,
                    "organization": "\u03a6\u0395\u039a",
                    "category": detect_category(title),
                    "status": detect_status(date_str[:10] if date_str else None, None),
                    "announced_date": date_str[:10] if date_str else None,
                    "deadline": None,
                    "positions": None,
                    "fek": fek,
                    "tags": ["\u03a6\u0395\u039a"],
                    "url": link,
                    "source": "efek",
                })
            print(f"    OK {len(items)} from eFEK")
        else:
            print(f"    x HTTP {r.status_code}")
    except Exception as e:
        print(f"    x Error: {e}")

    return items


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    print("=" * 50)
    print("ASEP Feed Scraper v3")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    all_items = []

    print("\n[1/2] Diavgeia API...")
    all_items.extend(scrape_diavgeia())

    print("\n[2/2] et.gr eFEK...")
    all_items.extend(scrape_efek())

    # Deduplicate and sort
    all_items = deduplicate(all_items)

    def sort_key(a):
        order = {"active": 0, "upcoming": 1, "expired": 2}
        return (order.get(a["status"], 3), a.get("announced_date") or "0000")

    all_items.sort(key=sort_key, reverse=False)
    # Put most recent first within each status
    active = [a for a in all_items if a["status"] == "active"]
    upcoming = [a for a in all_items if a["status"] == "upcoming"]
    expired = [a for a in all_items if a["status"] == "expired"]
    active.sort(key=lambda x: x.get("announced_date") or "", reverse=True)
    upcoming.sort(key=lambda x: x.get("announced_date") or "", reverse=True)
    expired.sort(key=lambda x: x.get("announced_date") or "", reverse=True)
    all_items = active + upcoming + expired

    output = {
        "last_updated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total": len(all_items),
        "announcements": all_items,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"OK Saved {len(all_items)} announcements")
    print(f"   Active: {len(active)} | Upcoming: {len(upcoming)} | Expired: {len(expired)}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
