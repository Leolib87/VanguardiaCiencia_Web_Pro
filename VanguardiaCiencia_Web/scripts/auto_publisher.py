import os
import requests
import datetime
import json
from pathlib import Path

# Configuración de Rutas
BASE_DIR = Path("C:/Users/leoli/OneDrive/Desktop/VanguardiaCiencia_Web")
CONTENT_DIR = BASE_DIR / "src/content/blog"
ASSETS_DIR = BASE_DIR / "src/assets"
FREEPIK_API_KEY = "FPSX79febb37aab9f7f29665f757e51f19f7"

def generate_image_freepik(prompt, slug):
    """Genera una imagen usando la API de Freepik AI (Optimizado)."""
    url = "https://api.freepik.com/v1/ai/text-to-image"
    headers = {
        "x-freepik-api-key": FREEPIK_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "prompt": f"{prompt}, high resolution, scientific photography, cinematic lighting, 4k",
        "aspect_ratio": "widescreen_16_9",
        "num_images": 1
    }
    
    try:
        print(f"📡 Solicitando imagen a Freepik: {slug}...")
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            image_data_obj = result.get('data', [{}])[0]
            image_url = image_data_obj.get('url')
            image_b64 = image_data_obj.get('base64')
            
            image_name = f"{slug}-hero.jpg"
            save_path = ASSETS_DIR / image_name
            
            if image_url:
                print(f"📥 Descargando imagen...")
                img_data = requests.get(image_url).content
                with open(save_path, 'wb') as handler:
                    handler.write(img_data)
                return f"../../assets/{image_name}"
            elif image_b64:
                print(f"📦 Guardando imagen Base64...")
                import base64
                with open(save_path, 'wb') as handler:
                    handler.write(base64.b64decode(image_b64))
                return f"../../assets/{image_name}"
            else:
                print("⚠️ Freepik no devolvió datos de imagen.")
        else:
            print(f"❌ Error API Freepik ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"💥 Error crítico en imagen: {e}")
    
    return "../../assets/blog-placeholder-1.jpg"

def create_scientific_post(title, description, content, category, image_prompt=None, source_url=None):
    """Crea un nuevo artículo en formato Astro con SEO y Estilo Pro."""
    slug = title.lower().replace(" ", "-").replace(":", "").replace("'", "").replace('"', "")[:50]
    filename = f"{slug}.md"
    filepath = CONTENT_DIR / filename
    
    # Determinar la fuente de forma elegante
    source_name = "Fuente Externa"
    if source_url:
        if "nature.com" in source_url: source_name = "Nature"
        elif "sciencedaily.com" in source_url: source_name = "ScienceDaily"
        elif "sciencenews.org" in source_url: source_name = "ScienceNews"
        elif "sciencemag.org" in source_url or "science.org" in source_url: source_name = "Science"

    # Generar o asignar imagen
    if image_prompt:
        hero_image = generate_image_freepik(image_prompt, slug)
    else:
        hero_image = "../../assets/blog-placeholder-1.jpg"

    # Plantilla del Artículo (Optimizado para Astro v4 y SEO)
    source_footer = f"\n---\n**Fuente:** [{source_name}]({source_url})" if source_url else ""
    
    template = f"""---
title: "{title}"
description: "{description}"
pubDate: "{datetime.date.today().isoformat()}"
category: "{category}"
heroImage: "{hero_image}"
author: "Vanguardia IA"
tags: ["Ciencia", "{category}", "Innovación"]
layout: "../../layouts/BlogPost.astro"
---

### Resumen Ejecutivo
{description}

---

{content}
{source_footer}
"""
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(template)
    
    print(f"✅ Artículo creado: {filename}")
    return filepath

def push_to_github():
    """Sincroniza los cambios con el repositorio."""
    os.chdir(BASE_DIR)
    os.system('git add .')
    os.system('git commit -m "Auto-publish: Nueva noticia científica"')
    os.system('git push origin main')
    print("🚀 Web actualizada en GitHub!")

if __name__ == "__main__":
    pass
