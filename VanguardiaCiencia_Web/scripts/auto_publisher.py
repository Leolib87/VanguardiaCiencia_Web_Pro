import os
import requests
import datetime
import json
import re
from pathlib import Path

# Configuración de Rutas
BASE_DIR = Path("C:/Users/leoli/OneDrive/Desktop/VanguardiaCiencia_Web")
CONTENT_DIR = BASE_DIR / "src/content/blog"
ASSETS_DIR = BASE_DIR / "src/assets"
FREEPIK_API_KEY = "FPSX79febb37aab9f7f29665f757e51f19f7"

def generate_image_freepik(prompt, slug):
    """Genera una imagen usando la API de Freepik AI (Soporte Base64 Confirmado)."""
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
        # Asegurar que la carpeta assets existe
        if not ASSETS_DIR.exists(): ASSETS_DIR.mkdir(parents=True)
        
        print(f"📡 Solicitando imagen a Freepik para: {slug}...")
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            image_data_obj = result.get('data', [{}])[0]
            
            image_name = f"{slug}-hero.jpg"
            save_path = ASSETS_DIR / image_name
            
            # Prioridad 1: Base64 (Confirmado en test manual)
            if 'base64' in image_data_obj:
                import base64
                print(f"📦 Guardando imagen desde Base64...")
                with open(save_path, 'wb') as handler:
                    handler.write(base64.b64decode(image_data_obj['base64']))
                return f"../../assets/{image_name}"
            
            # Prioridad 2: URL
            elif 'url' in image_data_obj:
                print(f"📥 Descargando imagen desde URL...")
                img_data = requests.get(image_data_obj['url']).content
                with open(save_path, 'wb') as handler:
                    handler.write(img_data)
                return f"../../assets/{image_name}"
            
            else:
                print("⚠️ Freepik no devolvió imagen válida.")
        else:
            print(f"❌ Error API Freepik ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"💥 Error crítico en imagen: {e}")
    
    return "../../assets/blog-placeholder-1.jpg"

def create_scientific_post(title, description, content, category, image_prompt=None, source_url=None):
    """Crea un nuevo artículo en formato Astro con SEO y Estilo Pro."""
    # Sanitización robusta para Windows: solo letras, números y guiones
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug) # Quitar todo lo que no sea letra, número o espacio
    slug = re.sub(r'[\s]+', '-', slug).strip('-') # Cambiar espacios por guiones
    slug = slug[:60] # Limitar longitud
    
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
