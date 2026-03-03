import os
import sys
import asyncio
import logging
import json
import re
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, CommandHandler, filters
from pathlib import Path

# --- COMPATIBILIDAD WINDOWS ---
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configuración
TOKEN = "8530303251:AAFqw7fYLFPWNRC-x1HySlnPI1PpnIFKio8"
ALLOWED_USER_ID = 7463161678
BASE_DIR = Path("C:/Users/leoli/OneDrive/Desktop/VanguardiaCiencia_Web/bot")
BANDEJA_DIR = BASE_DIR / "bandeja_de_entrada"
SCRIPTS_DIR = BASE_DIR.parent / "scripts"

sys.path.append(str(SCRIPTS_DIR))
try:
    from auto_publisher import create_scientific_post, push_to_github
except ImportError:
    logging.error("No se pudo importar auto_publisher.py")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
file_map = {}

async def process_with_gemini(url):
    """Procesamiento asíncrono con navegación profunda."""
    instruction = (
        "Actúa como el Editor Jefe de Vanguardia Ciencia. ES OBLIGATORIO que navegues a la URL proporcionada "
        "y leas el artículo completo. Si el link falla, busca la noticia en Google para obtener los datos técnicos. "
        "Genera un JSON profesional en español: {'title', 'category', 'description', 'content', 'image_prompt'}."
    )
    try:
        command = f'gemini -y -p "{instruction} URL: {url}" -o stream-json'
        process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        
        full_response = ""
        try:
            while True:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=480)
                if not line: break
                try:
                    line_decoded = line.decode('utf-8', errors='ignore').strip()
                    if not (line_decoded.startswith('{') and line_decoded.endswith('}')): continue
                    data = json.loads(line_decoded)
                    if data.get('type') == 'message' and data.get('role') == 'assistant':
                        chunk = data.get('content', '')
                        if chunk: full_response += chunk
                except: continue
        except asyncio.TimeoutError:
            if process:
                try: process.kill()
                except: pass
            return None
        
        await process.wait()
        content = ANSI_ESCAPE.sub('', full_response).strip()
        content = re.sub(r'```json\s*|```\s*', '', content).strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        return json.loads(json_match.group(0)) if json_match else None
    except: return None

async def task_analysis(context, chat_id, url, ref_id, filename):
    """Tarea en segundo plano para procesar la noticia (Bandeja o Link Directo)."""
    result = await process_with_gemini(url)
    if result:
        post_key = f"post_{ref_id}"
        context.bot_data[post_key] = {'data': result, 'url': url, 'file': str(BANDEJA_DIR / filename)}
        
        preview = (
            f"✅ **ANÁLISIS COMPLETADO**\n\n"
            f"📌 **{result.get('title', 'Sin título')}**\n\n"
            f"{result.get('content', 'Sin contenido')[:600]}...\n\n"
            f"¿Publicar en Vanguardia Ciencia?"
        )
        btns = [[InlineKeyboardButton("✅ PUBLICAR", callback_data=f"pubfinal_{ref_id}"),
                 InlineKeyboardButton("🗑️ BORRAR", callback_data=f"del_{ref_id}")]]
        await context.bot.send_message(chat_id=chat_id, text=preview, reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ El análisis de la noticia {ref_id} falló. Intenta con otro link.")

async def bandeja(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID: return
    files = sorted(list(BANDEJA_DIR.glob("*.json")), key=os.path.getmtime, reverse=True)
    if not files:
        await update.message.reply_text("📭 Bandeja vacía. Usa /radar.")
        return

    text = f"📂 **BANDEJA EDITORIAL ({len(files)} pendientes):**\n\n"
    keyboard = []
    row = []
    file_map.clear()

    for i, f_path in enumerate(files[:15]):
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            idx = str(i + 1)
            file_map[idx] = f_path.name
            text += f"{idx}. 📰 {data.get('title', 'Sin título')[:65]}...\n\n"
            row.append(InlineKeyboardButton(idx, callback_data=f"p_{idx}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        except: continue

    if row: keyboard.append(row)
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesador universal de mensajes y links."""
    if update.effective_user.id != ALLOWED_USER_ID: return
    text = update.message.text.strip()
    
    if text.startswith("http"):
        url = text
        ref_id = str(hash(url))[-5:] # ID corto único
        
        await update.message.reply_text(
            f"📡 **¡Link directo detectado!**\n\nHe iniciado el análisis profundo. Como es un link externo, "
            f"Gemini navegará por todo el artículo para redactar la noticia.\n\n"
            f"Te avisaré en cuanto esté lista (3-5 min)."
        )
        # Usamos un nombre de archivo ficticio para links directos
        asyncio.create_task(task_analysis(context, update.effective_chat.id, url, ref_id, f"direct_{ref_id}.json"))
    else:
        await update.message.reply_text("👋 Hola Leandro. Envíame un link directo o usa /bandeja.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split('_')
    action = data_parts[0]
    ref_id = data_parts[1] if len(data_parts) > 1 else ""

    if action == "p": # Selección desde bandeja
        filename = file_map.get(ref_id)
        if not filename:
            await query.edit_message_text("❌ Referencia expirada.")
            return
        f_path = BANDEJA_DIR / filename
        with open(f_path, "r", encoding="utf-8") as f: news_data = json.load(f)
        await query.edit_message_text(f"⏳ Análisis asíncrono iniciado para la noticia {ref_id}. Te avisaré en unos minutos.")
        asyncio.create_task(task_analysis(context, update.effective_chat.id, news_data['link'], ref_id, filename))

    elif action == "pubfinal":
        item = context.bot_data.get(f"post_{ref_id}")
        if not item:
            await query.edit_message_text("❌ Datos perdidos.")
            return
        await query.edit_message_text("🚀 Subiendo a la web...")
        try:
            create_scientific_post(item['data']['title'], item['data']['description'], item['data']['content'], item['data']['category'], item['data'].get('image_prompt'), source_url=item['url'])
            push_to_github()
            if os.path.exists(item['file']): os.remove(item['file'])
            await query.edit_message_text(f"✨ **¡PUBLICADO!**\n'{item['data']['title']}' ya está online.")
            del context.bot_data[f"post_{ref_id}"]
        except Exception as e: await query.edit_message_text(f"❌ Error: {e}")

    elif action == "del":
        item = context.bot_data.get(f"post_{ref_id}")
        if item and os.path.exists(item['file']): os.remove(item['file'])
        await query.edit_message_text("🗑️ Noticia eliminada.")
        if f"post_{ref_id}" in context.bot_data: del context.bot_data[f"post_{ref_id}"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID: return
    await update.message.reply_text("🔬 **VANGUARDIA IA v2.2**\n\n- Envíame un link directo.\n- Usa /radar para buscar nuevas.\n- Usa /bandeja para ver pendientes.")

async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Inicio"),
        BotCommand("radar", "Buscar noticias"),
        BotCommand("bandeja", "Ver bandeja")
    ])

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("radar", lambda u, c: subprocess.run([sys.executable, str(BASE_DIR / "radar.py")]))) # Simplificado para el radar
    application.add_handler(CommandHandler("bandeja", bandeja))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling()
