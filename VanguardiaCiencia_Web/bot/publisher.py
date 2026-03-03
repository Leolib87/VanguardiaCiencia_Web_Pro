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

# Mapeo global para evitar errores de longitud en botones de Telegram
file_map = {}

async def process_with_gemini(url):
    """Procesamiento profundo con timeout de seguridad de 60 segundos."""
    instruction = (
        "Actúa como el Editor Jefe de Vanguardia Ciencia. ES OBLIGATORIO que navegues a la URL proporcionada "
        "y leas el artículo completo. Extrae datos técnicos y genera un JSON profesional en español: "
        "{'title', 'category', 'description', 'content', 'image_prompt'}. "
        "Usa Markdown técnico para el contenido."
    )
    try:
        command = f'gemini -y -p "{instruction} URL: {url}" -o stream-json'
        process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        
        full_response = ""
        try:
            while True:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=60)
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
            logging.error("TIMEOUT: Gemini tardó más de 60s.")
            return None
        
        await process.wait()
        content = ANSI_ESCAPE.sub('', full_response).strip()
        content = re.sub(r'```json\s*|```\s*', '', content).strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        return json.loads(json_match.group(0)) if json_match else None
    except Exception as e:
        logging.error(f"Error Crítico Gemini: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID: return
    await update.message.reply_text("🔬 **VANGUARDIA IA v2.1 (Protección contra Bloqueos)**\n\n/radar - Buscar nuevas\n/bandeja - Ver pendientes")

async def run_radar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID: return
    msg = await update.message.reply_text("📡 Ejecutando Radar...")
    subprocess.run([sys.executable, str(BASE_DIR / "radar.py")])
    await msg.edit_text("✅ Radar finalizado. Usa /bandeja para ver los resultados.")

async def bandeja(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID: return
    
    files = sorted(list(BANDEJA_DIR.glob("*.json")), key=os.path.getmtime, reverse=True)
    if not files:
        await update.message.reply_text("📭 La bandeja está vacía. Usa /radar primero.")
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
            title = data.get('title', 'Sin título').replace('*', '').replace('_', '')
            text += f"{idx}. 📰 {title[:65]}...\n\n"
            
            row.append(InlineKeyboardButton(idx, callback_data=f"p_{idx}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        except: continue

    if row: keyboard.append(row)
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split('_')
    action = data_parts[0]
    ref_id = data_parts[1] if len(data_parts) > 1 else ""

    if action == "p":
        filename = file_map.get(ref_id)
        if not filename:
            await query.edit_message_text("❌ Referencia expirada. Usa /bandeja de nuevo.")
            return
            
        f_path = BANDEJA_DIR / filename
        with open(f_path, "r", encoding="utf-8") as f:
            news_data = json.load(f)
        
        await query.edit_message_text(f"🧠 Analizando (Máx 60s): {news_data['title'][:40]}...")
        
        result = await process_with_gemini(news_data['link'])
        if result:
            context.user_data['last_news'] = result
            context.user_data['last_url'] = news_data['link']
            context.user_data['last_file'] = str(f_path)
            
            preview = (
                f"📝 **VISTA PREVIA**\n\n"
                f"📌 **{result.get('title', 'Sin título')}**\n\n"
                f"{result.get('content', 'Sin contenido')[:500]}...\n\n"
                f"¿Publicar noticia?"
            )
            btns = [[InlineKeyboardButton("✅ PUBLICAR", callback_data="publish_final"),
                     InlineKeyboardButton("🗑️ BORRAR", callback_data=f"d_{ref_id}")]]
            await query.edit_message_text(preview, reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ El análisis tardó demasiado o falló. Intenta con otra noticia.")

    elif query.data == "publish_final":
        item = context.user_data.get('last_news')
        url = context.user_data.get('last_url')
        file_to_del = context.user_data.get('last_file')
        if not item: return
        
        await query.edit_message_text("🚀 Subiendo a la web...")
        try:
            create_scientific_post(item['title'], item['description'], item['content'], item['category'], item.get('image_prompt'), source_url=url)
            push_to_github()
            if file_to_del and os.path.exists(file_to_del): os.remove(file_to_del)
            await query.edit_message_text(f"✨ **¡PUBLICADO!**\nLa noticia ya está en camino a Vercel.")
        except Exception as e: await query.edit_message_text(f"❌ Error: {e}")

    elif action == "d":
        filename = file_map.get(ref_id)
        if filename:
            f_path = BANDEJA_DIR / filename
            if f_path.exists(): os.remove(f_path)
            await query.edit_message_text("🗑️ Noticia eliminada de la bandeja.")

async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Inicio"),
        BotCommand("radar", "Buscar noticias"),
        BotCommand("bandeja", "Ver bandeja")
    ])

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("radar", run_radar_cmd))
    application.add_handler(CommandHandler("bandeja", bandeja))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling()
