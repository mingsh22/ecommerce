import csv
import os
import json
import re
from openai import OpenAI

# =============================
# SETTINGS
# =============================
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
INPUT_CSV = "shopify_export.csv"
OUTPUT_CSV = "shopify_updated.csv"
USED_HANDLES_FILE = "used_handles.txt"
USED_TITLES_FILE = "used_titles.txt"
MODEL = "gpt-4o"
WORD_COUNT = 600

# =============================
# CATEGORY TONE PRESETS
# =============================
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
def safe_json_loads(text):
    try:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            return {}
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
    except Exception as e:
        print(f"⚠️ Error guessing category: {e}")
        return "Default"

def generate_keywords(title, body):
    prompt = f"""
You are an SEO keyword expert.
From the product title and description below, find:
1. The best single primary keyword (2-4 words) that is relevant to the product and has high Google search volume.
2. 3–5 related keywords (2–3 words each) that are relevant and also trending.
Return them as JSON in this format:
{{
  "primary": "keyword here",
  "related": ["keyword1", "keyword2", "keyword3"]
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
        raw_text = response.choices[0].message.content.strip()
        data = safe_json_loads(raw_text)
        if "primary" in data and "related" in data:
            return data["primary"], data["related"]
        else:
            return "product", ["shop", "buy online", "best deal"]
    except Exception as e:
        print("⚠️ Error generating keywords:", e)
        return "product", ["shop", "buy online", "best deal"]

def generate_unique_handle(primary_kw, descriptor):
    handle_base = f"{primary_kw} {descriptor}".lower()
    handle_base = re.sub(r'[^a-z0-9\s-]', '', handle_base)
    handle_base = re.sub(r'\s+', '-', handle_base.strip())
    words = handle_base.split('-')[:5]
    handle_candidate = "-".join(words)

    # Check for duplicates
    existing = set()
    if os.path.exists(USED_HANDLES_FILE):
        with open(USED_HANDLES_FILE, "r") as f:
            existing = set(line.strip() for line in f if line.strip())

    if handle_candidate in existing:
        suffix_num = 1
        while f"{handle_candidate}-a{suffix_num}" in existing:
            suffix_num += 1
        handle_candidate = f"{handle_candidate}-a{suffix_num}"

    with open(USED_HANDLES_FILE, "a") as f:
        f.write(handle_candidate + "\n")

    return handle_candidate

def ensure_unique_title(title):
    existing = set()
    if os.path.exists(USED_TITLES_FILE):
        with open(USED_TITLES_FILE, "r") as f:
            existing = set(line.strip() for line in f if line.strip())

    new_title = title
    if new_title in existing:
        suffix_num = 1
        while f"{new_title} ({suffix_num})" in existing:
            suffix_num += 1
        new_title = f"{new_title} ({suffix_num})"

    with open(USED_TITLES_FILE, "a") as f:
        f.write(new_title + "\n")

    return new_title

def generate_product_content(title, body, category, primary_keyword, related_keywords):
    tone_info = CATEGORY_TONE_GUIDE.get(category, CATEGORY_TONE_GUIDE["Default"])
    tone_voice = tone_info["voice"]

    prompt = f"""
You are rewriting and optimizing a Shopify product description.

Rules:
- Only allowed brand name: "Sports eHarmony Living". Do not include any other brand names.
- Do NOT mention or disclose that the product is sourced from wholesalers or suppliers.
- Avoid using the word "wholesale" or related terms.
- Avoid using gender-specific words (e.g., women, men, female, male).
- Avoid very specific color mentions.
- Avoid generic hype adjectives such as "Unmatched", "Unparalleled", "World-class".
- Use genuine, product-specific adjectives like "comfortable", "supportive", "durable", "breathable".
- Do not include any URLs, image links, or references to pictures.
- Write a unique, {WORD_COUNT}+ word SEO-optimized HTML description:
  - Matches the tone: {tone_voice}
  - ~1% primary keyword density.
  - ~0.5–1% related keyword density.
  - Sentences under 20 words.
  - Shopify-compatible HTML.
- Structure dynamically based on the product category, using headings (<h2>, <h3>) and bullet points.
- Include FAQ only if relevant (2–4 questions).

Product title: {title}
Current description: {body}
Primary keyword: {primary_keyword}
Related keywords: {", ".join(related_keywords)}

Return JSON:
"description_html", "seo_title", "seo_meta".
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        raw_text = response.choices[0].message.content.strip()
        data = safe_json_loads(raw_text)
        if all(k in data for k in ("description_html", "seo_title", "seo_meta")):
            return data["description_html"], data["seo_title"], data["seo_meta"]
        else:
            return body, title, ""
    except Exception as e:
        print("⚠️ Error generating product content:", e)
        return body, title, ""

# =============================
# MAIN
# =============================
def main():
    with open(INPUT_CSV, "r", encoding="utf-8-sig") as infile, \
         open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as outfile:
        
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames

        if "SEO Title" not in fieldnames:
            fieldnames.append("SEO Title")
        if "SEO Description" not in fieldnames:
            fieldnames.append("SEO Description")
        if "Handle" not in fieldnames:
            fieldnames.append("Handle")

        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        last_main_handle = None  # store main product handle for variants

        for row in reader:
            title = row.get("Title", "").strip()
            body = row.get("Body (HTML)", "")
            category = row.get("Type", "").strip()

            if title:  # main product row
                if not category:
                    category = guess_category_from_title(title)
             
                primary_kw, related_kws = generate_keywords(title, body)
                descriptor = related_kws[0] if related_kws else "product"

                print(f"🔍 Processing main product: {title} (Category: {category}, Primary_kw: {primary_kw}, Related_kws: {related_kws})")

                new_handle = generate_unique_handle(primary_kw, descriptor)
                last_main_handle = new_handle  # save for variants

                new_desc, seo_title, seo_meta = generate_product_content(title, body, category, primary_kw, related_kws)
                seo_title = ensure_unique_title(seo_title)

                row["Body (HTML)"] = new_desc
                row["SEO Title"] = seo_title
                row["SEO Description"] = seo_meta
                row["Title"] = seo_title
                row["Handle"] = new_handle

            else:  # variant row
                if last_main_handle:
                    row["Handle"] = last_main_handle  # inherit main product handle

            writer.writerow(row)

    print(f"✅ Done! Updated CSV saved as '{OUTPUT_CSV}' with handles & titles logged.")

if __name__ == "__main__":
    main()

