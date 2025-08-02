import os
import re
import json
import requests
from openai import OpenAI

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
    url = f"{BASE_URL}/products.json?limit=250"
    while url:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        products = resp.json().get("products", [])
        for p in products:
            existing_handles.add(p["handle"].strip().lower())
            existing_titles.add(p["title"].strip().lower())
        link_header = resp.headers.get("Link", "")
        match = re.search(r'<([^>]+)>; rel="next"', link_header)
        url = match.group(1) if match else None
    print(f"📦 Preloaded {len(existing_handles)} handles and {len(existing_titles)} titles.")

def get_draft_dsers_products():
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
    updated_tags = [t.strip() for t in tags.split(",") if t.strip().lower() != "dsers-new"]
    payload = {"product": {"id": product_id, "tags": ", ".join(updated_tags)}}
    resp = requests.put(f"{BASE_URL}/products/{product_id}.json", headers=HEADERS, json=payload)
    resp.raise_for_status()
    print(f"🏷️ Removed 'dsers-new' tag from product {product_id}")

# =============================
# AI HELPERS
# =============================
def safe_json_loads(text):
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(match.group()) if match else {}
    except:
        return {}

def guess_category_from_title(title):
    prompt = f"Given this product title, choose from Sportswear, Exercise Equipment & Recovery, Workout Accessories, or Default.\nReturn only the category.\nTitle: {title}"
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        cat = resp.choices[0].message.content.strip()
        return cat if cat in CATEGORY_TONE_GUIDE else "Default"
    except:
        return "Default"

def generate_keywords(title, body):
    # prompt = f"From the title and description, extract primary keyword (2-4 words) and 3–5 related keywords.\nReturn JSON."
    prompt = f"""
From the title and body, extract:
1. Primary keyword (2–4 words, must describe the actual product type, e.g., "tennis skirt", "sports bra").
2. 3–5 related keywords that are relevant to SEO for this product.
3. Return JSON in format like below:
{{
  "primary": "tennis skirt",
  "related": ["high waist tennis skirt", "breathable sports skirt", "yoga skirt", "golf skirt"]
}}

title: {title}
body: {body}
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        data = safe_json_loads(resp.choices[0].message.content.strip())
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
        candidate = f"{base}-{suffix}"
        suffix += 1
    seen_handles.add(candidate)
    existing_handles.add(candidate)
    return candidate

def regenerate_unique_title_via_ai(base_title, primary_kw, related_kws):
    prompt = f"""
The current product title "{base_title}" is a duplicate.
Generate a new, unique, SEO-friendly title that:
- Begin with the actual product type (e.g., "Sports Bra", "Tennis Skirt", "Yoga Pants") as detected from the primary_kw.
- Only allowed special characters in title: "-" and "&"
- Avoid any generic marketing lead-ins like "Shop the", "Stay Active with", "Discover our", "Experience", "Buy now".
- Uses the primary keyword: {primary_kw}
- Optionally uses 1–2 related keywords: {", ".join(related_kws)}
- Max length 70 chars
- Avoid forbidden terms, colors, gender-specific words, hype words
- No brand name "Sports eHarmony Living"
- Keep the title focused on describing the product clearly.
Return only the title.
"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return resp.choices[0].message.content.strip()
    except:
        return base_title

def ensure_unique_title(title, primary_kw, related_kws):
    title = title.replace("Sports eHarmony Living", "").strip()
    candidate = title
    attempt = 1
    while candidate.lower() in seen_titles or candidate.lower() in existing_titles:
        print(f"⚠️ Duplicate title '{candidate}', regenerating (Attempt {attempt})...")
        candidate = regenerate_unique_title_via_ai(title, primary_kw, related_kws)
        attempt += 1
        if attempt > 5:
            print("⚠️ Could not generate unique title after 5 attempts, adding suffix.")
            candidate = f"{title} ({attempt})"
            break
    seen_titles.add(candidate.lower())
    existing_titles.add(candidate.lower())
    return candidate

def generate_product_content(title, body, category, primary_kw, related_kws):
    tone_info = CATEGORY_TONE_GUIDE.get(category, CATEGORY_TONE_GUIDE["Default"])
    voice = tone_info["voice"]
    sections = ", ".join(tone_info["common_sections"])
    prompt = f"""
First, generate an SEO title that:
1. Begins with the product type (e.g., "Sports Bra", "Tennis Skirt", "Yoga Pants") as inferred from the primary_kw.
2. Avoid generic lead-ins such as "Shop the", "Stay Active with", "Discover our", "Experience".
3. Uses the primary keyword: {primary_kw}.
4. Optionally includes 1–2 related keywords: {", ".join(related_kws)}.
5. Keeps under 70 characters.
6. Avoids forbidden terms, gender-specific words, color names, hype words, and the brand name "Sports eHarmony Living".
7. Focuses on the product itself.
8. Only allowed special characters in title: "-" and "&"

Then, write a unique, SEO-optimized HTML product description for Shopify.
- At least {WORD_COUNT} human readble words
- ~1% primary keyword: {primary_kw}
- 0.5–1% each related keyword: {", ".join(related_kws)}
- Tone: {voice}
- Sections: {sections}
- No html tag apply to any of primary keyword and related keywords
- No "Conclusion" in headings
- No size charts, customer support, shipping, brand name, gender terms, colors, hype words
- Must be valid Shopify HTML
- End with 2–3 relevant FAQs.
- Use Bold font for FAQ questions.
- Do not include images, picture tags, or any gallery section.
Return JSON: description_html, seo_title, seo_meta
"""
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        data = safe_json_loads(resp.choices[0].message.content.strip())
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

        new_handle = generate_unique_handle(primary_kw, descriptor)
        new_desc, seo_title, seo_meta = generate_product_content(
            old_title, body, category, primary_kw, related_kws
        )

        # Ensure SEO title includes primary keyword
        if primary_kw.lower() not in seo_title.lower():
            seo_title = f"{primary_kw} - {seo_title}"

        # Ensure title uniqueness
        seo_title = ensure_unique_title(seo_title, primary_kw, related_kws)

        # 🆕 Print processing preview
        print("\n==============================")
        print(f"🆕 Processing Product ID: {p['id']}")
        print(f"Old Title: {old_title}")
        print(f"New Title: {seo_title}")
        print(f"Category: {category}")
        print(f"Tone: {CATEGORY_TONE_GUIDE.get(category, CATEGORY_TONE_GUIDE['Default'])['voice']}")
        print(f"Primary Keyword: {primary_kw}")
        print(f"Related Keywords: {related_kws}")
        print(f"New Handle: {new_handle}")
        print("==============================\n")

        shopify_update_product(p["id"], seo_title, new_desc, new_handle, seo_title, seo_meta)

        if new_handle != old_handle:
            try:
                shopify_create_redirect(old_handle, new_handle)
            except requests.exceptions.HTTPError as e:
                print(f"⚠️ Redirect creation failed for {old_handle} → {new_handle}: {e}")

        shopify_remove_dsers_tag(p["id"], tags)

if __name__ == "__main__":
    main()

