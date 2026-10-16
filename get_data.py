"""Download the original Survey of Consumer Finances (SCF) files from the Federal Reserve.

The script discovers file links on the Federal Reserve's own SCF pages instead of
hard-coding a list of years, downloads them into data/raw/, checks that each file is
real data (not an HTML error page), and records the source URL, retrieval time, size
and SHA-256 hash of every file in data/raw/manifest.csv.

What it downloads:
  * the summary extract public data (CSV version) for every survey from 1989 to the
    latest survey listed on the current-survey page;
  * the SAS macro that defines the summary-extract variables (bulletin.macro.txt);
  * the Fed's historic tables based on public data, in 2025 dollars (for validation);
  * the latest survey's codebook, standard-error documentation, standard-error tables
    and replicate weights (for the confidence interval check).

Reruns are safe: files that already exist and pass validation are kept, unless --force.

Usage:  python get_data.py [--force] [--no-replicates]
"""

import argparse
import csv
import hashlib
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
MANIFEST = RAW / "manifest.csv"

BASE = "https://www.federalreserve.gov"
CURRENT_PAGE = BASE + "/econres/scfindex.htm"
PREVIOUS_PAGE = BASE + "/econres/scf-previous-surveys.htm"
FIRST_YEAR = 1989
HEADERS = {"User-Agent": "ps158-reproduce/1.0 (course replication script; python-requests)"}
MANIFEST_FIELDS = ["survey_year", "kind", "url", "local_file", "retrieved_utc", "bytes", "sha256"]


def fetch(url, tries=3):
    """GET a URL, retrying transient failures; raise on any non-200 status."""
    for attempt in range(1, tries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=120)
            if r.status_code == 200:
                return r
            msg = f"HTTP {r.status_code}"
            if r.status_code < 500 and r.status_code != 429:
                raise RuntimeError(f"{msg} for {url}")
        except requests.RequestException as exc:
            msg = str(exc)
        if attempt < tries:
            time.sleep(5 * attempt)
    raise RuntimeError(f"Failed to download {url} after {tries} tries: {msg}")


def links(page_url):
    html = fetch(page_url).text
    return [urljoin(page_url, h) for h in re.findall(r'href="([^"]+)"', html)]


def discover():
    """Return a list of (survey_year, kind, url) found on the official SCF pages."""
    current = links(CURRENT_PAGE)
    found = {}
    for u in current:
        m = re.search(r"/scfp(\d{4})excel\.zip$", u)
        if m:
            found[int(m.group(1))] = u
    if len(found) != 1:
        raise RuntimeError(f"Expected one CSV summary extract on {CURRENT_PAGE}, found {found}")
    latest = max(found)

    # Each earlier main survey has its own page (scf_1989.htm, ...); panel pages end in 'p'.
    year_pages = sorted({u for u in links(PREVIOUS_PAGE) if re.search(r"/scf_\d{4}\.htm$", u)})
    for page in year_pages:
        year = int(re.search(r"scf_(\d{4})\.htm$", page).group(1))
        if not FIRST_YEAR <= year < latest:  # also skips scf_6263.htm (1962-63 survey)
            continue
        hits = [u for u in links(page) if re.search(rf"/scfp{year}excel\.zip$", u)]
        if hits:
            found[year] = hits[0]
        else:
            print(f"  warning: no CSV summary extract link found on {page}")

    files = [(y, "summary_extract_csv", found[y]) for y in sorted(found)]

    def pick(pattern, kind, year=""):
        hits = [u for u in current if re.search(pattern, u)]
        if not hits:
            raise RuntimeError(f"Could not find {kind} ({pattern}) on {CURRENT_PAGE}")
        files.append((year, kind, hits[0]))

    pick(r"/bulletin\.macro\.txt$", "variable_definitions_macro")
    pick(rf"/scf{latest}_tables_public_real_historical\.xlsx$", "historic_tables_public_real", latest)
    pick(rf"/codebk{latest}\.txt$", "codebook", latest)
    pick(r"/Standard_Error_Documentation\.pdf$", "standard_error_documentation", latest)
    pick(rf"/{latest}_tables1_2_stderrs\.xlsx$", "standard_error_tables", latest)
    pick(rf"/scf{latest}rw1s\.zip$", "replicate_weights_stata", latest)
    return latest, files


def validate(path):
    """Raise if the file is missing, empty, an HTML page, or a corrupt archive."""
    data = path.read_bytes()[:2048]
    if not data:
        raise ValueError(f"{path.name} is empty")
    if data.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
        raise ValueError(f"{path.name} is an HTML page, not data")
    suffix = path.suffix.lower()
    if suffix in (".zip", ".xlsx"):
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            if bad:
                raise ValueError(f"{path.name}: corrupt member {bad}")
            names = z.namelist()
        if suffix == ".zip" and not names:
            raise ValueError(f"{path.name} is an empty archive")
    elif suffix == ".pdf" and not data.startswith(b"%PDF"):
        raise ValueError(f"{path.name} is not a PDF")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest():
    if not MANIFEST.exists():
        return {}
    with open(MANIFEST, newline="") as f:
        return {row["local_file"]: row for row in csv.DictReader(f)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    ap.add_argument("--no-replicates", action="store_true",
                    help="skip the large replicate-weight file (only needed for the CI check)")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    print(f"Discovering files on {CURRENT_PAGE} and {PREVIOUS_PAGE} ...")
    latest, files = discover()
    years = sorted(y for y, k, _ in files if k == "summary_extract_csv")
    print(f"Latest survey: {latest}. Summary extracts found for: {', '.join(map(str, years))}")
    expected = list(range(FIRST_YEAR, latest + 1, 3))
    if years != expected:
        print(f"  warning: expected triennial surveys {expected}, found {years}")

    old = read_manifest()
    rows = []
    for year, kind, url in files:
        if args.no_replicates and kind == "replicate_weights_stata":
            continue
        local = RAW / url.rsplit("/", 1)[-1]
        rel = local.relative_to(ROOT).as_posix()
        retrieved = None
        if local.exists() and not args.force:
            try:
                validate(local)
                retrieved = old.get(rel, {}).get("retrieved_utc")
                print(f"  keep  {rel}")
            except Exception as exc:
                print(f"  existing {rel} failed validation ({exc}); downloading again")
        if retrieved is None:
            print(f"  get   {url}")
            r = fetch(url)
            tmp = local.with_name(local.name + ".part")
            tmp.write_bytes(r.content)
            validate(tmp)
            tmp.replace(local)
            retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows.append({"survey_year": year, "kind": kind, "url": url, "local_file": rel,
                     "retrieved_utc": retrieved or "unknown (file predates manifest)",
                     "bytes": local.stat().st_size, "sha256": sha256(local)})

    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {MANIFEST.relative_to(ROOT)} ({len(rows)} files).")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.exit(f"get_data.py failed: {exc}")
