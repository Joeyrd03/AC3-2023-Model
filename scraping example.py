import requests
from bs4 import BeautifulSoup
import json

def scrape_google_maps(query):
    base_url = "https://www.google.com/maps/search/"
    url = base_url + query.replace(" ", "+")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    data = soup.find_all("script", {"type": "application/ld+json"})
    if data:
        json_data = json.loads(data[0].string)
        return json_data
    return None

query = "restaurants in New York"
result = scrape_google_maps(query)
print(result)
