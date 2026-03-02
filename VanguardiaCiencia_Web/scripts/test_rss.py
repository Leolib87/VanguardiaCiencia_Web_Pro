import feedparser
import time
from datetime import datetime, timezone, timedelta

RSS_FEEDS = [
    "https://www.nature.com/nature.rss",
    "https://www.sciencedaily.com/rss/all.xml",
    "https://www.sciencenews.org/feed"
]

now = datetime.now(timezone.utc)
umbral = now - timedelta(hours=24)

print(f"--- HORA ACTUAL (UTC): {now} ---")
print(f"--- UMBRAL (24h atrás): {umbral} ---")

for url in RSS_FEEDS:
    print(f"\n📡 FEED: {url}")
    feed = feedparser.parse(url)
    for entry in feed.entries[:5]:
        pub_time = None
        # Intentar parsear fecha
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            pub_time = datetime.fromtimestamp(time.mktime(entry.published_parsed), timezone.utc)
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            pub_time = datetime.fromtimestamp(time.mktime(entry.updated_parsed), timezone.utc)
        
        status = "✅ DENTRO" if (pub_time and pub_time > umbral) else "❌ FUERA"
        print(f" - {status} | {entry.title[:60]}... | FECHA: {pub_time}")
