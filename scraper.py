"""
ASEP Feed Scraper - v10
Sources (in order of preference):
  1. info.asep.gr RSS feed
  2. info.asep.gr HTML with session/cookies
  3. Diavgeia API fallback (ASEP queries only)
"""

import json
import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime
import re
import time

OUTPUT_FILE = "data.json"
BASE_URL = "https://info.asep.gr"

# Very realistic browser headers
HEADERS_HTML = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "el-GR,el;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

HEADERS_RSS = {
    "User-Agent": "Mozilla/5.0 (compatible; FeedFetcher-Google)",
    "Accept": "application/rss+xml, application/xml, text/xml",
}

CATEGORY_MAP = {
    "1\u03ba/": "\u0391\u03a3\u0395\u03a0", "2\u03ba/": "\u0391\u03a3\u0395\u03a0",
    "3\u03ba/": "\u0391\u03a3\u0395\u03a0", "4\u03ba/": "\u0391\u03a3\u0395\u03a0",
    "5\u03ba/": "\u0391\u03a3\u0395\u03a0",
    "1\u03b3\u03b5/": "\u0391\u03a3\u0395\u03a0", "2\u03b3\u03b5/": "\u0391\u03a3\u0395\u03a0",
    "1\u03b3/": "\u0391\u03a3\u0395\u03a0", "2\u03b3/": "\u0391\u03a3\u0395\u03a0",
    "\u03bd\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03b9\u03b1\u03c4\u03c1": "\u039d\u03bf\u03c3\u03bf\u03ba\u03bf\u03bc\u03b5\u03af\u03b1",
    "\u03b4\u03ae\u03bc\u03bf": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03c0\u03b5\u03c1\u03b9\u03c6\u03ad\u03c1": "\u0394\u03ae\u03bc\u03bf\u03b9",
    "\u03c0\u03b1\u03b9\u03b4\u03b5\u03af\u03b1": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03b1\u03bd\u03b1\u03c0\u03bb\u03b7\u03c1\u03c9\u03c4": "\u0395\u03ba\u03c0\u03b1\u03af\u03b4\u03b5\u03c5\u03c3\u03b7",
    "\u03b4\u03b9\u03ba\u03b1\u03c3\u03c4": "\u0394\u03b9\u03ba\u03b1\u03c3\u03c4\u03b9\u03ba\u03cc",
    "\u03c3\u03c4\u03c1\u03b1\u03c4": "\u03a3\u03c4\u03c1\u03b1\u03c4\u03cc\u03c2",
}

def detect_category(text):
    t = (text or "").lower()
    for kw, cat in CATEGORY_MAP.items():
        if kw in t:
            return cat
    return "\u0391\u03a3\u0395\u03a0"

def detect_status(date_str):
    now = datetime.now()
    try:
        if date_str:
            d = datetime.strptime(date_str[:10], "%Y-%m-%d")
            if d.date() > now.date():
                return "upcoming"
        return "active"
    except Exception:
        return "active"

def parse_greek_date(text):
    if not text:
        return None
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', text)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    return None

def extract_tags(title):
    tags = ["\u0391\u03a3\u0395\u03a0"]
    for tag in ["\u03a0\u0395","\u03a4\u0395","\u0394\u0395","\u03a5\u0395",
                "\u0399\u0394\u0391\u03a7","\u0399\u0394\u039f\u03a7",
                "\u03a3\u039f\u03a7","\u03a3\u039c\u0395"]:
        if tag.lower() in title.lower():
            tags.append(tag)
    return tags

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
# Source 1: info.asep.gr RSS feeds
# ─────────────────────────────────────────────
RSS_URLS = [
    "https://info.asep.gr/rss.xml",
    "https://info.asep.gr/announcements-list/7846/feed",
    "https://info.asep.gr/feed",
    "https://info.asep.gr/announcements-list/feed",
    "https://info.asep.gr/taxonomy/term/7846/feed",
]

def scrape_rss():
    items = []
    for url in RSS_URLS:
        try:
            print(f"  -> RSS: {url}")
            feed = feedparser.parse(url)
            if not feed.entries:
                print(f"    x Empty or error")
                continue
            print(f"    OK {len(feed.entries)} entries!")
            for entry in feed.entries[:50]:
                title = entry.get("title", "").strip()
                if not title:
                    continue
                link = entry.get("link", "")
                pub = entry.get("published_parsed")
                announced = datetime(*pub[:3]).strftime("%Y-%m-%d") if pub else None
                pos_m = re.search(r'(\d[\d\.]*)\s*\u03b8\u03ad\u03c3', title, re.I)
                positions = int(pos_m.group(1).replace(".", "")) if pos_m else None
                items.append({
                    "id": f"asep-rss-{abs(hash(title))}",
                    "title": title,
                    "organization": "\u0391\u03a3\u0395\u03a0",
                    "category": detect_category(title),
                    "status": detect_status(announced),
                    "announced_date": announced,
                    "deadline": None,
                    "positions": positions,
                    "fek": None,
                    "tags": extract_tags(title),
                    "url": link,
                    "source": "info.asep.gr",
                })
            if items:
                return items
        except Exception as e:
            print(f"    x Error: {e}")
    return items


# ─────────────────────────────────────────────
# Source 2: info.asep.gr HTML with session
# ─────────────────────────────────────────────
def scrape_html_with_session(max_pages=5):
    items = []
    session = requests.Session()

    # First visit homepage to get cookies
    try:
        print("  -> Getting session cookies from homepage...")
        session.get(BASE_URL, headers=HEADERS_HTML, timeout=15)
        time.sleep(1)
    except Exception as e:
        print(f"    x Homepage error: {e}")

    for page in range(max_pages):
        url = f"{BASE_URL}/announcements-list/7846" if page == 0 else f"{BASE_URL}/announcements-list/7846?page={page}"
        try:
            print(f"  -> HTML page {page+1}: {url}")
            headers = {**HEADERS_HTML, "Referer": BASE_URL + "/"}
            r = session.get(url, headers=headers, timeout=20)
            print(f"    HTTP {r.status_code}")
            if r.status_code != 200:
                break

            soup = BeautifulSoup(r.text, "html.parser")
            page_items = 0

            for h3 in soup.find_all("h3"):
                title = h3.get_text(strip=True)
                if len(title) < 5:
                    continue

                # Find link
                link = ""
                a_tag = h3.find("a")
                if not a_tag:
                    parent = h3.find_parent(["div", "article", "li"])
                    if parent:
                        a_tag = parent.find("a", href=re.compile(r"/node/"))
                if a_tag:
                    href = a_tag.get("href", "")
                    if href and not href.startswith("http"):
                        href = BASE_URL + href
                    link = href

                # Find date
                date_str = None
                parent = h3.find_parent(["div", "article", "li", "section"])
                if parent:
                    text = parent.get_text(" ", strip=True)
                    date_str = parse_greek_date(text)

                pos_m = re.search(r'(\d[\d\.]*)\s*\u03b8\u03ad\u03c3', title, re.I)
                positions = int(pos_m.group(1).replace(".", "")) if pos_m else None

                items.append({
                    "id": f"asep-html-{abs(hash(title + (date_str or '')))}",
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
                page_items += 1

            print(f"    OK {page_items} items on page")
            if page_items == 0:
                break
            time.sleep(1.5)

        except Exception as e:
            print(f"    x Error: {e}")
            break

    return items


# ─────────────────────────────────────────────
# Source 3: Diavgeia fallback (ASEP only)
# ─────────────────────────────────────────────
def scrape_diavgeia_fallback():
    items = []
    print("  -> Diavgeia fallback: ASEP prokhrukseis...")
    try:
        r = requests.get(
            "https://diavgeia.gov.gr/opendata/search.json",
            params={"q": "\u0391\u03a3\u0395\u03a0 \u03c0\u03c1\u03bf\u03ba\u03ae\u03c1\u03c5\u03be\u03b7", "size": 20, "sort": "recent"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20
        )
        if r.status_code != 200:
            print(f"    x HTTP {r.status_code}")
            return items

        data = r.json()
        decisions = []
        if isinstance(data, list):
            decisions = data
        elif isinstance(data, dict):
            for key in ["decisions", "decisionList", "results", "items"]:
                val = data.get(key)
                if isinstance(val, list):
                    decisions = val; break
                elif isinstance(val, dict):
                    for sk in ["decision", "items", "list"]:
                        sv = val.get(sk)
                        if isinstance(sv, list):
                            decisions = sv; break
                    if decisions: break

        EXCLUDE = ["\u03c0\u03bb\u03b7\u03c1\u03c9\u03bc\u03ae\u03c2","\u03b1\u03ba\u03af\u03bd\u03b7\u03c4",
                   "\u03bc\u03af\u03c3\u03b8\u03c9\u03c3","\u03b5\u03b9\u03c3\u03c6\u03bf\u03c1\u03ac",
                   "\u03b4\u03b1\u03c0\u03ac\u03bd\u03b7","\u03c0\u03b1\u03c1\u03ac\u03c4\u03b1\u03c3\u03b7",
                   "\u03c3\u03c5\u03b3\u03ba\u03c1\u03cc\u03c4\u03b7\u03c3\u03b7 \u03b5\u03c0\u03b9\u03c4\u03c1\u03bf\u03c0"]

        for d in decisions:
            if not isinstance(d, dict): continue
            title = ""
            for key in ["subject","title","label"]:
                val = d.get(key)
                if val and isinstance(val, str) and len(val.strip()) > 5:
                    title = val.strip(); break
            if not title: continue
            if any(kw.lower() in title.lower() for kw in EXCLUDE): continue

            ada = d.get("ada","")
            issue_date = None
            for dk in ["issueDate","submissionTimestamp"]:
                val = d.get(dk)
                if val and isinstance(val, str): issue_date = val[:10]; break
                elif val and isinstance(val,(int,float)) and val>1e9:
                    try: issue_date = datetime.fromtimestamp(int(val)/1000).strftime("%Y-%m-%d"); break
                    except: pass

            org = ""
            for ok in ["organizationLabel","unitLabel","signerLabel"]:
                val = d.get(ok)
                if val and isinstance(val,str): org = val.strip(); break

            items.append({
                "id": f"diav-{ada or abs(hash(title))}",
                "title": title,
                "organization": org or "\u0391\u03a3\u0395\u03a0",
                "category": detect_category(title),
                "status": detect_status(issue_date),
                "announced_date": issue_date,
                "deadline": None, "positions": None, "fek": None,
                "tags": ["\u0394\u03b9\u03b1\u03cd\u03b3\u03b5\u03b9\u03b1","\u0391\u03a3\u0395\u03a0"],
                "url": f"https://diavgeia.gov.gr/decision/view/{ada}" if ada else "",
                "source": "diavgeia",
            })

        print(f"    OK {len(items)} from Diavgeia")
    except Exception as e:
        print(f"    x Error: {e}")
    return items


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    print("="*50)
    print("ASEP Feed Scraper v10")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*50)

    all_items = []

    # Try RSS first
    print("\n[1/3] RSS feeds...")
    rss_items = scrape_rss()
    all_items.extend(rss_items)
    print(f"  RSS total: {len(rss_items)}")

    # Try HTML with session
    if len(all_items) < 5:
        print("\n[2/3] HTML with session...")
        html_items = scrape_html_with_session(max_pages=5)
        all_items.extend(html_items)
        print(f"  HTML total: {len(html_items)}")
    else:
        print("\n[2/3] Skipping HTML (RSS sufficient)")

    # Fallback to Diavgeia
    if len(all_items) < 5:
        print("\n[3/3] Diavgeia fallback...")
        diav_items = scrape_diavgeia_fallback()
        all_items.extend(diav_items)
    else:
        print("\n[3/3] Skipping Diavgeia (enough data)")

    all_items = deduplicate(all_items)

    active   = sorted([a for a in all_items if a["status"]=="active"],
                      key=lambda x: x.get("announced_date") or "", reverse=True)
    upcoming = sorted([a for a in all_items if a["status"]=="upcoming"],
                      key=lambda x: x.get("announced_date") or "", reverse=True)
    expired  = sorted([a for a in all_items if a["status"]=="expired"],
                      key=lambda x: x.get("announced_date") or "", reverse=True)

    all_items = active + upcoming + expired

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "last_updated": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "total": len(all_items),
            "announcements": all_items,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"OK Saved {len(all_items)} announcements")
    print(f"   Active: {len(active)} | Upcoming: {len(upcoming)} | Expired: {len(expired)}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
