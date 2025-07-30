import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import linregress

# Load from CSV
df = pd.read_csv("trend_data.csv", parse_dates=["date"])
df.set_index("date", inplace=True)

# Rebuild dictionary
trend_dict = {col: df[col] for col in df.columns}

# Products to analyze
# products_to_plot = [
#     "adjustable dumbbells", "Massage Gun", "kettlebell", "yoga mat", "pull up bar",
#     "pickleball paddle", "tennis racket bag", "ski goggles", "Jump Rope", "ski glove", "ski boot bag", "neck warmer"
# ]

products_to_plot = [
    "adjustable dumbbells",
    "Massage Gun",
    "kettlebell",
    "yoga mat",
    "pull up bar",
    "pickleball paddle",
    "tennis racket bag",
    "ski goggles",
    "Jump Rope",
    "ski glove",
    "ski boot bag",
    "neck warmer",
    "Resistance Band",
    "Weighted Vest",
    "Ab Roller",
    "Yoga Blocks",
    "Fitness Tracker",
    "Foam Roller",
    "Pull-Up Bar",
    "Ankle Weights",
    "Battle Ropes",
    "Collapsible Water Bottle",
    "Grip Strengthener",
    "Balance Pad",
    "Protein Shaker",
    "Jump Box",
    "Under-Desk Elliptical",
]

underperforming_keywords = []
goodperforming_keywords = []

# Analyze trends
for product in products_to_plot:
    trend = trend_dict[product].dropna()
    avg = trend.mean()

    # Calculate linear trend slope
    x = (trend.index - trend.index[0]).days
    slope, intercept, r_value, p_value, std_err = linregress(x, trend)

    # Define what "underperforming" means
    # if avg < 20 or slope < 0:
    if avg < 20:
        underperforming_keywords.append({
            "keyword": product,
            "average_score": round(avg, 1),
            "slope": round(slope, 3)
        })
    else:
         goodperforming_keywords.append({
            "keyword": product,
            "average_score": round(avg, 1),
            "slope": round(slope, 3)
        })

# Show underperformers
print("Underperforming Keywords (low average):")
for kw in underperforming_keywords:
    print(f"- {kw['keyword']}: Avg={kw['average_score']}, Slope={kw['slope']}")

# Show goodperformers
print("Goodperforming Keywords (high average):")
for kw in goodperforming_keywords:
    print(f"- {kw['keyword']}: Avg={kw['average_score']}, Slope={kw['slope']}")

# Plot trends
plt.figure(figsize=(12, 6))
for product in products_to_plot:
    plt.plot(trend_dict[product], label=product)

plt.legend()
plt.title("Google Trends Over Time")
plt.xlabel("Date")
plt.ylabel("Search Interest")
plt.grid(True)
plt.tight_layout()
plt.show()
