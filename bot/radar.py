import feedparser
import json
import os
import re
import datetime
import time
from pathlib import Path

# Configuración de múltiples fuentes
RSS_FEEDS = [
    "https://www.nature.com/nature.rss",
    "https://www.sciencenews.org/feed",
    "https://www.sciencedaily.com/rss/all.xml",
    "https://www.sciencedaily.com/rss/most_popular.xml",
    "https://www.sciencedaily.com/rss/top/technology.xml"
]
BANDEJA_DIR = Path("C:/Users/leoli/OneDrive/Desktop/VanguardiaCiencia_Web/bot/bandeja_de_entrada")

def clean_filename(text):
    """Convierte un título en un nombre de archivo seguro."""
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[-\s]+', '_', text)[:100]

def get_source_info(url):
    """Retorna el nombre y emoji según la URL del feed."""
    if "nature.com" in url: return "Nature", "🧬"
    if "sciencenews.org" in url: return "ScienceNews", "🗞️"
    if "rss/all.xml" in url: return "ScienceDaily General", "🌐"
    if "most_popular.xml" in url: return "ScienceDaily Popular", "🔥"
    if "technology.xml" in url: return "ScienceDaily Technology", "🤖"
    return "Fuente Externa", "📡"

def ejecutar_radar():
    print(f"📡 Radar v4.0 (Master Mix): Escaneando y mezclando fuentes...")
    
    if not BANDEJA_DIR.exists(): BANDEJA_DIR.mkdir(parents=True)
    
    todas_las_entradas = []

    # 1. Recolectar de todas las fuentes
    for rss_url in RSS_FEEDS:
        source_name, emoji = get_source_info(rss_url)
        print(f"🔍 {emoji} Escaneando {source_name}...")
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries[:15]:
            # Normalizar fecha para ordenación
            # Intentamos obtener la fecha de varias formas comunes en RSS
            fecha_timestamp = 0
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                fecha_timestamp = time.mktime(entry.published_parsed)
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                fecha_timestamp = time.mktime(entry.updated_parsed)
            
            todas_las_entradas.append({
                "entry": entry,
                "source_name": source_name,
                "emoji": emoji,
                "timestamp": fecha_timestamp
            })

    # 2. Mezclar y Ordenar por fecha (más reciente primero)
    todas_las_entradas.sort(key=lambda x: x['timestamp'], reverse=True)

    # 3. Guardar en la bandeja (Mix)
    count = 0
    for item in todas_las_entradas:
        entry = item['entry']
        filename = f"{clean_filename(entry.title)}.json"
        filepath = BANDEJA_DIR / filename
        
        if not filepath.exists():
            data = {
                "title": entry.title,
                "link": entry.link,
                "summary": entry.summary if hasattr(entry, 'summary') else "",
                "source": f"{item['emoji']} {item['source_name']}",
                "published_at": time.ctime(item['timestamp']),
                "processed": False
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            count += 1
            print(f"   ✨ [{item['emoji']}] {entry.title[:60]}...")
            
            # Límite global de noticias nuevas para no saturar la bandeja
            if count >= 30: break
    
    print(f"\n🏁 Radar Mix finalizado. {count} noticias frescas de diversas fuentes añadidas.")

if __name__ == "__main__":
    ejecutar_radar()
