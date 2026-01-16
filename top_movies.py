import requests
import pandas as pd
import time

API_KEY = '9dec759ff4029bcf72fa0f1491183561'
BASE_URL = "https://api.themoviedb.org/3"

def get_director(movie_id):
    """Fetches the director's name for a specific movie ID."""
    url = f"{BASE_URL}/movie/{movie_id}/credits?api_key={API_KEY}"
    response = requests.get(url).json()
    if 'crew' in response:
        for member in response['crew']:
            if member['job'] == 'Director':
                return member['name']
    return "Unknown"

movie_data = []
print("Starting data fetch (Top 1000 movies)...")

# TMDB returns 20 movies per page. Page 1-50 gives us the Top 1000.
for page in range(1, 51):
    print(f"Fetching page {page} of 50...")
    list_url = f"{BASE_URL}/movie/top_rated?api_key={API_KEY}&page={page}"
    results = requests.get(list_url).json().get('results', [])

    for movie in results:
        m_id = movie['id']
        director = get_director(m_id)
        
        movie_data.append({
            'Rank': len(movie_data) + 1,
            'Title': movie['title'],
            'Director': director,
            'Rating': movie['vote_average'],
            'Release Date': movie['release_date'],
            'Vote Count': movie['vote_count']
        })
        
        # Small sleep to respect TMDB rate limits (approx 40 req/10 sec)
        time.sleep(0.05) 

# Create DataFrame and Export
df = pd.DataFrame(movie_data)
df.to_excel("TMDB_Top_1000_Movies.xlsx", index=False)

print("Success! File saved as 'TMDB_Top_1000_Movies.xlsx'")