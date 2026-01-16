import json

JSON_FILE = 'C:/Users/Kai/Downloads/movie_ids_12_29_2025.json/movie_ids_12_29_2025.json'

print("Finding popularity threshold for 10,000 movies...")
print("-" * 60)

# Collect all popularity values
popularities = []

with open(JSON_FILE, mode='r', encoding='utf-8') as f:
    for line in f:
        try:
            movie_data = json.loads(line.strip())
            popularity = movie_data.get('popularity', 0)
            popularities.append(popularity)
        except json.JSONDecodeError:
            continue

# Sort in descending order
popularities.sort(reverse=True)

print(f"Total movies: {len(popularities):,}")
print()

# Show counts at different thresholds
thresholds = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0]

print("Movies with popularity >= threshold:")
print("-" * 60)

for threshold in thresholds:
    count = sum(1 for p in popularities if p >= threshold)
    marker = " <-- CLOSEST TO 10K" if 8000 <= count <= 12000 else ""
    print(f"  >= {threshold:4.1f}: {count:7,} movies{marker}")

print()
print("=" * 60)
print("Finding exact threshold for ~10,000 movies...")
print("=" * 60)

# Binary search for exact 10,000 threshold
target = 10000
if len(popularities) >= target:
    threshold_value = popularities[target - 1]
    count_at_threshold = sum(1 for p in popularities if p >= threshold_value)

    print(f"Movie #10,000 has popularity: {threshold_value:.4f}")
    print(f"Movies with popularity >= {threshold_value:.4f}: {count_at_threshold:,}")

    # Show nearby values
    print()
    print("Nearby thresholds:")
    for offset in [-0.5, -0.3, -0.1, 0, 0.1, 0.3, 0.5]:
        test_threshold = threshold_value + offset
        count = sum(1 for p in popularities if p >= test_threshold)
        print(f"  >= {test_threshold:6.4f}: {count:7,} movies")
