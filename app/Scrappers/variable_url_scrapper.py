# electronic_scraper.py
"""
Robust scraper that extracts product cards based only on `div[data-id]`.
- Uses resp.url (final URL after redirects) as base for resolving relative links.
- More tolerant attribute/text extraction while still relying on data-id presence.
- Session with retries, optional Selenium fallback (forceable via CLI).
- Clear logging for debugging why a page returned no cards.
"""

import argparse
import json
import logging
import re
import time
from typing import List, Dict, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Configuration ---
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}
DEFAULT_TIMEOUT = 20
LOG = logging.getLogger("electronic_scraper")
LOG.setLevel(logging.INFO)
LOG.addHandler(logging.StreamHandler())

# --- Helpers: requests session with retries ---
def _create_session(retries: int = 3, backoff_factor: float = 0.3) -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"])
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

# --- Parsing helpers (robust but still focused on data-id cards) ---
def _text(soup: BeautifulSoup, selector: str) -> Optional[str]:
    el = soup.select_one(selector)
    return el.get_text(strip=True) if el else None

def _first_attr_from_selectors(soup: BeautifulSoup, selectors: List[str], attribute: str = "href") -> Optional[str]:
    for sel in selectors:
        el = soup.select_one(sel)
        if el and el.has_attr(attribute):
            val = el.get(attribute)
            if val:
                return val
    return None

def _first_text_from_selectors(soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
    for sel in selectors:
        txt = _text(soup, sel)
        if txt:
            return txt
    return None

def _resolve_url(base: str, link: Optional[str]) -> Optional[str]:
    if not link:
        return None
    try:
        return urljoin(base, link)
    except Exception:
        return link

def _find_price_text(soup: BeautifulSoup) -> Optional[str]:
    # Look for common currency symbols anywhere inside the card
    text = soup.get_text(" ", strip=True)
    m = re.search(r"(₹|Rs\.|INR|\$|USD|£|GBP)\s?[\d,]+(?:\.\d+)?", text)
    return m.group(0) if m else None

# --- Core card parser (uses only data-id presence to identify cards) ---
def parse_product_card(card_soup: BeautifulSoup, base_url: str) -> Dict[str, Optional[str]]:
    """
    Extract fields from a single product card BeautifulSoup element.
    This function assumes the caller already selected elements with `div[data-id]`.
    """
    data_id = card_soup.get("data-id")
    # product link heuristics: prefer anchors that look like product links, fallback to first anchor
    href = _first_attr_from_selectors(card_soup, ["a.pIpigb", "a.GnxRXv", "a[href]"], "href")
    product_url = _resolve_url(base_url, href)

    # image heuristics: common attributes
    image = _first_attr_from_selectors(card_soup, ["img.UCc1lI", "img[src]", "img[data-src]"], "src") \
            or _first_attr_from_selectors(card_soup, ["img[data-src]","img[srcset]"], "data-src") \
            or _first_attr_from_selectors(card_soup, ["img[srcset]"], "srcset")
    image_url = _resolve_url(base_url, image)

    # title heuristics: alt, anchor text, headings
    title = None
    # alt attribute on image
    img_el = card_soup.select_one("img")
    if img_el and img_el.has_attr("alt") and img_el.get("alt").strip():
        title = img_el.get("alt").strip()
    if not title:
        title = _first_text_from_selectors(card_soup, ["a.pIpigb", "a.GnxRXv", "a[title]", "h1, h2, h3, h4, .title, ._4rR01T"])
    # price heuristics
    price = _first_text_from_selectors(card_soup, [".QiMO5r .hZ3P6w", ".price", ".rupee, ._30jeq3"]) or _find_price_text(card_soup)
    original_price = _first_text_from_selectors(card_soup, [".QiMO5r .kRYCnD", ".original-price", ".strike"]) 
    discount = _first_text_from_selectors(card_soup, [".QiMO5r .HQe8jr span", ".discount", ".percent-off"])
    badge = _first_text_from_selectors(card_soup, [".MaiFhH .HZ0E6r", ".SJekt1 .JiknFv", ".badge", ".label"])

    return {
        "data_id": data_id,
        "title": title,
        "product_url": product_url,
        "image_url": image_url,
        "price": price,
        "original_price": original_price,
        "discount": discount,
        "badge": badge
    }

# --- Static scraping (requests + bs4) ---
def scrape_static(url: str, timeout: int = DEFAULT_TIMEOUT, session: Optional[requests.Session] = None) -> List[Dict]:
    """
    Fetch page with requests and parse `div[data-id]` cards.
    Returns list of product dicts. Uses final response URL as base for resolving relative links.
    """
    sess = session or _create_session()
    resp = sess.get(url, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    base = resp.url  # final URL after redirects
    soup = BeautifulSoup(resp.text, "lxml")
    cards = soup.select("div[data-id]")
    LOG.info("Static fetch: %d cards found on %s", len(cards), base)
    results = [parse_product_card(card, base_url=base) for card in cards]
    return results

# --- Selenium fallback (optional) ---
def _selenium_available() -> bool:
    try:
        import importlib
        return importlib.util.find_spec("selenium") is not None and importlib.util.find_spec("webdriver_manager") is not None
    except Exception:
        return False

def scrape_with_selenium(url: str, wait: float = 2.0, headless: bool = True) -> List[Dict]:
    """
    Use Selenium to render JS and extract product cards. Requires selenium and webdriver-manager.
    This function intentionally keeps the same `div[data-id]` selection logic.
    """
    from selenium import webdriver  # type: ignore
    from selenium.webdriver.common.by import By  # type: ignore
    from selenium.webdriver.chrome.options import Options  # type: ignore
    from selenium.webdriver.chrome.service import Service  # type: ignore
    from webdriver_manager.chrome import ChromeDriverManager  # type: ignore

    opts = Options()
    if headless:
        # modern headless flag
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"user-agent={HEADERS['User-Agent']}")
    # create driver using Service for compatibility
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_window_size(1200, 900)
    try:
        driver.get(url)
        time.sleep(wait)
        # attempt to trigger lazy load
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait)
        elements = driver.find_elements(By.CSS_SELECTOR, "div[data-id]")
        LOG.info("Selenium fetch: %d cards found", len(elements))
        results = []
        for el in elements:
            html = el.get_attribute("outerHTML")
            soup = BeautifulSoup(html, "lxml")
            # use driver.current_url as base (in case of redirects)
            results.append(parse_product_card(soup, base_url=driver.current_url))
        return results
    finally:
        driver.quit()

# --- Public API function ---
def scrape_listing(url: str, use_selenium_if_empty: bool = True, force_selenium: bool = False) -> List[Dict]:
    """
    Scrape a listing page URL and return list of product dicts.
    - If force_selenium is True, Selenium will be used (if available).
    - Otherwise, static fetch is attempted first; if it yields no cards and use_selenium_if_empty is True,
      Selenium will be attempted (if available).
    """
    session = _create_session()
    items: List[Dict] = []
    # If user explicitly forces Selenium, try it first (if available)
    if force_selenium:
        if _selenium_available():
            try:
                LOG.info("Force Selenium enabled: attempting Selenium render for %s", url)
                return scrape_with_selenium(url)
            except Exception as e:
                LOG.warning("Selenium forced but failed: %s", e)
        else:
            LOG.warning("Selenium requested but not available in environment; falling back to static fetch.")

    # Try static fetch
    try:
        items = scrape_static(url, session=session)
    except Exception as e:
        LOG.warning("Static fetch failed for %s: %s", url, e)
        items = []

    # If no items and selenium fallback allowed, try selenium
    if not items and use_selenium_if_empty and _selenium_available():
        try:
            LOG.info("No items from static fetch; attempting Selenium fallback for %s", url)
            items = scrape_with_selenium(url)
        except Exception as e:
            LOG.warning("Selenium fallback failed for %s: %s", url, e)
            items = []

    return items

# --- CLI usage ---
def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape product cards from a listing page (div[data-id] based)."
    )
    parser.add_argument("url", help="Listing page URL to scrape")
    parser.add_argument("--force-selenium", action="store_true", help="Force Selenium rendering (requires selenium & webdriver-manager)")
    parser.add_argument("--no-selenium-fallback", action="store_true", help="Do not attempt Selenium fallback if static fetch returns no cards")
    parser.add_argument("--headless", action="store_true", help="Run Selenium in headless mode when used")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout in seconds")
    return parser

if __name__ == "__main__":
    parser = _build_arg_parser()
    args = parser.parse_args()

    # If user forces selenium but it's not available, print error and exit
    if args.force_selenium and not _selenium_available():
        print(json.dumps({"error": "Selenium not installed. Install selenium and webdriver-manager to use this mode."}, ensure_ascii=False))
        raise SystemExit(1)

    try:
        data = scrape_listing(
            args.url,
            use_selenium_if_empty=not args.no_selenium_fallback,
            force_selenium=args.force_selenium
        )
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as exc:
        LOG.exception("Unhandled error while scraping: %s", exc)
        print(json.dumps({"error": str(exc)}))
