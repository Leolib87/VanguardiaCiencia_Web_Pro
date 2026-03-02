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
    """Genera una imagen usando la API de Freepik AI."""
    url = "https://api.freepik.com/v1/ai/text-to-image"
    headers = {
        "x-freepik-api-key": FREEPIK_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "prompt": f"{prompt}, high resolution, scientific photography, cinematic lighting, 4k",
        "model": "mystic",
        "aspect_ratio": "widescreen_16_9",
        "num_images": 1
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            # La API suele devolver una URL temporal o el contenido en base64 según el flujo
            # Ajustamos según el formato real de respuesta (asumiendo data[0].url)
            image_url = result.get('data', [{}])[0].get('url')
            if image_url:
                img_data = requests.get(image_url).content
                image_name = f"{slug}-hero.jpg"
                with open(ASSETS_DIR / image_name, 'wb') as handler:
                    handler.write(img_data)
                return f"../../assets/{image_name}"
    except Exception as e:
        print(f"Error generando imagen: {e}")
    
    return "../../assets/blog-placeholder-1.jpg"

def create_scientific_post(title, description, content, category, image_prompt=None):
    """Crea un nuevo artículo en formato Astro con SEO y Estilo Pro."""
    slug = title.lower().replace(" ", "-").replace(":", "").replace("'", "").replace('"', "")[:50]
    filename = f"{slug}.md"
    filepath = CONTENT_DIR / filename
    
    # Generar o asignar imagen
    if image_prompt:
        hero_image = generate_image_freepik(image_prompt, slug)
    else:
        hero_image = "../../assets/blog-placeholder-1.jpg"

    # Plantilla del Artículo
    template = f"""---
title: "{title}"
description: "{description}"
category: "{category}"
pubDate: "{datetime.date.today().isoformat()}"
heroImage: "{hero_image}"
---

{content}

---
*Noticia generada por el Sistema de Automatización de Vanguardia Ciencia basada en fuentes primarias internacionales.*
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
