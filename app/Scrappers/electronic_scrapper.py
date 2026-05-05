# electronic scrapper
import json
import time
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

# --- STATIC (requests + bs4) mode ---
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0 Safari/537.36"
}

def parse_product_card(card) -> Dict[str, Optional[str]]:
    """Parse a single product card BeautifulSoup element."""
    def text(sel):
        el = card.select_one(sel)
        return el.get_text(strip=True) if el else None

    def attr(sel, attribute='href'):
        el = card.select_one(sel)
        return el.get(attribute) if el and el.has_attr(attribute) else None

    product = {}
    product['data_id'] = card.get('data-id')
    product['product_url'] = attr('a.pIpigb', 'href') or attr('a.GnxRXv', 'href')
    product['title'] = text('a.pIpigb') or text('a.GnxRXv')
    product['image'] = attr('img.UCc1lI', 'src') or attr('img.UCc1lI', 'data-src')
    product['price'] = text('.QiMO5r .hZ3P6w')
    product['original_price'] = text('.QiMO5r .kRYCnD')
    product['discount'] = text('.QiMO5r .HQe8jr span')
    product['badge'] = text('.MaiFhH .HZ0E6r') or text('.SJekt1 .JiknFv')  # fallback
    return product

def scrape_page_static(url: str) -> List[Dict]:
    """Fetch page with requests and parse product cards."""
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    cards = soup.select('div[data-id]')
    results = [parse_product_card(card) for card in cards]
    return results

# --- DYNAMIC (Selenium) mode ---
# Install: pip install selenium webdriver-manager
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    pass

def create_driver(headless: bool = True):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"user-agent={HEADERS['User-Agent']}")
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=opts)
    driver.set_window_size(1200, 900)
    return driver

def scrape_page_selenium(url: str, wait: float = 2.0) -> List[Dict]:
    driver = create_driver(headless=True)
    try:
        driver.get(url)
        time.sleep(wait)  # allow JS to render; increase if needed
        # optional: scroll to bottom to trigger lazy load
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait)

        # find product card elements by data-id attribute
        cards = driver.find_elements(By.CSS_SELECTOR, "div[data-id]")
        results = []
        for el in cards:
            html = el.get_attribute("outerHTML")
            soup = BeautifulSoup(html, "lxml")
            results.append(parse_product_card(soup))
        return results
    finally:
        driver.quit()

# --- Pagination helper (Selenium) ---
def scrape_all_pages_selenium(start_url: str, pages: int = 3, wait: float = 2.0) -> List[Dict]:
    driver = create_driver(headless=True)
    all_results = []
    try:
        driver.get(start_url)
        for page in range(pages):
            time.sleep(wait)
            # parse current page
            cards = driver.find_elements(By.CSS_SELECTOR, "div[data-id]")
            for el in cards:
                html = el.get_attribute("outerHTML")
                soup = BeautifulSoup(html, "lxml")
                all_results.append(parse_product_card(soup))
            # try to click next page button
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "a._1LKTO3, a._1LKTO3._1xI1t")  # common Flipkart next selector fallback
                next_btn.click()
            except Exception:
                # fallback: try pagination span or break
                break
        return all_results
    finally:
        driver.quit()

# --- Example usage ---
if __name__ == "__main__":
    url = "https://www.flipkart.com/toys-and-games/pr?sid=tng&q=elctronics&sort=popularity"
    # Static attempt
    try:
        items = scrape_page_static(url)
        print(json.dumps(items, indent=2))
    except Exception as e:
        print("Static fetch failed, falling back to Selenium:", e)
        items = scrape_page_selenium(url)
        print(json.dumps(items, indent=2))
