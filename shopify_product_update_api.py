# 📜 Script Summary – Shopify Product Processing with AI & Duplicate Protection
# This script automates the updating of new Shopify products (imported from DSers and set to Draft), using the Shopify Admin API and OpenAI GPT to optimize titles, descriptions, SEO metadata, and handles while preventing duplicates.
# 
# 1️⃣ Shopify Connection & Settings
# Environment Variables:
# 
# SHOPIFY_STORE → Your Shopify store subdomain (e.g., my-store-name)
# 
# SHOPIFY_TOKEN → Shopify Admin API Access Token
# 
# OPENAI_API_KEY → OpenAI API Key
# 
# API Version: Uses 2025-01 for compatibility with Shopify Admin API.
# 
# Headers: Adds X-Shopify-Access-Token for authentication.
# 
# 2️⃣ Category Tone Guide
# Maintains a dictionary of product categories (Sportswear, Exercise Equipment & Recovery, Workout Accessories, Default)
# 
# Each category defines:
# 
# Voice/Tone for writing.
# 
# Common Sections to structure the description.
# 
# 3️⃣ Duplicate Prevention
# In-memory sets:
# 
# existing_handles & existing_titles → Loaded from all products in Shopify at script start.
# 
# seen_handles & seen_titles → Tracks handles/titles generated during the current script run.
# 
# Prevents duplication by checking against both current run and store-wide data.
# 
# Uses incremental suffixing (e.g., handle, handle-1, handle-2) until a unique one is found.
# 
# 4️⃣ Data Preloading
# preload_existing_handles_titles()
# 
# Calls /products.json in multiple pages until all products are fetched.
# 
# Saves existing handles and titles into sets for fast duplicate checking.
# 
# 5️⃣ Filtering Target Products
# get_draft_dsers_products():
# 
# Fetches products with status=draft.
# 
# Filters to only those containing the tag dsers-new (case-insensitive).
# 
# Ensures only newly imported DSers products are processed.
# 
# 6️⃣ AI-Powered Processing
# a) Guess Category
# guess_category_from_title():
# 
# Sends title to GPT to predict category from 4 fixed options.
# 
# Defaults to "Default" if GPT output is invalid.
# 
# b) Extract Keywords
# generate_keywords():
# 
# Uses GPT to extract:
# 
# Primary Keyword (2–4 words, high search volume).
# 
# 3–5 Related Keywords.
# 
# Returns defaults if GPT fails.
# 
# c) Generate Unique Handle
# generate_unique_handle():
# 
# Builds a slug from primary keyword + first related keyword.
# 
# Strips special characters, limits to 5 words.
# 
# Ensures uniqueness by checking against:
# 
# Already processed handles (seen_handles).
# 
# Shopify store-wide handles (existing_handles).
# 
# d) Ensure Unique Title
# ensure_unique_title():
# 
# Removes "Sports eHarmony Living" from title.
# 
# Avoids duplicates by checking against:
# 
# Already processed titles (seen_titles).
# 
# Shopify store-wide titles (existing_titles).
# 
# Adds numeric suffix (1), (2), etc. if needed.
# 
# e) Rewrite Product Content
# generate_product_content():
# 
# Uses GPT to rewrite and optimize product description with rules:
# 
# Do NOT:
# 
# Use "Sports eHarmony Living" in title.
# 
# Mention customization or shipping.
# 
# Use gender-specific words.
# 
# Mention exact colors.
# 
# Use hype words like "unmatched".
# 
# Must:
# 
# Have ≥600 words.
# 
# Use ~1% density for primary keyword.
# 
# Use ~0.5–1% density for related keywords.
# 
# Format in Shopify HTML.
# 
# Returns:
# 
# New description_html.
# 
# SEO title.
# 
# SEO meta description.
# 
# 7️⃣ Shopify Updates
# For each product:
# 
# Logs:
# 
# Prints original title, primary keyword, related keywords, and tone guide for verification.
# 
# Updates Product:
# 
# shopify_update_product() updates:
# 
# Title.
# 
# Body HTML.
# 
# Handle.
# 
# SEO Title Tag.
# 
# SEO Meta Description Tag.
# 
# Redirects:
# 
# If handle changes, shopify_create_redirect() creates a permanent redirect from old → new handle.
# 
# Removes dsers-new Tag:
# 
# shopify_remove_dsers_tag() removes dsers-new while preserving all other tags, ensuring the product isn’t reprocessed in future runs.
# 
# 8️⃣ Execution Flow
# Preload all existing handles & titles from Shopify.
# 
# Get only draft products with dsers-new tag.
# 
# For each product:
# 
# Guess category.
# 
# Generate keywords.
# 
# Generate unique handle.
# 
# Ensure unique title.
# 
# Generate optimized description + SEO metadata.
# 
# Update product via Shopify API.
# 
# Create redirect if handle changed.
# 
# Remove dsers-new tag.
# 
# Print a confirmation log for each product updated.
# 
# ✅ Key Benefits
# No CSV export/import needed → Direct Shopify API updates.
# 
# Fast duplicate prevention via preloading store data.
# 
# SEO-optimized content automatically generated.
# 
# Zero reprocessing — products lose dsers-new tag after first run.
# 
# Redirect safety when changing handles (preserves SEO & bookmarks).
# 
# Full logging for tracking what was updated.


import os
import re
import json
import requests
from openai import OpenAI
from urllib.parse import quote

# =============================
# SETTINGS
# =============================
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE")  # e.g., "my-store-name"
SHOPIFY_TOKEN = os.getenv("SHOPIFY_API_TOKEN")  # Admin API Access Token
API_VERSION = "2025-01"

BASE_URL = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/{API_VERSION}"
HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_TOKEN,
    "Content-Type": "application/json"
}

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
WORD_COUNT = 600
MODEL = "gpt-4o"

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
# MEMORY FOR DUPLICATES
# =============================
seen_handles = set()
seen_titles = set()
existing_handles = set()
existing_titles = set()

# =============================
# SHOPIFY HELPERS
# =============================
def preload_existing_handles_titles():
    """Fetch all existing product handles and titles using cursor-based pagination."""
    url = f"{BASE_URL}/products.json?limit=250"
    
    while url:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        
        products = resp.json().get("products", [])
        for p in products:
            existing_handles.add(p["handle"].strip().lower())
            existing_titles.add(p["title"].strip().lower())
        
        # Check for next page in Link header
        link_header = resp.headers.get("Link", "")
        next_url = None
        if 'rel="next"' in link_header:
            match = re.search(r'<([^>]+)>; rel="next"', link_header)
            if match:
                next_url = match.group(1)
        url = next_url
    
    print(f"📦 Preloaded {len(existing_handles)} handles and {len(existing_titles)} titles from Shopify.")

def get_draft_dsers_products():
    """Get only draft products with tag 'dsers-new'."""
    url = f"{BASE_URL}/products.json?status=draft&limit=250"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    products = resp.json().get("products", [])
    filtered = [p for p in products if any("dsers-new" in t.lower() for t in p.get("tags", "").split(","))]
    print(f"📋 Found {len(filtered)} draft products tagged 'dsers-new'.")
    return filtered

def shopify_update_product(product_id, title, body_html, handle, seo_title, seo_meta):
    payload = {
        "product": {
            "id": product_id,
            "title": title,
            "body_html": body_html,
            "handle": handle,
            "metafields_global_title_tag": seo_title,
            "metafields_global_description_tag": seo_meta
        }
    }
    resp = requests.put(f"{BASE_URL}/products/{product_id}.json", headers=HEADERS, json=payload)
    resp.raise_for_status()
    print(f"✅ Updated product {product_id} → {title}")

def shopify_create_redirect(old_handle, new_handle):
    payload = {
        "redirect": {
            "path": f"/products/{old_handle}",
            "target": f"/products/{new_handle}"
        }
    }
    resp = requests.post(f"{BASE_URL}/redirects.json", headers=HEADERS, json=payload)
    resp.raise_for_status()
    print(f"🔄 Redirect created: {old_handle} → {new_handle}")

def shopify_remove_dsers_tag(product_id, tags):
    """Remove dsers-new tag but keep others."""
    updated_tags = [t.strip() for t in tags.split(",") if t.strip().lower() != "dsers-new"]
    payload = {
        "product": {
            "id": product_id,
            "tags": ", ".join(updated_tags)
        }
    }
    resp = requests.put(f"{BASE_URL}/products/{product_id}.json", headers=HEADERS, json=payload)
    resp.raise_for_status()
    print(f"🏷️ Removed 'dsers-new' tag from product {product_id}")

# =============================
# AI HELPERS
# =============================
def safe_json_loads(text):
    try:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(json_match.group()) if json_match else {}
    except Exception as e:
        print(f"⚠️ JSON parse error: {e}")
        return {}

def guess_category_from_title(title):
    prompt = f"""
Given this product title, guess the best category from:
- Sportswear
- Exercise Equipment & Recovery
- Workout Accessories
- Default

Return exactly one category name.
Title: "{title}"
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        cat = response.choices[0].message.content.strip()
        return cat if cat in CATEGORY_TONE_GUIDE else "Default"
    except:
        return "Default"

def generate_keywords(title, body):
    prompt = f"""
From the title and description, find:
1. Primary keyword (2-4 words, high search volume)
2. 3–5 related keywords
Return JSON:
{{
  "primary": "keyword",
  "related": ["kw1", "kw2", "kw3"]
}}

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
    base = f"{primary_kw} {descriptor}".lower()
    base = re.sub(r'[^a-z0-9\s-]', '', base)
    base = re.sub(r'\s+', '-', base.strip())
    base = "-".join(base.split('-')[:5])
    candidate = base
    suffix = 1
    while candidate in seen_handles or candidate in existing_handles:
        print(f"⚠️ Duplicate handle '{candidate}', trying new one...")
        candidate = f"{base}-{suffix}"
        suffix += 1
    seen_handles.add(candidate)
    existing_handles.add(candidate)
    return candidate

def ensure_unique_title(title):
    title = title.replace("Sports eHarmony Living", "").strip()
    candidate = title
    suffix = 1
    while candidate.lower() in seen_titles or candidate.lower() in existing_titles:
        print(f"⚠️ Duplicate title '{candidate}', trying new one...")
        candidate = f"{title} ({suffix})"
        suffix += 1
    seen_titles.add(candidate.lower())
    existing_titles.add(candidate.lower())
    return candidate

def generate_product_content(title, body, category, primary_kw, related_kws):
    tone_info = CATEGORY_TONE_GUIDE.get(category, CATEGORY_TONE_GUIDE["Default"])
    voice = tone_info["voice"]
    sections = ", ".join(tone_info["common_sections"])

    prompt = f"""
- Write a unique, SEO‑optimized HTML product description for Shopify. 
- The description must be at least {WORD_COUNT} words, with approximately 1% density for the primary keyword and 0.5–1% density for each related keyword. 
- Use the following voice/tone: {voice}
- Organize the content with sections similar to: {sections}

Follow these rules exactly:
- Do not include images, picture tags, or any gallery section.
- Do not bold any keywords unless they are inside <h2> or <h3> headings.
- Do not use words like “Conclusion” in any <h2> or <h3> heading.
- Do not include a size table or size chart section.
- Do not mention customer support, returns, customization options, or shipping details.
- Do not include the brand name “Sports eHarmony Living” in the title.
- Avoid gender‑specific terms (e.g., “men’s,” “women’s”) and avoid specifying colors.
- Avoid generic hype words such as “unmatched,” “best ever,” “amazing quality,” etc.
- Ensure the HTML is valid and Shopify‑compatible.
- At the end of the description, include 2–3 relevant FAQs.

Title: {title}
Description: {body}
Primary keyword: {primary_kw}
Related keywords: {", ".join(related_kws)}

Return JSON: description_html, seo_title, seo_meta
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
    preload_existing_handles_titles()
    products = get_draft_dsers_products()

    for p in products:
        old_handle = p["handle"]
        old_title = p["title"]
        tags = p.get("tags", "")
        body = p.get("body_html", "")
        category = p.get("product_type", "") or guess_category_from_title(old_title)

        primary_kw, related_kws = generate_keywords(old_title, body)
        descriptor = related_kws[0] if related_kws else "product"

        print("\n====================")
        print(f"Title: {old_title}")
        print(f"Primary keyword: {primary_kw}")
        print(f"Related keywords: {related_kws}")
        print(f"Category tone: {CATEGORY_TONE_GUIDE[category]}")
        print("====================\n")

        new_handle = generate_unique_handle(primary_kw, descriptor)
        new_desc, seo_title, seo_meta = generate_product_content(old_title, body, category, primary_kw, related_kws)
        seo_title = ensure_unique_title(seo_title)

        shopify_update_product(p["id"], seo_title, new_desc, new_handle, seo_title, seo_meta)

        if new_handle != old_handle:
            shopify_create_redirect(old_handle, new_handle)

        # Remove the 'dsers-new' tag so we don't process it again
        shopify_remove_dsers_tag(p["id"], tags)

if __name__ == "__main__":
    main()

