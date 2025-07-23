import pandas as pd
import matplotlib.pyplot as plt

# ✅ Load from CSV
df = pd.read_csv("trend_data.csv", parse_dates=["date"])
df.set_index("date", inplace=True)

# ✅ Rebuild dictionary
trend_dict = {col: df[col] for col in df.columns}

# ✅ Example: plot selected products
products_to_plot = ["kettlebell", "yoga mat"]

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

