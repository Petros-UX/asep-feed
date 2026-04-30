"""
ΑΣΕΠ Feed Scraper
==================
Scrapes prokhrukseis from:
  - asep.gr (RSS + announcements page)
  - et.gr (ΦΕΚ search)
  - diavgeia.gov.gr (Διαύγεια API)

Saves results to data.json for the dashboard.

Requirements: pip install requests beautifulsoup4 feedparser
"""

import json
import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime, timedelta
import re
import os
import time

OUTPUT_FILE = "data.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ASEPFeedBot/1.0)"
}

CATEGORY_KEYWORDS = {
    "ΑΣΕΠ": ["ασεπ", "asep", "1κ/", "2κ/", "3κ/", "4κ/", "5κ/"],
    "Νοσοκομεία": ["νοσοκομε", "υγεία", "ιατρ", "νοσηλ", "εσυ", "γνα", "γνθ"],
    "Δήμοι": ["δήμο", "δημο", "ota", "οτα", "περιφέρ", "κοινοτ"],
    "Εκπαίδευση": ["παιδεία", "εκπαίδ", "σχολ", "αναπληρωτ", "υπουργείο παιδ"],
    "Δικαστικό": ["δικαστ", "πρωτοδικ", "εφετ", "ανώτατ"],
    "Στρατός": ["στρατ", "ναυτ", "αεροπορ", "ενοπλ"],
    "Τράπεζες": ["τράπεζ", "τραπεζ", "αγροτ", "εθνική τράπ"],
    "ΟΤΑ": ["ota", "οτα", "τοπική αυτ", "δημοτ"],
}

def detect_category(text):
    """Detect category based on keywords in text."""
    text_lower = (text or "").lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(k in text_lower for k in keywords):
            return cat
    return "Άλλο"

def detect_status(announced_date, deadline):
    """Determine announcement status."""
    now = datetime.now()
    try:
        if deadline:
            d = datetime.strptime(deadline, "%Y-%m-%d") if isinstance(deadline, str) else deadline
            if d.date() < now.date():
                return "expired"
        if announced_date:
            a = datetime.strptime(announced_date, "%Y-%m-%d") if isinstance(announced_date, str) else announced_date
            if a.date() > now.date():
                return "upcoming"
        return "active"
    except Exception:
        return "active"

def parse_date_el(text):
    """Parse Greek date strings like '15 Απριλίου 2025'."""
    months = {
        "ιανουαρίου": "01", "φεβρουαρίου": "02", "μαρτίου": "03",
        "απριλίου": "04", "μαΐου": "05", "ιουνίου": "06",
        "ιουλίου": "07", "αυγούστου": "08", "σεπτεμβρίου": "09",
        "οκτωβρίου": "10", "νοεμβρίου": "11", "δεκεμβρίου": "12",
        "ιαν": "01", "φεβ": "02", "μαρ": "03", "απρ": "04",
        "μαΐ": "05", "ιουν": "06", "ιουλ": "07", "αυγ": "08",
        "σεπτ": "09", "οκτ": "10", "νοε": "11", "δεκ": "12",
    }
    if not text:
        return None
    text = text.strip().lower()
    for m_el, m_num in months.items():
        if m_el in text:
            parts = re.findall(r'\d+', text)
            if len(parts) >= 2:
                day = parts[0].zfill(2)
                year = parts[-1] if len(parts[-1]) == 4 else datetime.now().year
                return f"{year}-{m_num}-{day}"
    # Try ISO format
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        return m.group(0)
    return None

# ──────────────────────────────────────────────
# Source 1: ΑΣΕΠ RSS Feed
# ──────────────────────────────────────────────
def scrape_asep_rss():
    """Fetch announcements from ΑΣΕΠ RSS feed."""
    announcements = []
    rss_urls = [
        "https://www.asep.gr/webcenter/portal/asepp/rss",
        "https://www.asep.gr/rss",
    ]

    for url in rss_urls:
        try:
            print(f"  → Fetching RSS: {url}")
            feed = feedparser.parse(url)
            if not feed.entries:
                continue

            for entry in feed.entries[:20]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                summary = entry.get("summary", "")
                pub_date = entry.get("published_parsed")

                announced = None
                if pub_date:
                    announced = datetime(*pub_date[:3]).strftime("%Y-%m-%d")

                # Try to extract deadline from summary
                deadline = None
                deadline_match = re.search(
                    r'(\d{1,2})[./](\d{1,2})[./](\d{4})',
                    summary
                )
                if deadline_match:
                    d, m, y = deadline_match.groups()
                    deadline = f"{y}-{m.zfill(2)}-{d.zfill(2)}"

                # Positions
                pos_match = re.search(r'(\d+)\s*θέσ', summary + title, re.IGNORECASE)
                positions = int(pos_match.group(1)) if pos_match else None

                # Tags from title
                tags = []
                for t in ["ΠΕ", "ΤΕ", "ΔΕ", "ΥΕ", "ΙΔΑΧ", "ΙΔΟΧ", "Μόνιμο", "Αναπληρωτές"]:
                    if t.lower() in (title + summary).lower():
                        tags.append(t)

                ann = {
                    "id": f"asep-rss-{abs(hash(title))}",
                    "title": title,
                    "organization": "ΑΣΕΠ",
                    "category": detect_category(title + summary),
                    "status": detect_status(announced, deadline),
                    "announced_date": announced,
                    "deadline": deadline,
                    "positions": positions,
                    "fek": None,
                    "tags": tags,
                    "url": link,
                    "source": "asep_rss",
                }
                announcements.append(ann)

            if announcements:
                print(f"    ✓ Found {len(announcements)} from RSS")
                return announcements

        except Exception as e:
            print(f"    ✗ RSS error: {e}")
            continue

    return announcements


# ──────────────────────────────────────────────
# Source 2: ΑΣΕΠ Website Scraper
# ──────────────────────────────────────────────
def scrape_asep_website():
    """Scrape announcements from ΑΣΕΠ website."""
    announcements = []
    urls = [
        "https://www.asep.gr/webcenter/portal/asepp/announcements",
        "https://www.asep.gr/el/prokhrukseis",
    ]

    for url in urls:
        try:
            print(f"  → Scraping ΑΣΕΠ: {url}")
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")

            # Look for announcement entries in various HTML structures
            entries = (
                soup.find_all("div", class_=re.compile(r"announcement|prokhruksi|result|item", re.I)) or
                soup.find_all("li", class_=re.compile(r"announcement|result", re.I)) or
                soup.find_all("tr", class_=re.compile(r"row|item", re.I))
            )

            for entry in entries[:30]:
                title_el = entry.find(["h2", "h3", "h4", "a", "span"], class_=re.compile(r"title|heading", re.I))
                if not title_el:
                    title_el = entry.find("a")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                if len(title) < 10:
                    continue

                link = title_el.get("href", "") if title_el.name == "a" else ""
                if link and not link.startswith("http"):
                    link = "https://www.asep.gr" + link

                text = entry.get_text(" ", strip=True)

                # ΦΕΚ
                fek_match = re.search(r'ΦΕΚ\s*(\d+\s*/\s*[ΑΒΓ])', text)
                fek = fek_match.group(1).replace(" ", "") if fek_match else None

                # Dates
                dates = re.findall(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', text)
                announced = None
                deadline = None
                if dates:
                    d0 = f"{dates[0][2]}-{dates[0][1].zfill(2)}-{dates[0][0].zfill(2)}"
                    announced = d0
                    if len(dates) > 1:
                        d1 = f"{dates[1][2]}-{dates[1][1].zfill(2)}-{dates[1][0].zfill(2)}"
                        deadline = d1

                # Positions
                pos_match = re.search(r'(\d+)\s*θέσ', text, re.IGNORECASE)
                positions = int(pos_match.group(1)) if pos_match else None

                tags = []
                for t in ["ΠΕ", "ΤΕ", "ΔΕ", "ΥΕ", "ΙΔΑΧ", "ΙΔΟΧ", "Μόνιμο"]:
                    if t in text:
                        tags.append(t)

                announcements.append({
                    "id": f"asep-web-{abs(hash(title))}",
                    "title": title,
                    "organization": "ΑΣΕΠ",
                    "category": detect_category(title + text),
                    "status": detect_status(announced, deadline),
                    "announced_date": announced,
                    "deadline": deadline,
                    "positions": positions,
                    "fek": fek,
                    "tags": tags,
                    "url": link,
                    "source": "asep_web",
                })

            if announcements:
                print(f"    ✓ Found {len(announcements)} from website")
                return announcements

        except Exception as e:
            print(f"    ✗ Website error: {e}")

    return announcements


# ──────────────────────────────────────────────
# Source 3: Διαύγεια API
# ──────────────────────────────────────────────
def scrape_diavgeia():
    """Fetch recent prokhrukseis from Διαύγεια API."""
    announcements = []
    try:
        print("  → Fetching Διαύγεια API...")
        # Search for ΑΣΕΠ decisions in Διαύγεια
        url = "https://diavgeia.gov.gr/opendata/search.json"
        params = {
            "q": "προκήρυξη ΑΣΕΠ",
            "size": 20,
            "sort": "recent",
            "decisionTypeUid": "Π",  # Proclamation type
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return announcements

        data = r.json()
        decisions = data.get("decisions", {}).get("decision", [])

        for d in decisions[:20]:
            title = d.get("subject", "").strip()
            if not title or len(title) < 10:
                continue

            ada = d.get("ada", "")
            issue_date = d.get("issueDate", "")[:10] if d.get("issueDate") else None
            org_name = d.get("organizationLabel", "") or d.get("signerInfo", {}).get("firstName", "")

            link = f"https://diavgeia.gov.gr/decision/view/{ada}" if ada else ""

            announcements.append({
                "id": f"diavgeia-{ada or abs(hash(title))}",
                "title": title,
                "organization": org_name or "Δημόσιος Φορέας",
                "category": detect_category(title + org_name),
                "status": detect_status(issue_date, None),
                "announced_date": issue_date,
                "deadline": None,
                "positions": None,
                "fek": None,
                "tags": ["Διαύγεια"],
                "url": link,
                "source": "diavgeia",
            })

        print(f"    ✓ Found {len(announcements)} from Διαύγεια")

    except Exception as e:
        print(f"    ✗ Διαύγεια error: {e}")

    return announcements


# ──────────────────────────────────────────────
# Deduplication
# ──────────────────────────────────────────────
def deduplicate(announcements):
    """Remove duplicate announcements by title similarity."""
    seen = set()
    unique = []
    for a in announcements:
        key = re.sub(r'\s+', ' ', a["title"].lower().strip())[:80]
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    print("=" * 50)
    print("ΑΣΕΠ Feed Scraper")
    print(f"Starting at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    all_announcements = []

    print("\n[1/3] ΑΣΕΠ RSS Feed...")
    rss = scrape_asep_rss()
    all_announcements.extend(rss)
    time.sleep(1)

    if len(all_announcements) < 3:
        print("\n[2/3] ΑΣΕΠ Website...")
        web = scrape_asep_website()
        all_announcements.extend(web)
        time.sleep(1)

    print("\n[3/3] Διαύγεια API...")
    diav = scrape_diavgeia()
    all_announcements.extend(diav)

    # Deduplicate
    all_announcements = deduplicate(all_announcements)

    # Sort: active first, then by deadline
    def sort_key(a):
        order = {"active": 0, "upcoming": 1, "expired": 2}
        return (order.get(a["status"], 3), a.get("deadline") or "9999-99-99")

    all_announcements.sort(key=sort_key)

    # Build output
    output = {
        "last_updated": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total": len(all_announcements),
        "announcements": all_announcements,
    }

    # Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Done! Saved {len(all_announcements)} announcements to {OUTPUT_FILE}")
    active = sum(1 for a in all_announcements if a["status"] == "active")
    upcoming = sum(1 for a in all_announcements if a["status"] == "upcoming")
    expired = sum(1 for a in all_announcements if a["status"] == "expired")
    print(f"   Ενεργές: {active} | Ερχόμενες: {upcoming} | Ληγμένες: {expired}")


if __name__ == "__main__":
    main()
