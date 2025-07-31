import csv
import os
import json
import re
from openai import OpenAI

# =============================
# SETTINGS
# =============================
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
INPUT_CSV = "products_export.csv"
OUTPUT_CSV = "products_updated.csv"
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
    "Home & Living": {
        "voice": "Warm, inviting, lifestyle-focused tone",
        "common_sections": ["Why You'll Love It", "Perfect For", "Care Instructions", "Customer Stories"]
    },
    "Electronics": {
        "voice": "Technical, informative but user-friendly tone",
        "common_sections": ["Why This Device Stands Out", "Specifications", "How to Use", "Pro Tips for Best Results"]
    },
    "Exercise Equipment & Recovery": {
        "voice": "Motivational, confident, and empowering tone that inspires fitness progress and emphasizes durability, safety, and performance benefits.",
        "common_sections": [
            "Enhance Your Training",
            "Why This Equipment Works",
            "Ideal For",
            "Key Features",
            "Care & Maintenance Tips",
            "How to Get Started"
        ]
    },
    "Workout Accessories": {
        "voice": "Supportive, energetic, and practical tone that encourages an active lifestyle and highlights how accessories improve workouts, comfort, and convenience.",
        "common_sections": [
            "Elevate Your Workout",
            "Why You'll Love This Accessory",
            "Perfect For",
            "Key Benefits",
            "Product Specifications",
            "Tips for Best Results"
        ]
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
- Home & Living
- Electronics
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
            print("⚠️ Keyword JSON incomplete, using defaults")
            return "product", ["shop", "buy online", "best deal"]
    except Exception as e:
        print("⚠️ Error generating keywords:", e)
        return "product", ["shop", "buy online", "best deal"]

def generate_product_content(title, body, category, image_url, primary_keyword, related_keywords):
    tone_info = CATEGORY_TONE_GUIDE.get(category, CATEGORY_TONE_GUIDE["Default"])
    tone_voice = tone_info["voice"]
    common_sections = ", ".join(tone_info["common_sections"])

    prompt = f"""
You are rewriting and optimizing a Shopify product description.

Please follow these rules carefully:

- Do NOT mention or disclose that the product is sourced from other wholesalers or suppliers. Present the product as if it comes directly from the source.
- Avoid using the word "wholesale" or any related terms anywhere in the description.
- Avoid using gender-specific words such as "women," "men," "female," or "male."
- Avoid mentioning very specific colors or color details.
- Avoid generic hype adjectives such as "Unmatched," "Unparalleled," "World-class," or similar superlatives.
- Use genuine, product-specific adjectives like "comfortable," "supportive," "durable," or "breathable" based on the product details.
- Do not include any URLs, image links, or references to pictures in the description.
- Write a unique, {WORD_COUNT}+ word SEO-optimized HTML description that:
  - Matches the tone: {tone_voice}
  - Maintains ~1% primary keyword density.
  - Maintains ~0.5–1% related keyword density.
  - Uses sentences under 20 words.
  - Is Shopify-compatible HTML.
- Use a semi-dynamic structure based on the product category, including headings (<h2>, <h3>) and bullet points.
- Include an FAQ only if relevant (2–4 questions).
- Do not mention the presence of images or external links.

Product title: {title}
Current description: {body}
Primary keyword: {primary_keyword}
Related keywords: {", ".join(related_keywords)}
Image URL: {image_url if image_url else 'No image provided'}

Return the result in JSON format with keys:
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
            print("⚠️ Content JSON incomplete, returning original description")
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

        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            title = row.get("Title", "").strip()
            body = row.get("Body (HTML)", "")
            image = row.get("Image Src", "")
            category = row.get("Type", "").strip()

            if not category and title:
                category = guess_category_from_title(title)

            if title:  # Process only main product rows
                print(f"🔍 Processing main product: {title} (Category: {category})")
                primary_kw, related_kws = generate_keywords(title, body)
                new_desc, seo_title, seo_meta = generate_product_content(
                    title, body, category, image, primary_kw, related_kws
                )

                row["Body (HTML)"] = new_desc
                row["SEO Title"] = seo_title
                row["SEO Description"] = seo_meta
                row["Title"] = seo_title  # Sync Title to SEO Title

            writer.writerow(row)

    print(f"✅ Done! Updated CSV saved as '{OUTPUT_CSV}' ready for Shopify import.")

if __name__ == "__main__":
    main()

