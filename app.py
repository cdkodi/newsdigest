import os
import feedparser
import requests
from google import genai
from google.genai import types

RSS_FEEDS = {
    "TOI_TopNews": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "IndianExpress": "https://indianexpress.com/section/india/feed/",
    "NDTV_Trending": "https://vshred.ndtv.com/trending.xml",
    "TheHindu_National": "https://www.thehindu.com/news/national/?service=rss",
    "Gadgets360_Tech": "https://feeds.feedburner.com/gadgets360-latest",
    "YourStory_Startups": "https://yourstory.com/feed",
    "MoneyControl_Latest": "https://www.moneycontrol.com/rss/latestnews.xml",
    "LiveMint_Companies": "https://www.livemint.com/rss/companies"
}

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
NOTION_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DB_ID = os.environ.get("NOTION_DATABASE_ID")

HISTORY_FILE = "processed_links.txt"

def load_processed_links():
    """Reads previously crawled items to save API call costs."""
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r") as f:
        return set(line.strip() for line in f)

def save_processed_link(link):
    """Appends a processed URL to local runtime storage."""
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{link}\n")

def push_to_notion(headline, source_url, hook, script_body):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    payload = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Headline": {"title": [{"text": {"content": headline}}]},
            "Source Link": {"url": source_url},
            "Suggested Hook": {"rich_text": [{"text": {"content": hook}}]},
            "AI Script": {"rich_text": [{"text": {"content": script_body}}]},
            "Status": {"select": {"name": "Draft"}}
        }
    }
    res = requests.post(url, json=payload, headers=headers)
    if res.status_code == 200:
        print(f"📌 Successfully pushed draft to Notion: {headline[:40]}...")
    else:
        print(f"❌ Notion write error ({res.status_code}): {res.text}")

def generate_video_assets(title, summary):
    client = genai.Client(api_key=GEMINI_KEY)
    prompt = f"""
    You are an expert short-form video producer for an Indian audience.
    Analyze this breaking news item and determine if it makes a viral 40-second vertical video (Shorts/Reels).
    
    Headline: {title}
    Context: {summary}
    
    Target Audience: Indian Gen-Z/Millennials (18-30). Pacing must be intense and hook-heavy.
    
    Provide your output strictly in JSON format matching this schema. No markdown wrappers.
    {{
        "is_viral_material": true or false,
        "on_screen_hook": "A short, highly gripping text overlay under 7 words to freeze the scroll",
        "full_script": "A narrative voiceover text broken up with minimal pacing bracket tags e.g. [0:00 - 0:05] voice text..."
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
    print("📡 Initializing remote scans on expanded Indian RSS network...")
    processed_links = load_processed_links()
    
    # Restrict trigger keywords to keep context punchy
    triggers = ["breaking", "just in", "arrested", "scam", "wins", "bizarre", "viral", "clash", "cancels", "retrenched", "protest", "launched", "shocking"]
    
    for source, feed_url in RSS_FEEDS.items():
        feed = feedparser.parse(feed_url)
        if not feed.entries:
            continue
            
        # Scan only the top 3 items per feed to guarantee lightning-fast executions
        for item in feed.entries[:3]:
            link = item.link
            
            # Skip if we already parsed this link in a prior execution window
            if link in processed_links:
                continue
                
            title = item.title
            summary = item.get("summary", "")
            
            if any(word in title.lower() or word in summary.lower() for word in triggers):
                print(f"🔥 New urgent story caught [{source}]: {title}")
                
                analysis = generate_video_assets(title, summary)
                if analysis and analysis.get("is_viral_material"):
                    push_to_notion(
                        headline=title,
                        source_url=link,
                        hook=analysis.get("on_screen_hook"),
                        script_body=analysis.get("full_script")
                    )
            
            # Add to memory tracking immediately
            save_processed_link(link)

if __name__ == "__main__":
    process_newsroom()
