from fastapi import FastAPI, HTTPException, Path, Request
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from app.Scrappers.electronic_scrapper import scrape_page_static
from app.Scrappers.variable_url_scrapper import scrape_listing

app = FastAPI(title="Flipkart Trending Products Scraper API")

@app.get("/")
def read_root():
    return {"message": "Welcome to Flipkart Trending Products Scraper API"}

@app.get("/electronics")
@app.get("/electronics/{sort_order}")
@app.get("/electronics/{sort_order}/return={limit}")
def get_electronics(sort_order: str = "popularity", limit: int = 0):
    # Allowed sort orders on Flipkart
    valid_sorts = ["popularity", "price_asc", "price_desc", "recency_desc", "discount"]
    
    # If the user asks for a sort that flipkart supports, we use the URL directly
    sort_param = sort_order if sort_order in valid_sorts else "popularity"
    url = f"https://www.flipkart.com/toys-and-games/pr?sid=tng&q=elctronics&sort={sort_param}"
    
    try:
        items = scrape_page_static(url)
        
        # If the user asked for a custom sort that we need to handle manually in Python:
        if sort_order not in valid_sorts:
            if sort_order == "popularity_desc":
                pass # popularity is already desc by default
            elif sort_order == "title_asc":
                items.sort(key=lambda x: str(x.get('title') or ''))
            elif sort_order == "title_desc":
                items.sort(key=lambda x: str(x.get('title') or ''), reverse=True)
            elif "price" in sort_order:
                # helper to parse "₹1,299" -> 1299
                def parse_price(p):
                    if not p: return 0
                    return float(''.join(c for c in p if c.isdigit() or c == '.'))
                items.sort(key=lambda x: parse_price(x.get('price')), reverse=sort_order.endswith("desc"))

        # Apply the limit if greater than 0
        if limit > 0:
            items = items[:limit]

        return {
            "status": "success", 
            "sort_applied": sort_order, 
            "return_limit": limit,
            "total_items": len(items), 
            "data": items
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

@app.get("/variable/{sort_order}/return={limit}/{target_url:path}")
def get_variable_url(request: Request, sort_order: str, limit: int, target_url: str = Path(..., description="The URL to scrape")):
    valid_sorts = ["popularity", "price_asc", "price_desc", "recency_desc", "discount"]
    
    # If the user passes an unencoded URL like ?sid=xxx, FastAPI treats those as API query parameters.
    # We must append them back to the target_url.
    if request.query_params:
        target_url = f"{target_url}?{str(request.query_params)}"

    # Fix collapsed slashes from URL path parsing
    if target_url.startswith("http:/") and not target_url.startswith("http://"):
        target_url = target_url.replace("http:/", "http://", 1)
    if target_url.startswith("https:/") and not target_url.startswith("https://"):
        target_url = target_url.replace("https:/", "https://", 1)
        
    # If not starting with http, prepend it
    if not target_url.startswith("http"):
        target_url = "https://" + target_url

    parsed_url = urlparse(target_url)
    query_params = parse_qs(parsed_url.query)
    
    if sort_order in valid_sorts:
        query_params['sort'] = [sort_order]
        new_query = urlencode(query_params, doseq=True)
        target_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, new_query, parsed_url.fragment))

    try:
        items = scrape_listing(target_url, use_selenium_if_empty=False) # Use static only inside API to avoid hanging
        
        if sort_order not in valid_sorts:
            if sort_order == "popularity_desc":
                pass
            elif sort_order == "title_asc":
                items.sort(key=lambda x: str(x.get('title') or ''))
            elif sort_order == "title_desc":
                items.sort(key=lambda x: str(x.get('title') or ''), reverse=True)
            elif "price" in sort_order:
                def parse_price(p):
                    if not p: return 0
                    return float(''.join(c for c in p if c.isdigit() or c == '.'))
                items.sort(key=lambda x: parse_price(x.get('price')), reverse=sort_order.endswith("desc"))

        # Apply the limit if greater than 0
        if limit > 0:
            items = items[:limit]

        return {
            "status": "success",
            "sort_applied": sort_order,
            "return_limit": limit,
            "target_url": target_url,
            "total_items": len(items),
            "data": items
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


