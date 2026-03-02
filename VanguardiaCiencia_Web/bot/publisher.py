import os
import sys
import asyncio
import logging
import json
import re
import feedparser
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, filters
from pathlib import Path

# Importar lógica de publicación
sys.path.append(str(Path(__file__).parent.parent / "scripts"))
from auto_publisher import create_scientific_post, push_to_github

# Configuración
TOKEN = "8530303251:AAFqw7fYLFPWNRC-x1HySlnPI1PpnIFKio8"
ALLOWED_USER_ID = 7463161678
RSS_FEEDS = [
    "https://www.nature.com/nature.rss",
    "https://www.sciencedaily.com/rss/all.xml",
    "https://www.sciencenews.org/feed"
]
LOG_FILE = Path(__file__).parent.parent / "scripts" / "published_news.log"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SYSTEM_INSTRUCTION = (
    "Actúa como el Editor Jefe de Vanguardia Ciencia. Tu tarea es analizar el contenido de la URL o resumen proporcionado "
    "y generar una noticia científica profesional en español. "
    "Debes devolver un JSON con exactamente estos campos: "
    "'title' (máximo 60 caracteres), 'category' (Salud, Tecnología, Espacio, Ambiente, Geofísica o IA Genómica), "
    "'description' (resumen SEO de 150 caracteres), 'content' (artículo completo en Markdown con subtítulos H3, "
    "bien estructurado y técnico), 'image_prompt' (un prompt en inglés detallado para generar una imagen realística "
    "sobre el tema en Freepik)."
)

pending_posts = {}

def get_published_urls():
    if not LOG_FILE.exists(): return set()
    with open(LOG_FILE, "r") as f:
        return set(line.strip() for f in f if line.strip())

def log_published_url(url):
    with open(LOG_FILE, "a") as f:
        f.write(f"{url}\n")

async def process_with_gemini(input_data):
    """Llama a Gemini CLI para procesar el link o resumen."""
    try:
        command = f'gemini -y -p "{SYSTEM_INSTRUCTION} Datos: {input_data}"'
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
        return None
    except Exception as e:
        logging.error(f"Error con Gemini: {e}")
        return None

async def send_preview(context, chat_id, post_data, source_url=None):
    """Envía la vista previa con botones al usuario."""
    post_id = str(hash(post_data['title']))
    pending_posts[post_id] = {'data': post_data, 'url': source_url}
    
    preview = (
        f"🔍 **SUGERENCIA DE VANGUARDIA IA**\n\n"
        f"📌 **Título:** {post_data.get('title')}\n"
        f"🗂️ **Categoría:** {post_data.get('category')}\n"
        f"📝 **Descripción:** {post_data.get('description')}\n\n"
        f"¿Deseas publicar esta noticia en la web?"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Publicar", callback_query_data=f"pub_{post_id}"),
            InlineKeyboardButton("🗑️ Descartar", callback_query_data=f"del_{post_id}")
        ]
    ]
    await context.bot.send_message(chat_id=chat_id, text=preview, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID: return
    url = update.message.text
    if not url.startswith("http"): return

    msg = await update.message.reply_text("🔬 Analizando link...")
    post_data = await process_with_gemini(f"URL: {url}")
    if post_data:
        await msg.delete()
        await send_preview(context, update.effective_chat.id, post_data, url)
    else:
        await msg.edit_text("❌ Error al procesar el link.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action, post_id = query.data.split('_')
    
    if post_id not in pending_posts:
        await query.edit_message_text("Sesión expirada o noticia ya procesada.")
        return

    if action == "pub":
        item = pending_posts[post_id]
        await query.edit_message_text("🚀 Publicando...")
        try:
            create_scientific_post(item['data']['title'], item['data']['description'], item['data']['content'], item['data']['category'], item['data'].get('image_prompt'))
            if item['url']: log_published_url(item['url'])
            push_to_github()
            await query.edit_message_text(f"✨ **¡PUBLICADO!**\n'{item['data']['title']}' ya está en la web.")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")
    else:
        await query.edit_message_text("🗑️ Noticia descartada.")
    
    del pending_posts[post_id]

async def surveillance_task(context: ContextTypes.DEFAULT_TYPE):
    """Tarea que revisa RSS cada 4 horas."""
    print("🕵️ Ejecutando ronda de vigilancia...")
    published = get_published_urls()
    
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:2]:
            if entry.link not in published:
                print(f"💡 Nueva sugerencia: {entry.title}")
                data = await process_with_gemini(f"RSS Entry - Título: {entry.title}. Resumen: {entry.summary}")
                if data:
                    await send_preview(context, ALLOWED_USER_ID, data, entry.link)
                    # Solo sugerir una por feed para no saturar a Leandro
                    break

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Manejadores
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Programar vigilancia cada 4 horas (14400 segundos)
    job_queue = application.job_queue
    job_queue.run_repeating(surveillance_task, interval=14400, first=10)
    
    print("🤖 Bot Vanguardia Editor Activo (Modo Supervisado)")
    application.run_polling()
