import os
import re
from pathlib import Path

blog_dir = Path("C:/Users/leoli/OneDrive/Desktop/VanguardiaCiencia_Web/src/content/blog")

mapping = {
    "001": "Salud y Medicina",
    "003": "Medio Ambiente",
    "30-": "Biología y Genómica",
    "agentes": "Inteligencia Artificial",
    "descubrimiento": "Física y Química",
    "el-caballo": "Biología y Genómica",
    "el-escudo": "Salud y Medicina",
    "hito": "Salud y Medicina",
    "ia-generativa": "Inteligencia Artificial",
    "interruptor": "Salud y Medicina",
    "luna": "Tecnología y Espacio",
    "metano": "Medio Ambiente",
    "ribosoma": "Biología y Genómica"
}

for f in blog_dir.glob("*.md"):
    content = f.read_text(encoding='utf-8')
    updated = False
    
    for key, cat in mapping.items():
        if key in f.name:
            content = re.sub(r'category:.*', f'category: "{cat}"', content)
            content = re.sub(r'author:.*', 'author: "Vanguardia IA"', content)
            content = re.sub(r'tags:.*', f'tags: ["Ciencia", "{cat}", "Innovación"]', content)
            updated = True
            break
    
    if updated:
        f.write_text(content, encoding='utf-8')
        print(f"✅ Normalizado: {f.name}")
