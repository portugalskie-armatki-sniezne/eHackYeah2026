"""refresh the service entity snapshot from official BIP exports and reviewed supplements."""

import argparse
from datetime import date
import hashlib
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import urlencode, urlsplit
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from import_service_entities import COLUMNS, http_url, validate_entities


BIP_EXPORT = "https://www.gov.pl/web/bip/spis"
REGIONAL_API = "https://bip.malopolska.pl/api/"
SEARCH_TERMS = ("straż", "dróg", "drogowy", "komunal", "wodoci", "kanaliz",
                "zieleni", "komunikac", "transport", "ciepl")


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold().replace("ł", "l"))
    return " ".join("".join(c for c in value if not unicodedata.combining(c)).split())


def classify(name: str) -> str | None:
    name = normalized(name)
    rules = (
        (r"straz (miejska|gminna)", "municipal_guard"),
        (r"zarzad (?:drog|drogowy)|zarzad drog", "road_manager"),
        (r"zarzad transportu|zwiazek.*komunikacja", "transport_authority"),
        (r"(?:zaklad|przedsiebiorstwo) komunikac|spolka transportowa", "transport_operator"),
        (r"zarzad zieleni|zaklad gospodarczy zieleni", "green_space_manager"),
        (r"zarzad infrastruktury wodnej", "water_infrastructure_manager"),
        (r"zwiazek.*wodoci", "water_sewage_authority"),
        (r"wodoci|wodno-kanaliz", "water_sewage_utility"),
        (r"energetyki cieplnej", "heating_utility"),
        (r"oczyszczania|skladowisko odpadow", "waste_management"),
        (r"zarzad (?:budynkow|zasobow|mienia)|zaklad administracji budynkow", "housing_manager"),
        (r"zarzad cmentarz", "cemetery_manager"),
        (r"zarzad infrastruktury sportowej", "sports_infrastructure_manager"),
        (r"zarzad inwestycji miejskich", "municipal_investment"),
        (r"(?:zaklad|przedsiebiorstwo|uslugi|agencja|gospodarka|spolka|jednostka|zespol).*komunal",
         "municipal_services"),
    )
    return next((kind for pattern, kind in rules if re.search(pattern, name)), None)


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.replace("\u2013", "-").replace("\u2014", "-").split()) or None


def new_entity(key: str, name: str, kind: str, source: str, verified: str) -> dict:
    record = dict.fromkeys(COLUMNS)
    record.update(source_key=key, name=clean(name), entity_type=kind,
                  source_urls=[source], verified_on=verified)
    return record


def parse_bip(data: bytes, verified: str) -> tuple[list[dict], int]:
    if data.startswith(b"PK"):
        with ZipFile(BytesIO(data)) as archive:
            info = archive.getinfo("subjects.xml")
            if info.file_size > 50_000_000:
                raise ValueError("BIP XML exceeds the size limit")
            data = archive.read(info)
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("BIP XML must not contain entity declarations")
    root = ET.fromstring(data)
    if root.tag != "resultset" or not len(root):
        raise ValueError("Unexpected or empty BIP export")
    records = []
    seen = set()
    mapping = {"place": "locality", "zipCode": "postal_code", "street": "street",
               "number": "house_number", "phone": "phone_number", "email": "email", "url": "bip_url"}
    for row in root:
        code = clean(row.findtext("communeTercCode/code"))
        name = clean(row.findtext("name"))
        kind = classify(name or "")
        if not code or not code.startswith("12") or not kind:
            continue
        identifier = clean(row.findtext("id"))
        if not identifier or identifier in seen:
            raise ValueError("Missing or duplicate BIP subject ID")
        seen.add(identifier)
        record = new_entity("bip:" + identifier, name, kind, BIP_EXPORT, verified)
        record["teryt_code"] = code
        record.update({column: clean(row.findtext(tag)) for tag, column in mapping.items()})
        records.append(record)
    if not records:
        raise ValueError("BIP export contains no matching Małopolska entities")
    return records, len(root)


def url_identity(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value)
    host = (parts.hostname or "").removeprefix("www.").casefold()
    path = parts.path.strip("/").casefold()
    if host == "bip.malopolska.pl":
        path = path.split(",")[0]
    return host + "/" + path + ("?" + parts.query if parts.query else "")


class TextLines(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.rows = []
        self.cells = []
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n")
        if tag == "tr":
            self.cells = []
        if tag in ("td", "th"):
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th"):
            self.parts.append("\n")
        if tag in ("td", "th") and self.cell is not None:
            self.cells.append(clean(" ".join(self.cell)) or "")
            self.cell = None
        if tag == "tr":
            self.rows.append(self.cells)

    def handle_data(self, data):
        self.parts.append(data)
        if self.cell is not None:
            self.cell.append(data)


def article_contacts(article: dict) -> dict:
    if article.get("isArchived") or article.get("isHistorical"):
        raise ValueError("Archived regional BIP article")
    parser = TextLines()
    parser.feed(article.get("content") or "")
    text = "".join(parser.parts)
    result = {}
    labels = {"miejscowosc": "locality", "ulica": "street", "numer domu": "house_number",
              "kod pocztowy": "postal_code", "telefon": "phone_number", "e-mail": "email"}
    for cells in parser.rows:
        if len(cells) == 2:
            field = labels.get(normalized(cells[0]).strip(":"))
            if field and clean(cells[1]):
                result[field] = clean(cells[1])
    codes = set(re.findall(r"TERYT\s*:\s*([0-9]{7})(?!\d)", text, re.I))
    if len(codes) == 1:
        result["teryt_code"] = codes.pop()
    addresses = set()
    streets = set()
    for line in text.splitlines():
        line = clean(line) or ""
        match = re.fullmatch(r"([0-9]{2}-[0-9]{3})\s+([^\W\d_]+(?:[ -][^\W\d_]+)*)[.,]?", line)
        if match:
            addresses.add(match.groups())
        match = re.fullmatch(r"(?:ul\.?|al\.?|pl\.?|os\.?)\s+(.+?)\s+(\d+[A-Za-z]?(?:/\d+[A-Za-z]?)?)[.,]?", line, re.I)
        if match:
            streets.add(match.groups())
    if len(addresses) == 1:
        postal, locality = addresses.pop()
        result.setdefault("postal_code", postal)
        result.setdefault("locality", locality)
    if len(streets) == 1:
        street, number = streets.pop()
        result.setdefault("street", street)
        result.setdefault("house_number", number)
    # ambiguous or personal contacts stay empty for subsequent review.
    emails = set(re.findall(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", text))
    general = {email for email in emails if re.match(
        r"^(?:sekretariat|biuro|kontakt|urzad|straz|sm|zgk|zuk|gzk|pzd|zdp|mzwik|zwik|mpgk|mpec|bok|sek)[@.]",
        email, re.I)}
    if len(general) == 1:
        result.setdefault("email", general.pop())
    phones = set()
    for line in text.splitlines():
        if re.search(r"\b(?:tel\.?|telefon)\s*[:.]?", line, re.I):
            for match in re.finditer(r"(?<!\d)(?:\+48[ -]*)?(?:\(?\d{2}\)?[ -]*)\d{3}[ -]*\d{2}[ -]*\d{2}(?!\d)", line):
                phones.add(re.sub(r"[^0-9+]", "", match.group()))
    if len(phones) == 1:
        result.setdefault("phone_number", phones.pop())
    return result


def fetch(url: str, cache: Path | None) -> bytes:
    path = cache / (hashlib.sha256(url.encode()).hexdigest() + ".data") if cache else None
    if path and path.exists():
        return path.read_bytes()
    request = Request(url, headers={"User-Agent": "eHackYeah2026-reference-data/1.0"})
    with urlopen(request, timeout=30) as response:
        data = response.read(50_000_001)
    if len(data) > 50_000_000:
        raise ValueError("Source response exceeds the size limit")
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return data


def contact_articles(context: dict, cache: Path | None) -> list[str]:
    menu_id = context.get("defaultMenuId")
    if not menu_id:
        return []
    menu = json.loads(fetch(REGIONAL_API + "menu/" + str(menu_id), cache))
    articles = []
    for item in menu:
        if not re.fullmatch(r"kontakt|dane teleadresowe(?: podmiotu)?|dane adresowe", normalized(item["name"])):
            continue
        match = re.search(r",([am]),([0-9]+)", item["link"])
        if not match:
            continue
        if match[1] == "a":
            articles.append(REGIONAL_API + "articles/" + match[2])
        else:
            listing = json.loads(fetch(REGIONAL_API + "menu/" + match[2] + "/articles?limit=10&offset=0", cache))
            article_id = listing.get("mainArticleId")
            if article_id:
                articles.append(REGIONAL_API + "articles/" + str(article_id))
        if len(articles) == 2:
            break
    return articles


def collect_regional(verified: str, cache: Path | None, units_path: Path | None) -> tuple[list[dict], list[str]]:
    units = {}
    if units_path:
        units = {unit["id"]: unit for unit in json.loads(units_path.read_text(encoding="utf-8"))}
    else:
        for term in SEARCH_TERMS:
            url = REGIONAL_API + "units/search?" + urlencode({"phrase": term})
            data = json.loads(fetch(url, cache))
            if not isinstance(data, list) or not data:
                raise ValueError(f"Unexpected regional BIP search response: {term}")
            units.update({unit["id"]: unit for unit in data})
    records, omissions = [], []
    for unit in sorted(units.values(), key=lambda unit: unit["id"]):
        kind = classify(unit["fullName"])
        if not kind:
            continue
        slug = unit["friendlyUrl"]
        url = REGIONAL_API + "contexts/" + slug
        context = json.loads(fetch(url, cache))
        if str(context["id"]) != str(unit["id"]):
            raise ValueError(f"Regional BIP identity mismatch: {slug}")
        record = new_entity("malopolska:" + str(unit["id"]), unit["fullName"], kind, url, verified)
        record["bip_url"] = "https://bip.malopolska.pl/" + slug
        website = clean(unit.get("externalLink"))
        if website and website.startswith("www."):
            website = "https://" + website
        if website and http_url(website) and urlsplit(website).hostname != "brak.pl":
            record["website"] = website
        article_id = context.get("startArticleId")
        if article_id:
            article_url = REGIONAL_API + "articles/" + article_id
            try:
                article = json.loads(fetch(article_url, cache))
            except HTTPError as error:
                if error.code != 404:
                    raise
                omissions.append(f"{record['source_key']}: start article returned 404")
                article = {}
            if article.get("isArchived") or article.get("isHistorical"):
                omissions.append(f"{record['source_key']}: archived start article")
                continue
            record.update(article_contacts(article))
            if article:
                record["source_urls"].append(article_url)
        if not all(record[field] for field in ("email", "phone_number", "street", "locality")):
            try:
                for article_url in contact_articles(context, cache):
                    article = json.loads(fetch(article_url, cache))
                    if article.get("isArchived") or article.get("isHistorical"):
                        continue
                    contacts = article_contacts(article)
                    if contacts:
                        record.update(contacts)
                        record["source_urls"].append(article_url)
            except HTTPError as error:
                if error.code != 404:
                    raise
                omissions.append(f"{record['source_key']}: contact page returned 404")
        record["source_urls"] = sorted(set(record["source_urls"]))
        records.append(record)
        print(f"Collected {record['source_key']}: {record['name']}", flush=True)
    return records, omissions


def merge_records(central: list[dict], regional: list[dict], supplements: list[dict],
                  previous: list[dict]) -> list[dict]:
    records = {record["source_key"]: record.copy() for record in central}
    for record in regional:
        matches = [existing for existing in records.values()
                   if url_identity(existing["bip_url"]) == url_identity(record["bip_url"])]
        if len(matches) > 1:
            raise ValueError("Ambiguous BIP URL match")
        if matches:
            existing = matches[0]
            for field in ("website", "phone_number", "email"):
                existing[field] = existing[field] or record[field]
            existing["source_urls"] = sorted(set(existing["source_urls"] + record["source_urls"]))
        else:
            records[record["source_key"]] = record.copy()
    for supplement in supplements:
        key = supplement["source_key"]
        aliases = supplement.get("replaces", [])
        for alias in aliases:
            records.pop(alias, None)
        fields = {field: value for field, value in supplement.items() if field != "replaces"}
        if key in records:
            existing = records[key]
            fields["source_urls"] = sorted(set(existing["source_urls"] + fields["source_urls"]))
            fields["verified_on"] = min(existing["verified_on"], fields["verified_on"])
            existing.update(fields)
        else:
            records[key] = dict.fromkeys(COLUMNS) | fields
    # preserve identities if a previously regional-only entity enters the central export.
    old_urls = {url_identity(record["bip_url"]): record["source_key"]
                for record in previous if record["bip_url"]}
    result = list(records.values())
    for record in result:
        record["source_key"] = old_urls.get(url_identity(record["bip_url"]), record["source_key"])
    return validate_entities(sorted(result, key=lambda record: record["source_key"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--supplements", type=Path, required=True)
    parser.add_argument("--bip-export", type=Path)
    parser.add_argument("--regional-units", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--verified-on", type=date.fromisoformat)
    args = parser.parse_args()
    if (args.bip_export or args.regional_units or args.cache_dir) and not args.verified_on:
        parser.error("Cached or local sources require --verified-on with their original retrieval date")
    verified = (args.verified_on or date.today()).isoformat()
    data = args.bip_export.read_bytes() if args.bip_export else fetch(BIP_EXPORT, args.cache_dir)
    central, total = parse_bip(data, verified)
    regional, omissions = collect_regional(verified, args.cache_dir, args.regional_units)
    supplements = json.loads(args.supplements.read_text(encoding="utf-8"))
    previous = json.loads(args.output.read_text(encoding="utf-8"))["entities"] if args.output.exists() else []
    entities = merge_records(central, regional, supplements, previous)
    snapshot = {
        "format_version": 1, "retrieved_on": verified,
        "central_export_url": BIP_EXPORT, "central_export_sha256": hashlib.sha256(data).hexdigest(),
        "central_total": total, "central_selected": len(central), "regional_selected": len(regional),
        "omissions": omissions, "entities": entities,
    }
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(f"Saved {len(entities)} service entities; {len(omissions)} source limitations recorded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
