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

async def process_with_gemini(url):
    """Procesamiento profundo obligando a la navegación real."""
    instruction = (
        "Actúa como el Editor Jefe de Vanguardia Ciencia. ES OBLIGATORIO que navegues a la URL proporcionada "
        "y leas el artículo completo. No te bases solo en el título. Extrae datos técnicos, nombres de investigadores "
        "o instituciones. Luego, genera un JSON profesional en español: "
        "{'title', 'category', 'description', 'content', 'image_prompt'}. "
        "Usa Markdown técnico para el contenido."
    )
    try:
        command = f'gemini -y -p "{instruction} URL a investigar: {url}" -o stream-json'
        process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        
        full_response = ""
        while True:
            line = await process.stdout.readline()
            if not line: break
            try:
                line_decoded = line.decode('utf-8', errors='ignore').strip()
                if not (line_decoded.startswith('{') and line_decoded.endswith('}')): continue
                
                data = json.loads(line_decoded)
                # CRÍTICO: Solo acumular contenido si el rol es 'assistant'
                if data.get('type') == 'message' and data.get('role') == 'assistant':
                    chunk = data.get('content', '')
                    if chunk: full_response += chunk
            except: continue
        
        await process.wait()
        
        if not full_response:
            logging.error("Gemini no generó ninguna respuesta para el asistente.")
            return None

        # Limpiar y extraer JSON
        content = ANSI_ESCAPE.sub('', full_response).strip()
        content = re.sub(r'```json\s*|```\s*', '', content).strip()
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        
        logging.error(f"JSON no válido. Respuesta completa: {content[:200]}...")
        return None
    except Exception as e:
        logging.error(f"Error crítico: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID: return
    help_text = (
        "🔬 **VANGUARDIA IA v2.0**\n\n"
        "1. Usa /radar para buscar novedades.\n"
        "2. Usa /bandeja para ver las noticias guardadas."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

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

    text = "📂 **NOTICIAS EN BANDEJA:**\n\n"
    keyboard = []
    
    # Mostrar las últimas 5 noticias de la bandeja
    for i, f_path in enumerate(files[:5]):
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            idx = str(i + 1)
            title = data.get('title', 'Sin título').replace('*', '').replace('_', '')
            text += f"{idx}. 📰 {title[:70]}...\n\n"
            keyboard.append(InlineKeyboardButton(idx, callback_data=f"proc_{f_path.name}"))
        except Exception as e:
            logging.error(f"Error leyendo {f_path.name}: {e}")
            continue

    if keyboard:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup([keyboard]), parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ No se pudo procesar ninguna noticia de la bandeja (Error de lectura).")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Usamos split con límite 1 para que el nombre del archivo se mantenga íntegro
    data_parts = query.data.split('_', 1)
    action = data_parts[0]
    filename = data_parts[1] if len(data_parts) > 1 else ""

    if action == "proc":
        f_path = BANDEJA_DIR / filename
        if not f_path.exists():
            await query.edit_message_text("❌ Archivo no encontrado.")
            return
        
        with open(f_path, "r", encoding="utf-8") as f:
            news_data = json.load(f)
        
        await query.edit_message_text(f"🧠 Analizando con Gemini: {news_data['title'][:40]}...\n(Espera unos 40s)")
        
        result = await process_with_gemini(news_data['link'])
        if result:
            context.user_data['last_news'] = result
            context.user_data['last_url'] = news_data['link']
            context.user_data['last_file'] = f_path
            
            preview = (
                f"📝 **VISTA PREVIA**\n\n"
                f"📌 **{result.get('title', 'Sin título')}**\n\n"
                f"{result.get('content', 'Sin contenido')[:400]}...\n\n"
                f"¿Publicar en la web?"
            )
            btns = [[InlineKeyboardButton("✅ Publicar", callback_data="publish_now"),
                     InlineKeyboardButton("🗑️ Borrar", callback_data=f"delete_{filename}")]]
            await query.edit_message_text(preview, reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Error al procesar con IA.")

    elif query.data == "publish_now":
        item = context.user_data.get('last_news')
        if not item: return
        await query.edit_message_text("🚀 Subiendo a la web...")
        try:
            create_scientific_post(item['title'], item['description'], item['content'], item['category'], item.get('image_prompt'))
            push_to_github()
            if 'last_file' in context.user_data and os.path.exists(context.user_data['last_file']):
                os.remove(context.user_data['last_file'])
            await query.edit_message_text(f"✨ **¡PUBLICADO!**\nLa noticia ya está en Vercel.")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

    elif action == "delete":
        f_path = BANDEJA_DIR / filename
        if f_path.exists(): os.remove(f_path)
        await query.edit_message_text("🗑️ Noticia eliminada.")

async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Inicio"),
        BotCommand("radar", "Buscar nuevas noticias"),
        BotCommand("bandeja", "Ver noticias en espera")
    ])

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("radar", run_radar_cmd))
    application.add_handler(CommandHandler("bandeja", bandeja))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling()
