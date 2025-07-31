import requests
import os

# ====== CONFIG ======
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")  # e.g. myshop
ACCESS_TOKEN = os.getenv("SHOPIFY_API_TOKEN")  # from private/custom app
API_VERSION = "2025-01"

BASE_URL = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{API_VERSION}"
HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": ACCESS_TOKEN
}

# ====== TEST FUNCTION ======
def test_shopify_api():
    url = f"{BASE_URL}/products.json?limit=5&fields=id,title,handle"
    resp = requests.get(url, headers=HEADERS)

    if resp.status_code == 200:
        products = resp.json().get("products", [])
        print(f"✅ API connection successful! Found {len(products)} products.")
        for p in products:
            print(f"ID: {p['id']}, Title: {p['title']}, Handle: {p['handle']}")
    else:
        print(f"❌ API connection failed. Status: {resp.status_code}")
        print(resp.text)

# ====== RUN TEST ======
if __name__ == "__main__":
    test_shopify_api()
