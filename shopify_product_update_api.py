# Summary of the Python Script
# Fetches all draft Shopify products tagged dsers-new using the Shopify Admin API, handling pagination.
# 
# For each product:
# Uses OpenAI to generate:
# SEO-optimized primary and related keywords.
# A rewritten, unique, SEO-friendly product description in Shopify-compatible HTML.
# Automatically guesses product category if missing, to guide tone and style.
# Generates a unique SEO-friendly handle based on keywords, avoiding duplicates by tracking used handles in a file.
# Ensures the new SEO title is unique by checking and incrementing duplicates using a persistent log.
# Updates the product via Shopify API with:
# New title, description (Body HTML), handle.
# SEO meta title and description (stored in metafields).
# Removes the dsers-new tag to prevent reprocessing.
# If the product handle changes, creates a Shopify URL redirect from the old handle to the new handle to preserve SEO juice.
# Logs every product update (product ID, old/new handle, old/new title) to a CSV file for audit and tracking.
# The script includes error handling and JSON parsing safeguards, and respects Shopify API rate limits by pausing between requests.
# Uses environment variables to securely load Shopify store name, API token, and OpenAI API key.

import os
import re
import json
import csv
import time
import requests
from openai import OpenAI

# =============================
# SETTINGS
# =============================
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE", "your-store-name")  # e.g. myshop
ACCESS_TOKEN = os.getenv("SHOPIFY_API_TOKEN", "your-access-token")
API_VERSION = "2025-07"
MODEL = "gpt-4o"
WORD_COUNT = 600

USED_HANDLES_FILE = "used_handles.txt"
USED_TITLES_FILE = "used_titles.txt"
LOG_FILE = "product_update_log.csv"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

BASE_URL = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{API_VERSION}"
HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": ACCESS_TOKEN
}

CATEGORY_TONE_GUIDE = {
    "Sportswear": {
        "voice": "Energetic, motivational, active lifestyle tone",
        "common_sections": ["Benefits You'll Enjoy", "Perfect For", "Specifications", "Pro Tips for Best Results"]
    },
    "Exercise Equipment & Recovery": {
        "voice": "Motivational, confident, empowering tone focusing on durability, safety, and performance.",
        "common_sections": ["Enhance Your Training", "Why This Equipment Works", "Ideal For", "Key Features", "Care & Maintenance Tips", "How to Get Started"]
    },
    "Workout Accessories": {
        "voice": "Supportive, energetic, practical tone highlighting how accessories improve workouts, comfort, and convenience.",
        "common_sections": ["Elevate Your Workout", "Why You'll Love This Accessory", "Perfect For", "Key Benefits", "Product Specifications", "Tips for Best Results"]
    },
    "Default": {
        "voice": "Friendly and persuasive product marketing tone",
        "common_sections": ["Benefits You'll Enjoy", "Why This Product Stands Out", "Perfect For", "Specifications"]
    }
}

# =============================
# HELPERS
# =============================
def shopify_get_draft_products_with_tag(tag):
    """Fetch draft products with specific tag."""
    products = []
    url = f"{BASE_URL}/products.json?status=draft&limit=250&fields=id,title,body_html,handle,product_type,tags"
    while url:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        for p in data.get("products", []):
            tags = p.get("tags", "")
            tag_list = [t.strip().lower() for t in tags.split(",")] if tags else []
            if tag.lower() in tag_list:
                products.append(p)

        # Pagination
        link_header = resp.headers.get("Link")
        if link_header and 'rel="next"' in link_header:
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    url = part[part.find("<")+1:part.find(">")]
                    break
        else:
            url = None
    return products

def shopify_update_product(product_id, title, body_html, handle, seo_title, seo_desc, old_tags):
    """Update product info and remove the 'dsers-new' tag."""
    # Remove 'dsers-new' tag (case insensitive)
    tags = [t.strip() for t in old_tags.split(",")] if old_tags else []
    tags = [t for t in tags if t.lower() != "dsers-new"]
    new_tags = ", ".join(tags)

    payload = {
        "product": {
            "id": product_id,
            "title": title,
            "body_html": body_html,
            "handle": handle,
            "tags": new_tags,
            "metafields_global_title_tag": seo_title,
            "metafields_global_description_tag": seo_desc
        }
    }
    resp = requests.put(f"{BASE_URL}/products/{product_id}.json", headers=HEADERS, json=payload)
    if resp.status_code == 200:
        print(f"✅ Updated product {product_id}")
    else:
        print(f"⚠️ Failed to update product {product_id}: {resp.text}")

def shopify_create_redirect(old_handle, new_handle):
    """Create redirect for SEO."""
    payload = {
        "redirect": {
            "path": f"/products/{old_handle}",
            "target": f"/products/{new_handle}"
        }
    }
    resp = requests.post(f"{BASE_URL}/redirects.json", headers=HEADERS, json=payload)
    if resp.status_code == 201:
        print(f"🔀 Redirect created: {old_handle} -> {new_handle}")
    else:
        print(f"⚠️ Failed to create redirect: {resp.text}")

def safe_json_loads(text):
    try:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(json_match.group()) if json_match else {}
    except Exception as e:
        print(f"⚠️ JSON parse error: {e}")
        return {}

def guess_category_from_title(title):
    prompt = f"""
You are an expert product categorizer.
Given this product title, guess the best product category from this list:
- Sportswear
- Exercise Equipment & Recovery
- Workout Accessories
- Default

Return exactly one category name from the list above.

Product Title: "{title}"
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        category_guess = response.choices[0].message.content.strip()
        return category_guess if category_guess in CATEGORY_TONE_GUIDE else "Default"
    except:
        return "Default"

def generate_keywords(title, body):
    prompt = f"""
You are an SEO keyword expert.
From the product title and description below, find:
1. Primary keyword (2–4 words) with high search volume.
2. 3–5 related keywords (2–3 words).

Return JSON:
{{ "primary": "keyword", "related": ["kw1", "kw2", "kw3"] }}

Title: {title}
Description: {body}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        data = safe_json_loads(response.choices[0].message.content.strip())
        return data.get("primary", "product"), data.get("related", ["shop", "buy online", "best deal"])
    except:
        return "product", ["shop", "buy online", "best deal"]

def generate_unique_handle(primary_kw, descriptor):
    handle_base = f"{primary_kw} {descriptor}".lower()
    handle_base = re.sub(r'[^a-z0-9\s-]', '', handle_base)
    handle_base = re.sub(r'\s+', '-', handle_base.strip())
    words = handle_base.split('-')[:5]
    handle_candidate = "-".join(words)

    existing = set()
    if os.path.exists(USED_HANDLES_FILE):
        with open(USED_HANDLES_FILE, "r") as f:
            existing = set(line.strip() for line in f)

    if handle_candidate in existing:
        suffix = 1
        while f"{handle_candidate}-a{suffix}" in existing:
            suffix += 1
        handle_candidate = f"{handle_candidate}-a{suffix}"

    with open(USED_HANDLES_FILE, "a") as f:
        f.write(handle_candidate + "\n")

    return handle_candidate

def ensure_unique_title(title):
    existing = set()
    if os.path.exists(USED_TITLES_FILE):
        with open(USED_TITLES_FILE, "r") as f:
            existing = set(line.strip() for line in f)

    new_title = title
    if new_title in existing:
        suffix = 1
        while f"{new_title} ({suffix})" in existing:
            suffix += 1
        new_title = f"{new_title} ({suffix})"

    with open(USED_TITLES_FILE, "a") as f:
        f.write(new_title + "\n")

    return new_title

def generate_product_content(title, body, category, primary_kw, related_kws):
    tone_info = CATEGORY_TONE_GUIDE.get(category, CATEGORY_TONE_GUIDE["Default"])
    prompt = f"""
You are rewriting and optimizing a Shopify product description.

Rules:
- Only allowed brand name: "Sports eHarmony Living"
- No gender-specific words.
- Avoid specific colors.
- Avoid hype adjectives.
- Unique, {WORD_COUNT}+ words SEO HTML.
- ~1% primary keyword, 0.5–1% related keywords.
- Headings and bullet points.
- FAQs only if relevant.

Product title: {title}
Description: {body}
Primary keyword: {primary_kw}
Related keywords: {", ".join(related_kws)}

Return JSON: "description_html", "seo_title", "seo_meta".
"""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        data = safe_json_loads(response.choices[0].message.content.strip())
        return data.get("description_html", body), data.get("seo_title", title), data.get("seo_meta", "")
    except:
        return body, title, ""

# =============================
# MAIN
# =============================
def main():
    tag_to_process = "dsers-new"
    products = shopify_get_draft_products_with_tag(tag_to_process)

    if not products:
        print(f"No draft products found with tag '{tag_to_process}'.")
        return

    with open(LOG_FILE, "w", newline="", encoding="utf-8-sig") as logf:
        logwriter = csv.writer(logf)
        logwriter.writerow(["Product ID", "Old Handle", "New Handle", "Old Title", "New Title"])

        for p in products:
            old_handle = p["handle"]
            old_title = p["title"]
            body = p.get("body_html", "") or ""
            category = p.get("product_type", "") or guess_category_from_title(old_title)
            old_tags = p.get("tags", "")

            primary_kw, related_kws = generate_keywords(old_title, body)
            descriptor = related_kws[0] if related_kws else "product"
            new_handle = generate_unique_handle(primary_kw, descriptor)

            new_desc, seo_title, seo_meta = generate_product_content(old_title, body, category, primary_kw, related_kws)
            seo_title = ensure_unique_title(seo_title)

            shopify_update_product(p["id"], seo_title, new_desc, new_handle, seo_title, seo_meta, old_tags)

            if new_handle != old_handle:
                shopify_create_redirect(old_handle, new_handle)

            logwriter.writerow([p["id"], old_handle, new_handle, old_title, seo_title])

            # To respect API rate limits
            time.sleep(0.5)

    print(f"✅ Done! Processed {len(products)} products. Log saved to '{LOG_FILE}'.")

if __name__ == "__main__":
    main()

