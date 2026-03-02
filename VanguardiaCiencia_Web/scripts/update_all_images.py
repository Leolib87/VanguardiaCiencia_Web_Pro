import os
import sys
import re
from pathlib import Path

# Importar lógica de publicación existente
sys.path.append(str(Path(__file__).parent))
from auto_publisher import generate_image_freepik

BASE_DIR = Path("C:/Users/leoli/OneDrive/Desktop/VanguardiaCiencia_Web")
CONTENT_DIR = BASE_DIR / "src/content/blog"

def update_legacy_posts():
    print("🚀 Iniciando actualización masiva de imágenes con Freepik...")
    
    for md_file in CONTENT_DIR.glob("*.md"):
        print(f"📄 Procesando: {md_file.name}")
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extraer título (mejorando el regex)
        title_match = re.search(r'title: ["\'](.+?)["\']', content)
        if not title_match: 
            print(f"⚠️ No se encontró título en {md_file.name}")
            continue
            
        title = title_match.group(1)
        slug = md_file.stem
        
        print(f"🎨 Generando imagen para: {title}")
        prompt = f"Futuristic science illustration about {title}, cinematic lighting, photorealistic, 4k"
        new_hero = generate_image_freepik(prompt, slug)
        
        # Actualizar heroImage
        new_content = re.sub(r'heroImage: .*', f'heroImage: "{new_hero}"', content)
        
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"✅ {md_file.name} actualizado.")

if __name__ == "__main__":
    update_legacy_posts()
