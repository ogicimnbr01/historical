import wikipediaapi  # pyre-ignore[21]
import requests  # pyre-ignore[21]

# User-Agent for Wikipedia API (Policy requirement)
USER_AGENT = 'HistoryShortsBot/1.0 (AWS Lambda)'

def search_wikipedia(query, lang='en'):
    """
    Uses Wikipedia Search API to find the closest matching title.
    FILTERS OUT POP CULTURE (movies, games) to ensure historical accuracy.
    """
    # Refine query: Add 'history' and exclude common pop culture terms
    # Aggressively filter out TV series, documentaries, films, games
    refined_query = f"{query} history -intitle:film -intitle:movie -intitle:game -intitle:series -intitle:documentary"
    
    search_url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": refined_query,
        "format": "json",
        "srlimit": 1  # We only want the best match
    }
    
    try:
        # Custom headers
        headers = {'User-Agent': USER_AGENT}
        response = requests.get(search_url, params=params, headers=headers, timeout=5)
        data = response.json()
        
        if "query" in data and "search" in data["query"]:
            results = data["query"]["search"]
            if results:
                best_match = results[0]["title"]
                print(f"🔍 Smart Search Found: '{query}' -> '{best_match}'")
                return best_match
    except Exception as e:
        print(f"⚠️ Search API Error: {e}")
    
    return None

def get_wiki_summary(topic, lang='en'):
    """
    AWS Lambda friendly Wikipedia summary fetcher.
    Tries direct page first, falls back to Smart Search if not found.
    """
    # 1. Initialize API
    wiki_wiki = wikipediaapi.Wikipedia(
        user_agent=USER_AGENT,
        language=lang,
        extract_format=wikipediaapi.ExtractFormat.WIKI
    )

    try:
        # 2. Try Direct Page Access
        page = wiki_wiki.page(topic)

        if page.exists():
            print(f"✅ Direct Page Found: '{topic}'")
            return page.text[:2500]
        
        # 3. Fallback: Smart Search
        print(f"⚠️ Direct page '{topic}' not found. Attempting Smart Search...")
        best_match_title = search_wikipedia(topic, lang)
        
        if best_match_title:
            # Try fetching the discovered page
            page = wiki_wiki.page(best_match_title)
            if page.exists():
                print(f"✅ Smart Search Success: Using page '{best_match_title}' for topic '{topic}'")
                return page.text[:2500]

        print(f"❌ Research Failed: No data found for '{topic}'")
        return None

    except Exception as e:
        print(f"⚠️ Wikipedia API error: {e}")
        return None

