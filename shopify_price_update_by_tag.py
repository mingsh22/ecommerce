import os
import requests
import sys

# =============================
# SETTINGS
# =============================
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")
SHOPIFY_TOKEN = os.getenv("SHOPIFY_API_TOKEN")
API_VERSION = "2025-01"

BASE_URL = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{API_VERSION}"
HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_TOKEN,
    "Content-Type": "application/json"
}

# =============================
# MAIN LOGIC
# =============================
def get_products_by_tag(tag):
    url = f"{BASE_URL}/products.json?limit=250"
    products = []
    while url:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        batch = resp.json().get("products", [])
        filtered = [p for p in batch if tag.lower() in p.get("tags", "").lower()]
        products.extend(filtered)
        link_header = resp.headers.get("Link", "")
        import re
        match = re.search(r'<([^>]+)>; rel="next"', link_header)
        url = match.group(1) if match else None
    return products

def update_product_price(product, multiplier):
    product_id = product["id"]
    variants = product.get("variants", [])
    for variant in variants:
        original_price = float(variant["price"])
        new_price = round(original_price * multiplier, 2)
        payload = {
            "variant": {
                "id": variant["id"],
                "price": str(new_price)
            }
        }
        resp = requests.put(f"{BASE_URL}/variants/{variant['id']}.json", headers=HEADERS, json=payload)
        resp.raise_for_status()
        print(f"✅ Updated product {product_id} variant {variant['id']} price: {original_price} → {new_price}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python shopify_price_update_by_tag.py <tag> <multiplier>")
        sys.exit(1)
    tag = sys.argv[1]
    try:
        multiplier = float(sys.argv[2])
    except ValueError:
        print("Multiplier must be a number.")
        sys.exit(1)
    products = get_products_by_tag(tag)
    print(f"Found {len(products)} products with tag '{tag}'.")
    for product in products:
        update_product_price(product, multiplier)

if __name__ == "__main__":
    main()
