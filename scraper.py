"""
ΑΣΕΠ Feed Scraper - v2 (Fixed)
================================
Fixes:
  - Diavgeia API: correct JSON structure parsing
  - ASEP: longer timeout + more URL attempts
  - RSS: updated feed URLs
"""

import json
import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime
import re
import time

OUTPUT_FILE = "data.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

CATEGORY_KEYWORDS = {
    "ΑΣΕΠ": ["ασεπ", "asep", "1κ/", "2κ/", "3κ/", "4κ/", "5κ/"],
    "Νοσοκομεία": ["νοσοκομε", "υγεία", "ιατρ", "νοσηλ", "εσυ", "γνα", "γνθ"],
    "Δήμοι": ["δήμο", "δημο", "περιφέρ", "κοινοτ"],
    "Εκπαίδευση": ["παιδεία", "εκπαίδ", "σχολ", "αναπληρωτ"],
    "Δικαστικό": ["δικαστ", "πρωτοδικ", "εφετ"],
    "Στρατός": ["στρατ", "ναυτ", "αεροπορ", "ενοπλ"],
    "Τράπεζες": ["τράπεζ", "αγροτ", "εθνική τράπ"],
}

def detect_category(text):
    text_lower = (text or "").lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(k in text_lower for k in keywords):
            return cat
    return "Άλλο"

def detect_status(announced_date, deadline):
    now = datetime.now()
    try:
        if deadline:
            d = datetime.strptime(deadline, "%Y-%m-%d")
            if d.date() < now.date():
                return "expired"
        if announced_date:
            a = datetime.strptime(announced_date, "%Y-%m-%d")
            if a.date() > now.date():
                return "upcoming"
        return "active"
    except Exception:
        return "active"

def deduplicate(announcements):
    seen = set()
    unique = []
    for a in announcements:
        key = re.sub(r'\s+', ' ', a["title"].lower().strip())[:80]
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


# ──────────────────────────────────────────────
# Source 1: ΑΣΕΠ RSS
# ──────────────────────────────────────────────
def scrape_asep_rss():
    announcements = []
    rss_urls = [
        "https://www.asep.gr/webcenter/portal/asepp/rss",
        "https://www.asep.gr/rss",
        "https://www.asep.gr/webcenter/faces/rss",
        "https://www.asep.gr/el/rss",
    ]
    for url in rss_urls:
        try:
            print(f"  -> RSS: {url}")
            feed = feedparser.parse(url)
            if not feed.entries:
                print(f"    x Keno feed")
                continue
            for entry in feed.entries[:20]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                pub = entry.get("published_parsed")
                announced = datetime(*pub[:3]).strftime("%Y-%m-%d") if pub else None

                deadline = None
                m = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', summary)
                if m:
                    d, mo, y = m.groups()
                    deadline = f"{y}-{mo.zfill(2)}-{d.zfill(2)}"

                pos_m = re.search(r'(\d+)\s*thethmorphs', summary + title, re.I)
                positions = int(pos_m.group(1)) if pos_m else None

                tags = [t for t in ["PE","TE","DE","YE","IDAX","IDOX","Monimon"]
                        if t.lower() in (title+summary).lower()]

                announcements.append({
                    "id": f"rss-{abs(hash(title))}",
                    "title": title,
                    "organization": "ASEP",
                    "category": detect_category(title + summary),
                    "status": detect_status(announced, deadline),
                    "announced_date": announced,
                    "deadline": deadline,
                    "positions": positions,
                    "fek": None,
                    "tags": tags,
                    "url": link,
                    "source": "asep_rss",
                })
            if announcements:
                print(f"    OK {len(announcements)} anakoinoseis")
                return announcements
        except Exception as e:
            print(f"    x Sfalma: {e}")
    return announcements


# ──────────────────────────────────────────────
# Source 2: ΑΣΕΠ Website (increased timeout)
# ──────────────────────────────────────────────
def scrape_asep_website():
    announcements = []
    urls = [
        "https://www.asep.gr/webcenter/portal/asepp/announcements",
        "https://www.asep.gr/el/prokhrukseis",
        "https://www.asep.gr",
    ]
    for url in urls:
        try:
            print(f"  -> ASEP Website: {url}")
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                print(f"    x HTTP {r.status_code}")
                continue
            soup = BeautifulSoup(r.text, "html.parser")

            entries = (
                soup.find_all("div", class_=re.compile(r"announcement|prokhruksi|result|item|news", re.I)) or
                soup.find_all("li", class_=re.compile(r"announcement|result|news", re.I)) or
                soup.find_all("article")
            )

            for entry in entries[:30]:
                title_el = (
                    entry.find(["h2","h3","h4"], class_=re.compile(r"title|heading", re.I)) or
                    entry.find("a")
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if len(title) < 10:
                    continue

                link = title_el.get("href","") if title_el.name == "a" else ""
                if link and not link.startswith("http"):
                    link = "https://www.asep.gr" + link

                text = entry.get_text(" ", strip=True)
                fek_m = re.search(r'FEK\s*(\d+\s*/\s*[ABG])', text)
                fek = fek_m.group(1).replace(" ","") if fek_m else None

                dates = re.findall(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', text)
                announced = deadline = None
                if dates:
                    announced = f"{dates[0][2]}-{dates[0][1].zfill(2)}-{dates[0][0].zfill(2)}"
                    if len(dates) > 1:
                        deadline = f"{dates[1][2]}-{dates[1][1].zfill(2)}-{dates[1][0].zfill(2)}"

                pos_m = re.search(r'(\d+)\s*thes', text, re.I)
                positions = int(pos_m.group(1)) if pos_m else None

                announcements.append({
                    "id": f"web-{abs(hash(title))}",
                    "title": title,
                    "organization": "ASEP",
                    "category": detect_category(title + text),
                    "status": detect_status(announced, deadline),
                    "announced_date": announced,
                    "deadline": deadline,
                    "positions": positions,
                    "fek": fek,
                    "tags": [],
                    "url": link,
                    "source": "asep_web",
                })
            if announcements:
                print(f"    OK {len(announcements)} anakoinoseis")
                return announcements
        except Exception as e:
            print(f"    x Sfalma: {e}")
    return announcements


# ──────────────────────────────────────────────
# Source 3: Diavgeia API (FIXED)
# ──────────────────────────────────────────────
def scrape_diavgeia():
    announcements = []
    queries = [
        "ASEP prokhruksh plhrosh thesewn",
        "prokhruksh proslhpsh monimou proswpikou",
        "prokhruksh IDAX IDOX",
    ]

    # Use Greek queries encoded properly
    greek_queries = [
        "\u0391\u03a3\u0395\u03a0 \u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03c0\u03bb\u03ae\u03c1\u03c9\u03c3\u03b7 \u03b8\u03ad\u03c3\u03b5\u03c9\u03bd",
        "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u03c0\u03c1\u03cc\u03c3\u03bb\u03b7\u03c8\u03b7 \u03bc\u03cc\u03bd\u03b9\u03bc\u03bf\u03c5 \u03c0\u03c1\u03bf\u03c3\u03c9\u03c0\u03b9\u03ba\u03bf\u03cd",
        "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7 \u0399\u0394\u0391\u03a7 \u0399\u0394\u039f\u03a7",
    ]

    for query in greek_queries:
        try:
            print(f"  -> Diavgeia: searching...")
            url = "https://diavgeia.gov.gr/opendata/search.json"
            params = {
                "q": query,
                "size": 20,
                "sort": "recent",
            }
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                print(f"    x HTTP {r.status_code}")
                continue

            data = r.json()
            print(f"    -> Response type: {type(data).__name__}")

            # FIXED: handle all possible response structures
            decisions = []
            if isinstance(data, list):
                decisions = data
            elif isinstance(data, dict):
                for key in ["decisions", "decisionList", "results", "items", "data"]:
                    val = data.get(key)
                    if val is not None:
                        if isinstance(val, list):
                            decisions = val
                            break
                        elif isinstance(val, dict):
                            for subkey in ["decision", "items", "list"]:
                                subval = val.get(subkey)
                                if isinstance(subval, list):
                                    decisions = subval
                                    break
                        if decisions:
                            break

            print(f"    -> Found {len(decisions)} decisions")

            for d in decisions[:20]:
                if not isinstance(d, dict):
                    continue

                title = ""
                for key in ["subject", "title", "decisionTypeName", "label"]:
                    val = d.get(key)
                    if val and isinstance(val, str) and len(val) > 5:
                        title = val.strip()
                        break

                if not title or len(title) < 10:
                    continue

                # Keep only prokhrukseis-related
                title_lower = title.lower()
                relevant_words = [
                    "\u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be",
                    "\u03c0\u03c1\u03cc\u03c3\u03bb\u03b7\u03c8",
                    "\u03c0\u03bb\u03ae\u03c1\u03c9\u03c3",
                    "\u03b8\u03ad\u03c3\u03b5",
                    "asep", "\u03b1\u03c3\u03b5\u03c0"
                ]
                if not any(k in title_lower for k in relevant_words):
                    continue

                ada = d.get("ada") or d.get("protocolNumber") or ""
                issue_date = ""
                for dk in ["issueDate", "submissionTimestamp", "publishDate", "date"]:
                    val = d.get(dk)
                    if val and isinstance(val, str):
                        issue_date = val[:10]
                        break
                    elif val and isinstance(val, (int, float)):
                        # epoch milliseconds
                        try:
                            issue_date = datetime.fromtimestamp(val/1000).strftime("%Y-%m-%d")
                        except Exception:
                            pass
                        break

                org = ""
                for ok in ["organizationLabel", "unitLabel", "signerLabel", "issuerLabel"]:
                    val = d.get(ok)
                    if val and isinstance(val, str):
                        org = val
                        break
                if not org:
                    org = "\u0394\u03b7\u03bc\u03cc\u03c3\u03b9\u03bf\u03c2 \u03a6\u03bf\u03c1\u03ad\u03b1\u03c2"

                link = f"https://diavgeia.gov.gr/decision/view/{ada}" if ada else ""

                pos_m = re.search(r'(\d+)\s*\u03b8\u03ad\u03c3', title, re.I)
                positions = int(pos_m.group(1)) if pos_m else None

                tags = ["\u0394\u03b9\u03b1\u03cd\u03b3\u03b5\u03b9\u03b1"]

                announcements.append({
                    "id": f"diav-{ada or abs(hash(title))}",
                    "title": title,
                    "organization": org,
                    "category": detect_category(title + org),
                    "status": detect_status(issue_date if issue_date else None, None),
                    "announced_date": issue_date if issue_date else None,
                    "deadline": None,
                    "positions": positions,
                    "fek": None,
                    "tags": tags,
                    "url": link,
                    "source": "diavgeia",
                })

            if announcements:
                print(f"    OK {len(announcements)} anakoinoseis so far")
                break

        except Exception as e:
            print(f"    x Sfalma: {e}")
            import traceback
            traceback.print_exc()
        time.sleep(1)

    return announcements


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    print("=" * 50)
    print("ASEP Feed Scraper v2")
    print(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    all_announcements = []

    print("\n[1/3] ASEP RSS Feed...")
    all_announcements.extend(scrape_asep_rss())
    time.sleep(2)

    if len(all_announcements) < 3:
        print("\n[2/3] ASEP Website...")
        all_announcements.extend(scrape_asep_website())
        time.sleep(2)
    else:
        print("\n[2/3] Skipping website (enough from RSS)")

    print("\n[3/3] Diavgeia API...")
    all_announcements.extend(scrape_diavgeia())

    all_announcements = deduplicate(all_announcements)

    def sort_key(a):
        order = {"active": 0, "upcoming": 1, "expired": 2}
        return (order.get(a["status"], 3), a.get("deadline") or "9999-99-99")

    all_announcements.sort(key=sort_key)

    output = {
        "last_updated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total": len(all_announcements),
        "announcements": all_announcements,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    active = sum(1 for a in all_announcements if a["status"] == "active")
    upcoming = sum(1 for a in all_announcements if a["status"] == "upcoming")
    expired = sum(1 for a in all_announcements if a["status"] == "expired")

    print(f"\n{'='*50}")
    print(f"OK Saved {len(all_announcements)} announcements to data.json")
    print(f"   Active: {active} | Upcoming: {upcoming} | Expired: {expired}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
