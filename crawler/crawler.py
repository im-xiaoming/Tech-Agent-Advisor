import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://cellphones.com.vn"
MOBILE_CATEGORY = "https://cellphones.com.vn/mobile.html"
OUT_PATH = Path("data") / "cellphones_mobile.jsonl"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}


def setup_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update(HEADERS)
    return session


def get_soup(url: str, session: requests.Session) -> BeautifulSoup | None:
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, "html.parser")
    except requests.RequestException as e:
        print(f"Request failed for {url}: {e}")
        return None


def normalize_url(href: str) -> str | None:
    if not href:
        return None
    href = href.strip()
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith("/"):
        return urljoin(BASE_URL, href)
    if href.startswith("http"):
        return href
    return urljoin(BASE_URL, href)


def extract_product_links(category_url: str, session: requests.Session, limit: int = 200) -> List[str]:
    soup = get_soup(category_url, session)
    if not soup:
        return []

    links = set()

    # Common product link selectors observed on cellphones.com.vn
    selectors = [
        "a.product__link",
        "a.product__name",
        "a.product-item__link",
        "a.product__thumb",
        "a.button__link.product__link",
    ]

    for sel in selectors:
        for a in soup.select(sel):
            href = a.get("href")
            url = normalize_url(href)
            if url and BASE_URL in url:
                links.add(url)

    # Fallback: find anchors under product listing blocks
    for block in soup.select(".product, .product-item, .product__box, .product-list__item"):
        a = block.find("a", href=True)
        if a:
            url = normalize_url(a.get("href"))
            if url and BASE_URL in url:
                links.add(url)

    # Limit results
    result = list(links)[:limit]
    print(f"Found {len(result)} product links on {category_url}")
    return result


def extract_brand_links(category_url: str, session: requests.Session) -> List[tuple]:
    """Return list of (brand_name, brand_url) from the category page."""
    soup = get_soup(category_url, session)
    if not soup:
        return []

    brands = []
    # common brand list selectors
    for a in soup.select(".list-brand a, .brand-list a, a.list-brand__item, .list-brand__item a"):
        href = a.get("href")
        url = normalize_url(href)
        name = clean_text(a.get_text(" ", strip=True)) or None
        if url and BASE_URL in url:
            brands.append((name or brand_name_from_url(url), url))

    # dedupe while preserving order
    seen = set()
    out = []
    for name, url in brands:
        if url not in seen:
            seen.add(url)
            out.append((name, url))
    print(f"Found {len(out)} brands on {category_url}")
    return out


def clean_text(s: str) -> str:
    if not s:
        return ""
    text = re.sub(r"\s+", " ", s)
    return text.strip()


def brand_name_from_url(url: str) -> str:
    slug = Path(urlparse(url).path.rstrip("/")).stem.lower()
    slug = re.sub(r"^(?:dien-thoai-|mobile-)", "", slug)
    known_names = {
        "apple": "Apple",
        "asus": "ASUS",
        "google": "Google",
        "honor": "HONOR",
        "infinix": "Infinix",
        "nokia": "Nokia",
        "nothing": "Nothing",
        "oneplus": "OnePlus",
        "oppo": "OPPO",
        "realme": "realme",
        "samsung": "Samsung",
        "tecno": "TECNO",
        "vivo": "vivo",
        "xiaomi": "Xiaomi",
    }
    return known_names.get(slug, slug.replace("-", " ").title())


def find_specs_container(soup: BeautifulSoup):
    selectors = [
        "#thong-so-ky-thuat",
        ".cps-block-technicalInfo",
        "#tabSpec",
        ".product-specs",
        ".product__specs",
        ".specification",
        ".thong-so",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            return node
    return None


def extract_product_data(product_url: str, session: requests.Session) -> dict | None:
    soup = get_soup(product_url, session)
    if not soup:
        return None

    # Title
    title = None
    if soup.find("h1"):
        title = clean_text(soup.find("h1").get_text(" ", strip=True))
    if not title and soup.select_one("meta[property=\"og:title\"]"):
        title = soup.select_one("meta[property=\"og:title\"]").get("content")

    # Description / short
    desc = ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        desc = clean_text(meta_desc.get("content"))
    elif soup.select_one("meta[property=\"og:description\"]"):
        desc = clean_text(soup.select_one("meta[property=\"og:description\"]").get("content", ""))

    # Price
    price = None
    price_selectors = [
        ".price",
        ".product__price",
        ".product-price",
        ".product-price__current",
        ".price-regular",
    ]
    for sel in price_selectors:
        node = soup.select_one(sel)
        if node and node.get_text(strip=True):
            price = clean_text(node.get_text(" ", strip=True))
            break

    # Images
    images = []
    for img in soup.select("img"):
        src = img.get("data-src") or img.get("src") or img.get("data-zoom-image")
        if not src:
            continue
        src = normalize_url(src)
        if src and BASE_URL in src and "/media/catalog/product/" in src:
            images.append(src)
    images = list(dict.fromkeys(images))

    # Tables inside article/SEO content often compare other products.
    specs_container = find_specs_container(soup)
    specs_text = ""
    if specs_container:
        specs_table = specs_container.select_one("table")
        specs_source = specs_table or specs_container
        specs_text = clean_text(specs_source.get_text(" ", strip=True))

    # Full description blocks
    desc_parts = []
    for sel in ["#tabDesc", ".product-description", ".description", ".product__description"]:
        for node in soup.select(sel):
            t = clean_text(node.get_text(" ", strip=True))
            if t:
                desc_parts.append(t)

    full_description = "\n".join([desc] + desc_parts)

    # Fallback: collect visible textual content from main area
    if not specs_text and not full_description:
        main = soup.find("main") or soup.find(class_=re.compile(r"product|content|main", re.I))
        if main:
            text = clean_text(main.get_text(" ", strip=True))
            full_description = text

    scraped = {
        "url": product_url,
        "title": title or "",
        "price": price or "",
        "description": full_description,
        "specs": specs_text,
        "images": images,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }

    # price numeric
    def parse_price_number(p: str) -> int | None:
        if not p:
            return None

        prices = re.findall(r"\d{1,3}(?:[.\s]\d{3})+", p)
        if not prices:
            return None

        return min(int(re.sub(r"[^\d]", "", value)) for value in prices)

    scraped["price_raw"] = scraped.pop("price")
    scraped["price"] = parse_price_number(scraped["price_raw"]) or ""

    # parse specs into key-value if possible
    def parse_specs_kv(specs_node) -> dict:
        kv = {}
        if not specs_node:
            return kv

        for table in specs_node.select("table")[:1]:
            for tr in table.find_all("tr"):
                tds = tr.find_all(["th", "td"])
                if len(tds) >= 2:
                    k = clean_text(tds[0].get_text(" ", strip=True))
                    v = clean_text(tds[1].get_text(" ", strip=True))
                    if k and v:
                        kv[k] = v

        if not kv:
            for line in clean_text(specs_node.get_text("\n", strip=True)).split("\n"):
                m = re.match(r"^(?P<k>[^:：]+)[:：]\s*(?P<v>.+)$", line)
                if m:
                    kv[m.group("k").strip()] = m.group("v").strip()

        return kv

    scraped["specs_kv"] = parse_specs_kv(specs_container)

    # variants (color/storage)
    def extract_variants(soup: BeautifulSoup) -> List[dict]:
        variants = []
        # common variant containers
        for node in soup.select(".product-variants, .variants, .product-attributes, .product-attribute, .variant"):
            # options can be buttons, spans or selects
            for opt in node.select(".option, .variant-item, li, button, label, option"): 
                text = clean_text(opt.get_text(" ", strip=True))
                if not text:
                    continue
                # try split color/storage
                color = None
                storage = None
                m_gb = re.search(r"(\d+\s?GB|\d+GB)", text, re.I)
                if m_gb:
                    storage = m_gb.group(0)
                m_color = re.search(r"Màu\s*[:：]?\s*(.+)$|^(.+)\s*-\s*Màu", text, re.I)
                if m_color:
                    color = m_color.group(1) or m_color.group(2)
                variants.append({"text": text, "color": clean_text(color or ""), "storage": clean_text(storage or "")})

        # also look for selects
        for sel in soup.find_all("select"):
            if not sel.get("name"):
                continue
            for opt in sel.find_all("option"):
                v = clean_text(opt.get_text(" ", strip=True))
                if v:
                    variants.append({"text": v})

        # dedupe
        seen = set()
        out = []
        for v in variants:
            key = v.get("text")
            if key and key not in seen:
                seen.add(key)
                out.append(v)
        return out

    scraped["variants"] = extract_variants(soup)

    # promotions, warranty, stock
    promo_texts = []
    for sel in [".promotion, .product__promotion, .product-promotion, .promotion-info, .badge, .status"]:
        for node in soup.select(sel):
            t = clean_text(node.get_text(" ", strip=True))
            if t:
                promo_texts.append(t)
    scraped["promotions"] = list(dict.fromkeys(promo_texts))

    # rating and reviews: try JSON-LD first
    rating = None
    reviews_count = None
    reviews = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            j = json.loads(script.string or "{}")
        except Exception:
            continue
        if isinstance(j, dict):
            if j.get("@type") == "Product":
                agg = j.get("aggregateRating") or {}
                rating = agg.get("ratingValue") or rating
                reviews_count = agg.get("reviewCount") or reviews_count
                if j.get("review"):
                    for r in j.get("review")[:5]:
                        reviews.append({"author": r.get("author"), "rating": r.get("reviewRating", {}).get("ratingValue"), "text": r.get("reviewBody")})
        elif isinstance(j, list):
            for obj in j:
                if obj.get("@type") == "Product":
                    agg = obj.get("aggregateRating") or {}
                    rating = agg.get("ratingValue") or rating
                    reviews_count = agg.get("reviewCount") or reviews_count

    # fallback selectors
    if not rating:
        rnode = soup.select_one(".rating, .product-rating, .average-rating, .score")
        if rnode:
            rating = clean_text(rnode.get_text(" ", strip=True))
    if not reviews_count:
        rnode = soup.select_one(".review-count, .reviews-count, .count-review")
        if rnode:
            reviews_count = re.sub(r"[^0-9]", "", rnode.get_text(" ", strip=True))

    scraped["rating"] = rating or ""
    scraped["reviews_count"] = int(reviews_count) if reviews_count and str(reviews_count).isdigit() else reviews_count or 0
    scraped["reviews_sample"] = reviews

    # RAG-friendly source text; chunking belongs in the indexing pipeline.
    rag_text = "\n\n".join([p for p in [scraped["title"], scraped["description"], scraped["specs"]] if p])
    scraped["text"] = clean_text(rag_text)

    return scraped


def save_jsonl(items: List[dict], out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def load_existing_urls(out_path: Path) -> set:
    existing = set()
    if not out_path.exists():
        return existing
    try:
        with out_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    url = obj.get("url")
                    if url:
                        existing.add(url)
                except Exception:
                    continue
    except Exception:
        pass
    return existing


def crawl_mobile(limit: int = 200, pause: float = 1.0):
    session = setup_session()
    existing_urls = load_existing_urls(OUT_PATH)
    results = []

    # try to crawl by brand; fallback to category page if no brands found
    brands = extract_brand_links(MOBILE_CATEGORY, session)
    gathered_links = []
    if brands:
        for brand_name, brand_url in brands:
            links = extract_product_links(brand_url, session, limit=limit)
            for l in links:
                if l not in gathered_links:
                    gathered_links.append((l, brand_name))
                if len(gathered_links) >= limit:
                    break
            if len(gathered_links) >= limit:
                break
    else:
        for l in extract_product_links(MOBILE_CATEGORY, session, limit=limit):
            gathered_links.append((l, None))

    total = len(gathered_links)
    new_items = []
    for i, (url, brand_name) in enumerate(gathered_links, start=1):
        print(f"[{i}/{total}] Fetching {url}")
        if url in existing_urls:
            print("  - skipped (already saved)")
            continue
        data = extract_product_data(url, session)
        if not data:
            continue
        if brand_name:
            data["brand"] = brand_name
        results.append(data)
        new_items.append(data)
        # write per-item batch to avoid data loss
        save_jsonl([data], OUT_PATH)
        existing_urls.add(url)
        time.sleep(pause + (0.1 * (i % 3)))

    print(f"Scraped {len(results)} products ({len(new_items)} new). Saved to {OUT_PATH}")
    return results


if __name__ == "__main__":
    # default run: crawl mobile category and save JSONL
    crawl_mobile(limit=200, pause=1.0)
