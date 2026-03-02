import os
import sys
import re
import requests
import base64
from pathlib import Path

# Configuración de Rutas
BASE_DIR = Path("C:/Users/leoli/OneDrive/Desktop/VanguardiaCiencia_Web")
CONTENT_DIR = BASE_DIR / "src/content/blog"
ASSETS_DIR = BASE_DIR / "src/assets"
FREEPIK_API_KEY = "FPSX79febb37aab9f7f29665f757e51f19f7"

def generate_image_freepik(prompt, slug):
    """Genera una imagen usando la API de Freepik AI (soporta URL y Base64)."""
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
        print(f"📡 Solicitando imagen a Freepik para: {slug}")
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            image_data_obj = result.get('data', [{}])[0]
            image_url = image_data_obj.get('url')
            image_b64 = image_data_obj.get('base64')
            
            image_name = f"{slug}-hero.jpg"
            save_path = ASSETS_DIR / image_name
            
            if image_url:
                print(f"📥 Descargando imagen desde URL...")
                img_data = requests.get(image_url).content
                with open(save_path, 'wb') as handler:
                    handler.write(img_data)
                print(f"✅ Imagen guardada: {image_name}")
                return f"../../assets/{image_name}"
            elif image_b64:
                print(f"📦 Guardando imagen desde Base64...")
                with open(save_path, 'wb') as handler:
                    handler.write(base64.b64decode(image_b64))
                print(f"✅ Imagen guardada: {image_name}")
                return f"../../assets/{image_name}"
            else:
                print(f"⚠️ No se encontró datos de imagen en la respuesta.")
        else:
            print(f"❌ Error API Freepik: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"💥 Excepción: {e}")
    
    return None

def update_legacy_posts():
    print("🚀 Iniciando actualización masiva de imágenes con Freepik...")
    
    if not ASSETS_DIR.exists():
        ASSETS_DIR.mkdir(parents=True)

    for md_file in CONTENT_DIR.glob("*.md"):
        print(f"\n📄 Procesando: {md_file.name}")
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        title_match = re.search(r'title:\s*["\']?(.+?)["\']?\s*$', content, re.MULTILINE)
        if not title_match: continue
            
        title = title_match.group(1).strip().strip('"').strip("'")
        slug = md_file.stem
        
        print(f"🎨 Título: {title}")
        new_hero_path = generate_image_freepik(title, slug)
        
        if new_hero_path:
            # Reemplazar la línea de heroImage
            new_content = re.sub(r'heroImage:.*', f'heroImage: "{new_hero_path}"', content)
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"✨ {md_file.name} actualizado.")
        else:
            print(f"⏭️ Fallo en {md_file.name}.")

if __name__ == "__main__":
    update_legacy_posts()
