import json
import requests
import time
from app import app
from db import db
from models.game import Movie

# TMDB API Configuration
TMDB_API_KEY = '9dec759ff4029bcf72fa0f1491183561'  # Replace with your actual API key
TMDB_API_BASE_URL = 'https://api.themoviedb.org/3'

# Configuration
JSON_FILE = 'C:/Users/Kai/Downloads/movie_ids_12_29_2025.json/movie_ids_12_29_2025.json'
BATCH_SIZE = 100  # Insert movies in batches
REQUEST_DELAY = 0.25  # Delay between API requests (seconds) to avoid rate limits
SKIP_ADULT = False  # Skip adult movies
SKIP_VIDEO = False  # Skip video content (usually not theatrical releases)
MIN_POPULARITY = 5.0  # Minimum popularity score to include movie
MAX_POPULARITY = 7.0

def fetch_movie_details(movie_id):
    """Fetch movie details from TMDB API."""
    url = f"{TMDB_API_BASE_URL}/movie/{movie_id}"
    params = {'api_key': TMDB_API_KEY}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching movie {movie_id}: {e}")
        return None

def extract_year_from_date(date_string):
    """Extract year from YYYY-MM-DD format."""
    if not date_string:
        return 0
    try:
        return int(date_string[:4]) if len(date_string) >= 4 else 0
    except (ValueError, TypeError):
        return 0

def import_movies():
    """Import movies from JSON file and enrich with TMDB API data."""

    with app.app_context():
        try:
            movies_to_add = []
            total_processed = 0
            skipped_adult = 0
            skipped_video = 0
            skipped_popularity = 0
            api_errors = 0

            print(f"Reading movies from {JSON_FILE}...")
            print(f"Configuration: SKIP_ADULT={SKIP_ADULT}, SKIP_VIDEO={SKIP_VIDEO}, MIN_POPULARITY={MIN_POPULARITY} , MAX_POPULARITY={MAX_POPULARITY}")
            print(f"API request delay: {REQUEST_DELAY}s")
            print("-" * 60)

            with open(JSON_FILE, mode='r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        # Parse JSON line
                        movie_data = json.loads(line.strip())

                        # Skip adult movies if configured
                        if SKIP_ADULT and movie_data.get('adult', False):
                            skipped_adult += 1
                            continue

                        # Skip videos if configured
                        if SKIP_VIDEO and movie_data.get('video', False):
                            skipped_video += 1
                            continue

                        # Skip movies below minimum popularity
                        popularity = movie_data.get('popularity', 0)
                        if popularity < MIN_POPULARITY:
                            skipped_popularity += 1
                            continue

                        movie_id = movie_data.get('id')
                        title = movie_data.get('original_title')

                        if not movie_id or not title:
                            print(f"Line {line_num}: Missing id or title, skipping")
                            continue

                        # Fetch additional details from TMDB API
                        print(f"[{line_num}] Fetching details for: {title} (ID: {movie_id})")
                        details = fetch_movie_details(movie_id)

                        if details:
                            # Extract release year
                            release_date = details.get('release_date', '')
                            year = extract_year_from_date(release_date)

                            # Add movie to batch
                            movies_to_add.append(Movie(
                                title=title,
                                year=year
                            ))

                            total_processed += 1

                            # Insert in batches
                            if len(movies_to_add) >= BATCH_SIZE:
                                print(f"\nInserting batch of {len(movies_to_add)} movies...")
                                db.session.bulk_save_objects(movies_to_add)
                                db.session.commit()
                                movies_to_add = []
                                print(f"Batch inserted. Total processed: {total_processed}")
                                print("-" * 60)
                        else:
                            api_errors += 1

                        # Rate limiting delay
                        time.sleep(REQUEST_DELAY)

                    except json.JSONDecodeError as e:
                        print(f"Line {line_num}: Invalid JSON - {e}")
                        continue
                    except Exception as e:
                        print(f"Line {line_num}: Unexpected error - {e}")
                        continue

            # Insert remaining movies
            if movies_to_add:
                print(f"\nInserting final batch of {len(movies_to_add)} movies...")
                db.session.bulk_save_objects(movies_to_add)
                db.session.commit()

            print("\n" + "=" * 60)
            print("IMPORT COMPLETE!")
            print("=" * 60)
            print(f"Total movies imported: {total_processed}")
            print(f"Skipped (adult): {skipped_adult}")
            print(f"Skipped (video): {skipped_video}")
            print(f"Skipped (low popularity): {skipped_popularity}")
            print(f"API errors: {api_errors}")
            print("=" * 60)

        except FileNotFoundError:
            print(f"Error: File not found - {JSON_FILE}")
        except Exception as e:
            print(f"Error: {e}")
            db.session.rollback()

if __name__ == "__main__":
    if TMDB_API_KEY == 'YOUR_TMDB_API_KEY_HERE':
        print("ERROR: Please set your TMDB API key in the TMDB_API_KEY variable")
        print("You can get an API key from: https://www.themoviedb.org/settings/api")
    else:
        import_movies()
