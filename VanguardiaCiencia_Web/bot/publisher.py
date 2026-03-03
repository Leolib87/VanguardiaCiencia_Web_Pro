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

SYSTEM_INSTRUCTION = (
    "Actúa como el Editor Jefe de Vanguardia Ciencia. ES OBLIGATORIO que navegues a la URL proporcionada "
    "y leas el artículo completo. Extrae datos técnicos y genera un JSON profesional en español. "
    "CATEGORÍAS FIJAS: Salud y Medicina, Física y Química, Tecnología y Espacio, "
    "Medio Ambiente, Inteligencia Artificial, Biología y Genómica. "
    "Responde SOLO con un JSON: {'title', 'category', 'description', 'content', 'image_prompt'}."
)

async def process_with_gemini(prompt):
    """Llama a Gemini de forma genérica para análisis o refinado."""
    try:
        command = f'gemini -y -p "{prompt}" -o stream-json'
        process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        
        full_response = ""
        while True:
            line = await process.stdout.readline()
            if not line: break
            try:
                line_decoded = line.decode('utf-8', errors='ignore').strip()
                if not (line_decoded.startswith('{') and line_decoded.endswith('}')): continue
                data = json.loads(line_decoded)
                if data.get('type') == 'message' and data.get('role') == 'assistant':
                    chunk = data.get('content', '')
                    if chunk: full_response += chunk
            except: continue
        
        await process.wait()
        content = ANSI_ESCAPE.sub('', full_response).strip()
        content = re.sub(r'```json\s*|```\s*', '', content).strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        return json.loads(json_match.group(0)) if json_match else None
    except: return None

async def task_analysis(context, chat_id, url, ref_id, filename, instruction=None, current_data=None):
    """Tarea de análisis que soporta refinado interactivo."""
    if instruction and current_data:
        # Modo Refinado
        prompt = (
            f"Como Editor Jefe, aplica este cambio al artículo actual:\n"
            f"INSTRUCCIÓN DEL USUARIO: {instruction}\n\n"
            f"ARTÍCULO ACTUAL (JSON): {json.dumps(current_data)}\n\n"
            f"Devuelve el nuevo JSON corregido manteniendo la estructura."
        )
        msg_text = "✍️ Refinando artículo según tus instrucciones..."
    else:
        # Modo Análisis Inicial
        prompt = f"{SYSTEM_INSTRUCTION} URL a investigar: {url}"
        msg_text = None # Ya se envió el mensaje de inicio asíncrono

    result = await process_with_gemini(prompt)
    
    if result:
        post_key = f"post_{ref_id}"
        context.bot_data[post_key] = {'data': result, 'url': url, 'file': str(BANDEJA_DIR / filename)}
        # Activar este ID como el que se está editando actualmente
        context.user_data['active_edit_id'] = ref_id
        
        preview = (
            f"✅ **PROPUESTA EDITORIAL**\n\n"
            f"📌 **{result.get('title', 'Sin título')}**\n"
            f"🗂️ **Categoría:** {result.get('category')}\n\n"
            f"{result.get('content', 'Sin contenido')[:600]}...\n\n"
            f"💡 *Puedes escribirme cambios (ej: 'hazlo más técnico') o publicar:* "
        )
        btns = [[InlineKeyboardButton("✅ PUBLICAR", callback_data=f"pubfinal_{ref_id}"),
                 InlineKeyboardButton("🗑️ BORRAR", callback_data=f"del_{ref_id}")]]
        await context.bot.send_message(chat_id=chat_id, text=preview, reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Falló el procesamiento de la noticia {ref_id}.")

async def bandeja(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID: return
    files = sorted(list(BANDEJA_DIR.glob("*.json")), key=os.path.getmtime, reverse=True)
    if not files:
        await update.message.reply_text("📭 Bandeja vacía. Usa /radar.")
        return

    text = f"📂 **BANDEJA VANGUARDIA ({len(files)} noticias):**\n\n"
    keyboard = []
    row = []
    file_map.clear()

    for i, f_path in enumerate(files[:20]):
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            idx = str(i + 1)
            file_map[idx] = f_path.name
            source_info = data.get('source', 'Nature')
            text += f"{idx}. {source_info} **{data.get('title', 'Sin título')[:60]}...**\n\n"
            row.append(InlineKeyboardButton(idx, callback_data=f"p_{idx}"))
            if len(row) == 5:
                keyboard.append(row)
                row = []
        except: continue

    if row: keyboard.append(row)
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID: return
    text = update.message.text.strip()
    
    # 1. Si es un link, análisis nuevo
    if text.startswith("http"):
        url = text
        ref_id = str(hash(url))[-5:]
        await update.message.reply_text("📡 Link detectado. Iniciando análisis profundo...")
        asyncio.create_task(task_analysis(context, update.effective_chat.id, url, ref_id, f"direct_{ref_id}.json"))
        return

    # 2. Si hay una edición activa, es una instrucción de refinado
    active_id = context.user_data.get('active_edit_id')
    if active_id:
        item = context.bot_data.get(f"post_{active_id}")
        if item:
            await update.message.reply_text(f"✍️ Aplicando cambios a: *{item['data']['title'][:40]}...*", parse_mode="Markdown")
            asyncio.create_task(task_analysis(context, update.effective_chat.id, item['url'], active_id, Path(item['file']).name, instruction=text, current_data=item['data']))
            return

    await update.message.reply_text("👋 Hola. Envíame un link o usa /bandeja.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_parts = query.data.split('_')
    action = data_parts[0]
    ref_id = data_parts[1] if len(data_parts) > 1 else ""

    if action == "p":
        filename = file_map.get(ref_id)
        if not filename:
            await query.edit_message_text("❌ Referencia expirada.")
            return
        f_path = BANDEJA_DIR / filename
        with open(f_path, "r", encoding="utf-8") as f: news_data = json.load(f)
        await query.edit_message_text(f"⏳ Análisis asíncrono iniciado ({ref_id})...")
        asyncio.create_task(task_analysis(context, update.effective_chat.id, news_data['link'], ref_id, filename))

    elif action == "pubfinal":
        item = context.bot_data.get(f"post_{ref_id}")
        if not item:
            await query.edit_message_text("❌ Datos perdidos.")
            return
        await query.edit_message_text("🚀 Publicando...")
        try:
            create_scientific_post(item['data']['title'], item['data']['description'], item['data']['content'], item['data']['category'], item['data'].get('image_prompt'), source_url=item['url'])
            push_to_github()
            if os.path.exists(item['file']): os.remove(item['file'])
            await query.edit_message_text(f"✨ **¡PUBLICADO!**\nYa está online.")
            # Limpiar rastro de edición
            context.user_data['active_edit_id'] = None
            del context.bot_data[f"post_{ref_id}"]
        except Exception as e: await query.edit_message_text(f"❌ Error: {e}")

    elif action == "del":
        await query.edit_message_text("🗑️ Noticia eliminada de la bandeja.")
        context.user_data['active_edit_id'] = None
        item = context.bot_data.get(f"post_{ref_id}")
        file_path = item['file'] if item else (str(BANDEJA_DIR / file_map.get(ref_id)) if ref_id in file_map else None)
        if file_path and os.path.exists(file_path): os.remove(file_path)

async def run_radar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ejecuta el script del radar de forma segura."""
    if update.effective_user.id != ALLOWED_USER_ID: return
    msg = await update.message.reply_text("📡 **Radar v4.0:** Escaneando Nature, Science y ScienceDaily...")
    
    # Usamos run_in_executor para no bloquear el bot mientras el radar escanea
    def run_script():
        return subprocess.run([sys.executable, str(BASE_DIR / "radar.py")], capture_output=True, text=True)
    
    await asyncio.get_event_loop().run_in_executor(None, run_script)
    await msg.edit_text("✅ **Radar finalizado.** Las fuentes han sido actualizadas. Usa /bandeja para ver las novedades.")

async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Inicio"),
        BotCommand("radar", "Escanear fuentes"),
        BotCommand("bandeja", "Ver bandeja")
    ])

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("🔬 Vanguardia Editor v2.3 INTERACTIVO Activo")))
    application.add_handler(CommandHandler("radar", run_radar_cmd))
    application.add_handler(CommandHandler("bandeja", bandeja))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling()
