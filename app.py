import os
import feedparser
import requests
from google import genai
from google.genai import types

# Clean Target RSS channels for Indian breaking content
RSS_FEEDS = {
    "TOI_TopNews": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "IndianExpress": "https://indianexpress.com/section/india/feed/"
}

# ZERO HARDCODED IDS: These functions look inside the runner system at runtime.
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
NOTION_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DB_ID = os.environ.get("NOTION_DATABASE_ID")

def push_to_notion(headline, source_url, hook, script_body):
    """Inserts a structured news asset row natively into the Notion board schema."""
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Headline": {
                "title": [{"text": {"content": headline}}]
            },
            "Source Link": {
                "url": source_url
            },
            "Suggested Hook": {
                "rich_text": [{"text": {"content": hook}}]
            },
            "AI Script": {
                "rich_text": [{"text": {"content": script_body}}]
            },
            "Status": {
                "select": {"name": "Draft"}
            }
        }
    }
    
    res = requests.post(url, json=payload, headers=headers)
    if res.status_code == 200:
        print(f"📌 Successfully pushed draft to Notion: {headline[:40]}...")
    else:
        print(f"❌ Notion write error ({res.status_code}): {res.text}")

def generate_video_assets(title, summary):
    """Prompts Gemini to structure the news item into a 40-second vertical video format."""
    client = genai.Client(api_key=GEMINI_KEY)
    
    prompt = f"""
    You are an expert short-form video producer for an Indian audience.
    Analyze this breaking news item and output a 40-second vertical video script (YouTube Shorts/Instagram Reels).
    
    Headline: {title}
    Context: {summary}
    
    Target Audience: Indian Gen-Z/Millennials (18-30). Pacing must be intense and hook-heavy.
    
    Provide your output strictly in JSON format matching this schema. Do not include markdown wrappers like ```json.
    {{
        "is_viral_material": true or false,
        "on_screen_hook": "A short, highly gripping text overlay under 7 words to freeze the scroll",
        "full_script": "A narrative voiceover text broken up with minimal pacing bracket tags e.g. [0:00 - 0:05] voice text... [0:05 - 0:20] next text..."
    }}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        import json
        return json.loads(response.text)
    except Exception as e:
        print(f"⚠️ Brain module processing fault: {e}")
        return None

def process_newsroom():
    print("📡 Initializing remote scans on active Indian RSS feeds...")
    
    # Simple deduplication set for this run execution to prevent duplicate pushes
    seen_urls = set()
    
    for source, feed_url in RSS_FEEDS.items():
        feed = feedparser.parse(feed_url)
        
        # Guard against empty or malformed feed responses
        if not feed.entries:
            print(f"⚠️ No entries found for source: {source}")
            continue
            
        # Scrape only the 5 most recent articles per check
        for item in feed.entries[:5]:
            title = item.title
            link = item.link
            summary = item.get("summary", "")
            
            if link in seen_urls:
                continue
            seen_urls.add(link)
            
            # Filter headlines for high-momentum indicators
            triggers = ["breaking", "just in", "arrested", "scam", "wins", "bizarre", "viral", "clash", "cancels", "retrenched", "protest"]
            if any(word in title.lower() or word in summary.lower() for word in triggers):
                print(f"🔥 Flagged urgent candidate item: {title}")
                
                # Request analysis from Gemini
                analysis = generate_video_assets(title, summary)
                if analysis and analysis.get("is_viral_material"):
                    push_to_notion(
                        headline=title,
                        source_url=link,
                        hook=analysis.get("on_screen_hook"),
                        script_body=analysis.get("full_script")
                    )

if __name__ == "__main__":
    process_newsroom()
