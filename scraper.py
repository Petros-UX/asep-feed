"""
ASEP Feed Scraper - v9
Scrapes directly from info.asep.gr/announcements-list/7846
This is the official ASEP announcements page - 100% relevant results!
"""

import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time

OUTPUT_FILE = "data.json"

BASE_URL = "https://info.asep.gr"
ANNOUNCEMENTS_URL = f"{BASE_URL}/announcements-list/7846"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "el-GR,el;q=0.9",
}

CATEGORY_MAP = {
    "1\u03ba/": "\u0391\u03a3\u0395\u03a0", "2\u03ba/": "\u0391\u03a3\u0395\u03a0",
    "3\u03ba/": "\u0391\u03a3\u0395\u03a0", "4\u03ba/": "\u0391\u03a3\u0395\u03a0",
    "5\u03ba/": "\u0391\u03a3\u0395\u03a0",
    "1\u03b3\u03b5/": "\u0391\u03a3\u0395\u03a0", "2\u03b3\u03b5/": "\u0391\u03a3\u0395\u03a0",
    "1\u03b3\u03b2/": "\u0391\u03a3\u0395\u03a0", "1\u03b4\u03b1/": "\u0391\u03a3\u0395\u03a0",
    "1\u03b3/": "\u0391\u03a3\u0395\u03a0", "2\u03b3/": "\u0391\u03a3\u0395\u03a0",
    "\u03bd\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03b9\u03b1\u03c4\u03c1": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03bd\u03bf\u03c3\u03b7\u03bb": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03b4\u03ae\u03bc\u03bf": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03b4\u03b7\u03bc\u03bf": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03c0\u03b5\u03c1\u03b9\u03c6\u03ad\u03c1": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03c0\u03b1\u03b9\u03b4\u03b5\u03af\u03b1": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03b5\u03ba\u03c0\u03b1\u03af\u03b4": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
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
    return "\u0391\u03a3\u0395\u03a0"  # Default: ΑΣΕΠ (since all come from ASEP site)

def detect_status(date_str):
    """All current announcements are active."""
    now = datetime.now()
    try:
        if date_str:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            if d.date() > now.date():
                return "upcoming"
        return "active"
    except Exception:
        return "active"

def parse_greek_date(text):
    """Parse date like '28/04/2026' or '28/04/2026 - 12:07'"""
    if not text:
        return None
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    return None

def extract_tags(title):
    tags = ["\u0391\u03a3\u0395\u03a0"]
    t = title.upper()
    for tag in ["\u03a0\u0395", "\u03a4\u0395", "\u0394\u0395", "\u03a5\u0395",
                "\u0399\u0394\u0391\u03a7", "\u0399\u0394\u039f\u03a7", "\u03a3\u039f\u03a7", "\u03a3\u039c\u0395"]:
        if tag in t:
            tags.append(tag)
    return tags

def scrape_page(url):
    """Scrape a single page of announcements."""
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"    x HTTP {r.status_code} for {url}")
            return items, False

        soup = BeautifulSoup(r.text, "html.parser")

        # Find announcement entries
        # Structure: h3 with title inside an article/div, with date nearby
        entries = []

        # Try finding h3 tags with announcement titles
        for h3 in soup.find_all("h3"):
            title = h3.get_text(strip=True)
            if len(title) < 5:
                continue

            # Find link
            link = ""
            a_tag = h3.find("a") or h3.find_parent("a")
            if not a_tag:
                # Look for sibling or nearby link
                parent = h3.find_parent(["div", "article", "li"])
                if parent:
                    a_tag = parent.find("a", href=re.compile(r"/node/"))
            if a_tag:
                href = a_tag.get("href", "")
                if href and not href.startswith("http"):
                    href = BASE_URL + href
                link = href

            # Find date - look near the h3
            date_str = None
            parent = h3.find_parent(["div", "article", "li", "section"])
            if parent:
                # Look for date text nearby
                text = parent.get_text(" ", strip=True)
                date_str = parse_greek_date(text)

            entries.append({
                "title": title,
                "link": link,
                "date": date_str,
            })

        print(f"    -> Found {len(entries)} entries on page")

        for e in entries:
            title = e["title"]
            link = e["link"]
            date_str = e["date"]

            # Extract positions from title
            pos_m = re.search(r'(\d[\d\.]*)\s*\u03b8\u03ad\u03c3', title, re.I)
            positions = None
            if pos_m:
                try:
                    positions = int(pos_m.group(1).replace(".", ""))
                except Exception:
                    pass

            items.append({
                "id": f"asep-{abs(hash(title + (date_str or '')))}",
                "title": title,
                "organization": "\u0391\u03a3\u0395\u03a0",
                "category": detect_category(title),
                "status": detect_status(date_str),
                "announced_date": date_str,
                "deadline": None,
                "positions": positions,
                "fek": None,
                "tags": extract_tags(title),
                "url": link,
                "source": "info.asep.gr",
            })

        # Check if there's a next page
        has_next = bool(soup.find("a", string=re.compile(r"Επόμενο|Next")))
        return items, has_next

    except Exception as e:
        print(f"    x Error scraping {url}: {e}")
        import traceback
        traceback.print_exc()
        return items, False


def scrape_asep_info(max_pages=5):
    """Scrape multiple pages from info.asep.gr"""
    all_items = []
    seen_ids = set()

    for page in range(max_pages):
        url = ANNOUNCEMENTS_URL if page == 0 else f"{ANNOUNCEMENTS_URL}?page={page}"
        print(f"  -> Page {page + 1}: {url}")

        items, has_next = scrape_page(url)

        for item in items:
            uid = item["id"]
            if uid not in seen_ids:
                seen_ids.add(uid)
                all_items.append(item)

        print(f"    OK {len(items)} items | Total so far: {len(all_items)}")

        if not has_next:
            print(f"    -> No more pages")
            break

        time.sleep(1)

    return all_items


def main():
    print("=" * 50)
    print("ASEP Feed Scraper v9")
    print("Source: info.asep.gr (official ASEP portal)")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    print(f"\nScraping {ANNOUNCEMENTS_URL} ...")
    items = scrape_asep_info(max_pages=5)  # Get up to 5 pages = ~50 announcements

    # Sort: most recent first
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
    print(f"OK Saved {len(all_items)} announcements from info.asep.gr")
    print(f"   Active: {len(active)} | Upcoming: {len(upcoming)} | Expired: {len(expired)}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
