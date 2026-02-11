import wikipediaapi

def get_wiki_summary(topic, lang='en'):
    """
    AWS Lambda friendly Wikipedia summary fetcher.
    Must define User-Agent (Wikipedia policy).
    """
    # Custom User-Agent to avoid blocking
    wiki_wiki = wikipediaapi.Wikipedia(
        user_agent='HistoryShortsBot/1.0 (AWS Lambda)',
        language=lang,
        extract_format=wikipediaapi.ExtractFormat.WIKI
    )

    try:
        page = wiki_wiki.page(topic)

        if page.exists():
            # Take first 2000 chars (Summary + Intro) to save tokens
            print(f"✅ Wikipedia found for '{topic}'")
            return page.text[:2000]
        else:
            print(f"⚠️ Wikipedia page not found for '{topic}'")
            return None
    except Exception as e:
        print(f"⚠️ Wikipedia API error: {e}")
        return None
