# Flipkart-scrapper
simple flipkart product scrapper written in python

A simple fast api based flikpart product scrapper.

Tech-stack :
- Fast Api
- BS4
-Requests
-Selenium (for extra features in future)
-playwright (for extra features in future)

Running build & docker container: 

docker build -t flipkart-scraper .
docker run -p 8000:8000 flipkart-scraper


ednpoints :
- http://localhost:8000/
- http://localhost:8000/electronics //specific category (only electronics)
- http://localhost:8000/electronics/{sort_order} //specific category with sort order
- http://localhost:8000/electronics/{sort_order}/return={limit} //specific category with sort order and limit
- http://localhost:8000/variable/{sort_order}/return={limit}/{target_url:path} //variable url with sort order and limit

example : 


sort_orders 

- recency_desc
- popularity_desc
- price_asc
- price_desc

run without docker:
start virtual environment 
.venv\Scripts\activate 

install dependencies 
pip install -r requirements.txt

run fast api 
uvicorn main:app --reload