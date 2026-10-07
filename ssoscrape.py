"""Scrape Singapore Statutes Online (https://sso.agc.gov.sg/): the list of current Acts, and each Act's
provisions (number, title, link and text).

    python ssoscrape.py                      # every current Act (about an hour at SSO's crawl delay)
    python ssoscrape.py --limit 10           # the first 10 Acts
    python ssoscrape.py --act PC1871         # one Act by its SSO code
    python ssoscrape.py --statutes-only      # just the list of Acts
    python ssoscrape.py --act PDPA2012 --with-text   # with each provision's text

Provision text is opt-in: SSO loads an Act's text in parts (about 25 requests for a long Act), which at
the crawl delay is minutes per Act.

SSO's robots.txt asks for a 6-second crawl delay, which is the default here.
"""
import argparse
import csv
import json
import re
import time

import requests
from bs4 import BeautifulSoup

SSO = "https://sso.agc.gov.sg"
BROWSE = SSO + "/Browse/Act/Current/All{page}?PageSize=500&SortBy=Title&SortOrder=ASC"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/130.0.0.0 Safari/537.36",
}
CRAWL_DELAY = 6  # seconds, from https://sso.agc.gov.sg/robots.txt


def fetch(session, url):
    response = session.get(url, headers=HEADERS, timeout=60)
    response.raise_for_status()
    return BeautifulSoup(response.content, "html.parser")


def get_statutes(session, delay=CRAWL_DELAY, max_pages=10):
    """Every current Act as {name, code, url}. The code (e.g. PC1871) comes from SSO's own link."""
    statutes, seen = [], set()
    for page in range(max_pages):
        url = BROWSE.format(page=f"/{page}" if page else "")
        print(f"Fetching page {page + 1}: {url}")
        table = fetch(session, url).find("table", class_="browse-list")
        if not table:
            print("No statutes table found")
            break
        added = 0
        for a in table.find_all("a", class_="non-ajax", href=True):
            match = re.match(r"^/Act/([A-Za-z0-9]+)$", a["href"])
            name = a.get_text(strip=True)
            if not match or match.group(1) in seen:
                continue
            seen.add(match.group(1))
            statutes.append({"name": name, "code": match.group(1), "url": SSO + a["href"]})
            added += 1
        print(f"Added {added} statutes")
        if not added:
            break
        time.sleep(delay)
    return statutes


def act_text(session, soup, delay):
    """The Act's text, which SSO lazy-loads part by part: one request per part listed on the page."""
    toc_sys_id = None
    for block in soup.find_all("div", class_="global-vars"):  # several; the Act's own one has tocSysId
        try:
            toc_sys_id = json.loads(block["data-json"]).get("tocSysId")
        except (KeyError, ValueError):
            continue
        if toc_sys_id:
            break
    if not toc_sys_id:
        return []
    parts = []
    for div in soup.find_all("div", class_="dms", attrs={"data-field": "seriesId"}):
        time.sleep(delay)
        url = f"{SSO}/Details/GetLazyLoadContent?TocSysId={toc_sys_id}&SeriesId={div['data-term']}"
        try:
            parts.append(fetch(session, url))
        except requests.RequestException as exc:
            print(f"  part {div['data-term']} failed ({exc})")
    return parts


def provision_text(prov_id, sources):
    """A provision's text: the div.prov1 around its anchor, in whichever part holds it."""
    for source in sources:
        anchor = source.find(id=prov_id)
        if anchor:
            container = anchor.find_parent("div", class_="prov1") or anchor
            return container.get_text(" ", strip=True)
    return ""


def get_provisions(session, code, with_text=False, delay=CRAWL_DELAY):
    """An Act's provisions from its whole-document view: number, title, link and (optionally) text."""
    soup = fetch(session, f"{SSO}/Act/{code}?WholeDoc=1")
    sources = [soup] + (act_text(session, soup, delay) if with_text else [])
    toc = soup.find("div", id="tocPanel")
    provisions = []
    for link in toc.find_all("a", class_="nav-link") if toc else []:
        span = link.find("span")
        if not span:
            continue
        match = re.match(r"^(\d+[A-Z]*)\s+(.+)", span.get_text(strip=True))
        if not match:
            continue
        number, title = match.groups()
        prov_id = link.get("href", "#").split("#")[-1]
        provisions.append({
            "number": number,
            "title": title,
            "url": f"{SSO}/Act/{code}?WholeDoc=1&ProvIds={prov_id}#{prov_id}",
            "content": provision_text(prov_id, sources) if with_text else "",
        })
    return provisions


def main():
    parser = argparse.ArgumentParser(description="Scrape Acts and their provisions from Singapore Statutes Online.")
    parser.add_argument("--limit", type=int, default=0, help="Only the first N Acts (default: all).")
    parser.add_argument("--act", action="append", default=[], help="Scrape only this Act code (repeatable), e.g. PC1871.")
    parser.add_argument("--statutes-only", action="store_true", help="Write statutes.csv and stop.")
    parser.add_argument("--with-text", action="store_true", help="Also fetch each provision's text (slow: several requests per Act).")
    parser.add_argument("--delay", type=float, default=CRAWL_DELAY, help=f"Seconds between requests (default {CRAWL_DELAY}, per robots.txt).")
    parser.add_argument("--statutes-file", default="statutes.csv")
    parser.add_argument("--provisions-file", default="provisions.csv")
    args = parser.parse_args()

    session = requests.Session()
    if args.act:
        statutes = [{"name": code, "code": code, "url": f"{SSO}/Act/{code}"} for code in args.act]
    else:
        print("Retrieving statutes...")
        statutes = get_statutes(session, args.delay)
        # utf-8-sig so Excel shows the names correctly
        with open(args.statutes_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Statute", "Code", "URL"])
            writer.writerows([s["name"], s["code"], s["url"]] for s in statutes)
        print(f"Wrote {len(statutes)} statutes to {args.statutes_file}")
        if args.statutes_only:
            return
        if args.limit:
            statutes = statutes[:args.limit]

    with open(args.provisions_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Statute", "Code", "Number", "Title", "URL", "Content"])
        for i, statute in enumerate(statutes, start=1):
            try:
                provisions = get_provisions(session, statute["code"], args.with_text, args.delay)
            except requests.RequestException as exc:
                print(f"[{i}/{len(statutes)}] {statute['name']}: failed ({exc})")
                provisions = []
            for p in provisions:
                writer.writerow([statute["name"], statute["code"], p["number"], p["title"], p["url"], p["content"]])
            print(f"[{i}/{len(statutes)}] {statute['name']}: {len(provisions)} provisions")
            time.sleep(args.delay)
    print(f"Wrote provisions to {args.provisions_file}")


if __name__ == "__main__":
    main()
