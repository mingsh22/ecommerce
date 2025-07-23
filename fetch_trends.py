from pytrends.request import TrendReq
import pandas as pd
import time
import random

# ✅ List your products here
products = [
    "adjustable dumbbells", "Massage Gun", "kettlebell", "yoga mat", "pull up bar",
    "pickleball paddle", "tennis racket bag", "ski goggles", "Jump Rope", "ski glove", "ski boot bag", "neck warmer"
]

pytrends = TrendReq(hl='en-US', tz=360)
batch_size = 5
all_data = {}

# ✅ Helper to fetch one batch, with retries
def get_batch_data(batch, max_retries=5):
    wait = 5  # Initial wait time in seconds
    for attempt in range(max_retries):
        try:
            pytrends.build_payload(batch)
            df = pytrends.interest_over_time()
            if 'isPartial' in df.columns:
                df = df.drop(columns=['isPartial'])
            return df
        except Exception as e:
            print(f"❌ Error on attempt {attempt+1} for batch {batch}: {e}")
            time.sleep(wait)
            wait *= 2  # Exponential backoff
    return None

# ✅ Fetch in batches
for i in range(0, len(products), batch_size):
    batch = products[i:i + batch_size]
    print(f"🔍 Fetching: {batch}")
    df_batch = get_batch_data(batch)
    if df_batch is not None:
        for col in df_batch.columns:
            all_data[col] = df_batch[col]
    time.sleep(random.uniform(15, 25))  # Random delay between 15-25 sec per batch

# ✅ Combine & Save
combined_df = pd.DataFrame(all_data)
combined_df.index.name = 'date'
combined_df.to_csv("trend_data.csv")
print("✅ Data saved to trend_data.csv")
