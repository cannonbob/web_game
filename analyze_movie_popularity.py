import json
from collections import defaultdict

JSON_FILE = 'C:/Users/Kai/Downloads/movie_ids_12_29_2025.json/movie_ids_12_29_2025.json'

# Count movies by popularity ranges
total_movies = 0
movies_above_7 = 0
popularity_buckets = defaultdict(int)

print("Analyzing movie popularity distribution...")
print("-" * 60)

with open(JSON_FILE, mode='r', encoding='utf-8') as f:
    for line in f:
        try:
            movie_data = json.loads(line.strip())
            popularity = movie_data.get('popularity', 0)
            total_movies += 1

            if popularity > 7:
                movies_above_7 += 1

                # Create buckets in 0.2 steps starting from 7.0
                bucket = int((popularity - 7.0) / 0.2) * 0.2 + 7.0
                bucket_key = f"{bucket:.1f}-{bucket+0.2:.1f}"
                popularity_buckets[bucket_key] += 1

        except json.JSONDecodeError:
            continue

print(f"Total movies in file: {total_movies:,}")
print(f"Movies with popularity > 7: {movies_above_7:,}")
print(f"Percentage: {(movies_above_7/total_movies*100):.2f}%")
print("\n" + "=" * 60)
print("Distribution for movies with popularity > 7 (in 0.2 steps):")
print("=" * 60)

# Sort by bucket range and display
sorted_buckets = sorted(popularity_buckets.items(),
                       key=lambda x: float(x[0].split('-')[0]))

for bucket_range, count in sorted_buckets:
    bar = '#' * min(int(count / 10), 50)  # Visual bar
    print(f"{bucket_range:>12}: {count:6,} {bar}")

print("=" * 60)
