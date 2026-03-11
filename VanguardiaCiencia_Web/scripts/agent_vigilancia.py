import feedparser
import sys
import os
import asyncio
import json
import re
from pathlib import Path

# Importar lógica de publicación
sys.path.append(str(Path(__file__).parent))
from auto_publisher import create_scientific_post, push_to_github

# Configuración
RSS_FEEDS = [
    "https://www.nature.com/nature.rss",
    "https://www.sciencedaily.com/rss/all.xml",
    "https://www.sciencenews.org/feed"
]

LOG_FILE = Path(__file__).parent / "published_news.log"

SYSTEM_INSTRUCTION = (
    "Actúa como el Editor Jefe de Vanguardia Ciencia. Tu tarea es analizar el resumen de la noticia proporcionada "
    "y generar una noticia científica profesional en español. "
    "Debes devolver un JSON con exactamente estos campos: "
    "'title' (máximo 60 caracteres), 'category' (Salud, Tecnología, Espacio, Ambiente, Geofísica o IA Genómica), "
    "'description' (resumen SEO de 150 caracteres), 'content' (artículo completo en Markdown con subtítulos H3, "
    "bien estructurado y técnico), 'image_prompt' (un prompt en inglés detallado para generar una imagen realística "
    "sobre el tema en Freepik)."
)

def get_published_urls():
    if not LOG_FILE.exists(): return set()
    with open(LOG_FILE, "r") as f:
        return set(line.strip() for f in f if line.strip())

def log_published_url(url):
    with open(LOG_FILE, "a") as f:
        f.write(f"{url}
")

async def process_with_gemini(summary):
    try:
        command = f'gemini -y -p "{SYSTEM_INSTRUCTION} Noticia: {summary}"'
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        output = stdout.decode('utf-8', errors='ignore').strip()
        json_match = re.search(r'\{.*\}', output, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except:
        return None

async def run_agent():
    print("🕵️ Agente de Vigilancia iniciando...")
    published = get_published_urls()
    
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:3]: # Revisar las 3 más nuevas de cada feed
            if entry.link not in published:
                print(f"🆕 Nueva noticia encontrada: {entry.title}")
                
                # Procesar
                data = await process_with_gemini(f"Título: {entry.title}. Resumen: {entry.summary}")
                
                if data:
                    print(f"✍️ Generando artículo: {data['title']}")
                    create_scientific_post(
                        data['title'], 
                        data['description'], 
                        data['content'], 
                        data['category'], 
                        data.get('image_prompt')
                    )
                    log_published_url(entry.link)
                    push_to_github()
                    print("🚀 Publicado con éxito.")
                    return # Publicar solo una por ejecución para no saturar
    
    print("📭 No hay noticias nuevas por ahora.")

if __name__ == "__main__":
    asyncio.run(run_agent())
