# sgstatutescraper

Scrapes [Singapore Statutes Online](https://sso.agc.gov.sg/) (SSO): the list of current Acts, and each
Act's provisions with their number, title, direct link and (optionally) text.

## Install

```bash
pip install -r requirements.txt
```

## Use

```bash
python ssoscrape.py --statutes-only            # statutes.csv: every current Act (526 as of Oct 2026)
python ssoscrape.py --limit 10                 # provisions of the first 10 Acts
python ssoscrape.py --act PDPA2012 --act PC1871   # provisions of chosen Acts, by SSO code
python ssoscrape.py --act PDPA2012 --with-text    # ...with each provision's text
python ssoscrape.py                            # provisions of every current Act
```

Act codes (such as `PDPA2012`, `PC1871` or `AJPA2016`) are listed in `statutes.csv`.

## Output

| File | Columns |
| --- | --- |
| `statutes.csv` | Statute, Code, URL |
| `provisions.csv` | Statute, Code, Number, Title, URL, Content |

Both are UTF-8 with a BOM, so they open correctly in Excel. `Content` is filled only with `--with-text`.

## Being polite to SSO

SSO's `robots.txt` asks crawlers to wait 6 seconds between requests, and that is the default `--delay`.
Provision text is opt-in because SSO loads an Act's text in parts: a long Act takes about 25 requests,
or a few minutes at that delay. Listing the provisions of every Act takes about an hour.

## How it works

- The Acts come from SSO's "Browse > Acts > Current" pages (500 per page). Each Act's code is read from
  SSO's own link, not guessed from its name.
- Provisions come from each Act's table of contents (`/Act/<code>?WholeDoc=1`).
- With `--with-text`, the parts SSO lazy-loads (`/Details/GetLazyLoadContent`) are fetched and each
  provision's text is taken from its section block.
