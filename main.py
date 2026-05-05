from fastapi import FastAPI, HTTPException
from app.Scrappers.electronic_scrapper import scrape_page_static

app = FastAPI(title="Flipkart Trending Products Scraper API")

@app.get("/")
def read_root():
    return {"message": "Welcome to Flipkart Trending Products Scraper API"}

@app.get("/electronics")
@app.get("/electronics/{sort_order}")
def get_electronics(sort_order: str = "popularity"):
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

        return {
            "status": "success", 
            "sort_applied": sort_order, 
            "total_items": len(items), 
            "data": items
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

