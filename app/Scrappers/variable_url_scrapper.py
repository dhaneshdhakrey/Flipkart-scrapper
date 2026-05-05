# electronic_scraper.py
import json
import time
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0 Safari/537.36"
}

# --- Parsing helpers ---
def _text(soup, selector: str) -> Optional[str]:
    el = soup.select_one(selector)
    return el.get_text(strip=True) if el else None

def _attr(soup, selector: str, attribute: str = "href") -> Optional[str]:
    el = soup.select_one(selector)
    if not el:
        return None
    return el.get(attribute) if el.has_attr(attribute) else None

def parse_product_card(card_soup, base_url: str) -> Dict[str, Optional[str]]:
    """Extract fields from a single product card BeautifulSoup element."""
    data_id = card_soup.get("data-id")
    # product links: prefer title link then image anchor
    href = _attr(card_soup, "a.pIpigb", "href") or _attr(card_soup, "a.GnxRXv", "href")
    if href:
        href = urljoin(base_url, href)
    image = _attr(card_soup, "img.UCc1lI", "src") or _attr(card_soup, "img.UCc1lI", "data-src")
    title = _text(card_soup, "a.pIpigb") or _text(card_soup, "a.GnxRXv")
    price = _text(card_soup, ".QiMO5r .hZ3P6w")
    original_price = _text(card_soup, ".QiMO5r .kRYCnD")
    discount = _text(card_soup, ".QiMO5r .HQe8jr span")
    badge = _text(card_soup, ".MaiFhH .HZ0E6r") or _text(card_soup, ".SJekt1 .JiknFv")
    return {
        "data_id": data_id,
        "title": title,
        "product_url": href,
        "image_url": image,
        "price": price,
        "original_price": original_price,
        "discount": discount,
        "badge": badge
    }

# --- Static scraping (requests + bs4) ---
def scrape_static(url: str, timeout: int = 20) -> List[Dict]:
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    cards = soup.select("div[data-id]")
    results = [parse_product_card(card, base_url=url) for card in cards]
    return results

# --- Optional Selenium fallback ---
def _selenium_available() -> bool:
    try:
        import selenium  # type: ignore
        return True
    except Exception:
        return False

def scrape_with_selenium(url: str, wait: float = 2.0, headless: bool = True) -> List[Dict]:
    """Use Selenium to render JS and extract product cards. Requires selenium and webdriver-manager."""
    from selenium import webdriver  # type: ignore
    from selenium.webdriver.common.by import By  # type: ignore
    from selenium.webdriver.chrome.options import Options  # type: ignore
    from webdriver_manager.chrome import ChromeDriverManager  # type: ignore

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"user-agent={HEADERS['User-Agent']}")
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=opts)
    driver.set_window_size(1200, 900)
    try:
        driver.get(url)
        time.sleep(wait)
        # scroll to bottom to trigger lazy load
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait)
        elements = driver.find_elements(By.CSS_SELECTOR, "div[data-id]")
        results = []
        for el in elements:
            html = el.get_attribute("outerHTML")
            soup = BeautifulSoup(html, "lxml")
            results.append(parse_product_card(soup, base_url=url))
        return results
    finally:
        driver.quit()

# --- Public API function ---
def scrape_listing(url: str, use_selenium_if_empty: bool = True) -> List[Dict]:
    """
    Scrape a listing page URL and return list of product dicts.
    If static fetch yields no cards and use_selenium_if_empty is True, Selenium fallback is attempted.
    """
    try:
        items = scrape_static(url)
    except Exception as e:
        items = []
    # If no items found, optionally try Selenium
    if not items and use_selenium_if_empty and _selenium_available():
        try:
            items = scrape_with_selenium(url)
        except Exception:
            items = []
    return items

# --- CLI usage ---
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scrape product cards from a listing page (div[data-id] based).")
    parser.add_argument("url", help="Listing page URL to scrape")
    parser.add_argument("--selenium", action="store_true", help="Force Selenium rendering even if static fetch returns results")
    parser.add_argument("--headless", action="store_true", help="Run Selenium in headless mode when used")
    args = parser.parse_args()

    if args.selenium and not _selenium_available():
        print(json.dumps({"error": "Selenium not installed. Install selenium and webdriver-manager to use this mode."}))
        raise SystemExit(1)

    if args.selenium:
        data = scrape_with_selenium(args.url, headless=args.headless)
    else:
        data = scrape_listing(args.url, use_selenium_if_empty=True)

    print(json.dumps(data, indent=2, ensure_ascii=False))
