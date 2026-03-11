import os
import sys
import asyncio
import logging
import json
import re
import subprocess
from datetime import datetime, timedelta
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
BASE_DIR = Path("C:/Users/leoli/BOTS_SYSTEM/VanguardiaCiencia_Web/bot")
BANDEJA_DIR = BASE_DIR / "bandeja_de_entrada"
SCRIPTS_DIR = BASE_DIR.parent / "scripts"
GEMINI_SESSION = os.getenv("GEMINI_SESSION", "vanguardia-editor")

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
    vault_path = r"C:\Users\leoli\OneDrive\Desktop\OBSYNC\obsync2notehuawei\L30l1b_vault\Bots_Context\Vanguardia_Editor.md"
    try:
        command = f'gemini -y --resume {GEMINI_SESSION} -p "@{vault_path} {prompt}" -o stream-json'
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
        
        # ASEGURAR QUE LA URL SE GUARDE CORRECTAMENTE
        url_to_process = news_data.get('link')
        
        await query.edit_message_text(f"⏳ Análisis asíncrono iniciado ({ref_id})...")
        asyncio.create_task(task_analysis(context, update.effective_chat.id, url_to_process, ref_id, filename))

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

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra estadísticas detalladas de la web y el sistema."""
    if update.effective_user.id != ALLOWED_USER_ID: return
    
    msg = await update.message.reply_text("📊 Calculando estadísticas reales...")
    
    # 1. Contar noticias por categoría
    blog_dir = Path(BASE_DIR).parent / "src" / "content" / "blog"
    files = list(blog_dir.glob("*.md"))
    total_posts = len(files)
    
    cat_counts = {}
    for f_path in files:
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                content = f.read()
                match = re.search(r'category: "(.*?)"', content)
                if match:
                    cat = match.group(1)
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1
        except: continue

    # 2. Leer balance de Freepik
    freepik_info = "Último saldo: Desconocido"
    balance_file = Path(BASE_DIR).parent / "scripts" / "freepik_balance.txt"
    if balance_file.exists():
        try:
            with open(balance_file, "r") as f:
                freepik_info = f.read().strip()
        except: pass

    # 3. Preparar el reporte
    stats_text = f"📈 **ESTADÍSTICAS VANGUARDIA CIENCIA**\n\n"
    stats_text += f"📝 **Total Noticias:** {total_posts}\n\n"
    stats_text += "📂 **Distribución por Categoría:**\n"
    
    for cat, count in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
        stats_text += f"• {cat}: {count}\n"
    
    stats_text += f"\n📥 **Bandeja de Entrada:** {len(list(BANDEJA_DIR.glob('*.json')))} pendientes\n"
    stats_text += f"🚀 **Servidor:** Online (Vercel)\n"
    stats_text += f"🎨 **Freepik AI:** {freepik_info}"

    await msg.edit_text(stats_text, parse_mode="Markdown")

from pubmed_scout import search_pubmed

# ... (resto de imports y config)

async def investigar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Busca investigaciones reales en PubMed."""
    if update.effective_user.id != ALLOWED_USER_ID: return
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Uso: /investigar [tema] (ej: /investigar longevidad)")
        return

    msg = await update.message.reply_text(f"🔍 Investigando '{query}' en PubMed Central...")
    
    def run_search():
        return search_pubmed(query, max_results=5)
    
    results = await asyncio.get_event_loop().run_in_executor(None, run_search)
    
    if not results:
        await msg.edit_text(f"❌ No encontré papers recientes sobre '{query}'.")
        return

    text = f"🧬 **RESULTADOS DE INVESTIGACIÓN PARA: {query.upper()}**\n\n"
    keyboard = []
    row = []
    
    # Usar el mismo sistema de file_map para procesar
    for i, res in enumerate(results):
        idx = str(len(file_map) + 1)
        # Guardamos en la bandeja temporalmente para que se pueda procesar
        filename = f"pubmed_{idx}.json"
        f_path = BANDEJA_DIR / filename
        with open(f_path, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=4, ensure_ascii=False)
        
        file_map[idx] = filename
        text += f"{idx}. 🔬 **{res['title'][:70]}...**\n   📅 *{res['date']}*\n\n"
        row.append(InlineKeyboardButton(idx, callback_data=f"p_{idx}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    
    if row: keyboard.append(row)
    await msg.delete()
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def semanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Accede al número semanal completo de Nature y extrae todos los artículos destacados."""
    if update.effective_user.id != ALLOWED_USER_ID: return
    
    msg = await update.message.reply_text("🔎 Explorando la edición semanal completa de Nature... (Esto puede tomar un momento)")
    
    prompt = (
        "Navega a https://www.nature.com/nature/current-issue y extrae los títulos y links de TODOS los artículos "
        "de investigación (Research Articles) y noticias de impacto que encuentres. Captura hasta 30 resultados. "
        "IMPORTANTE: Los links deben ser URLs COMPLETAS (https://www.nature.com/...). "
        "Devuelve SOLO un JSON: [{'title': '...', 'link': '...'}]"
    )
    
    try:
        command = f'gemini -y --resume {GEMINI_SESSION} -p "{prompt}" -o stream-json'
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
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        
        if json_match:
            results = json.loads(json_match.group(0))
            text = f"📅 **EDICIÓN SEMANAL: {len(results)} ARTÍCULOS DETECTADOS**\n\n"
            keyboard = []
            row = []
            file_map.clear() # Empezar de cero para esta lista
            
            for i, res in enumerate(results):
                idx = str(i + 1)
                link = res['link']
                if link.startswith('/'): link = f"https://www.nature.com{link}"
                
                filename = f"weekly_{idx}.json"
                with open(BANDEJA_DIR / filename, "w", encoding="utf-8") as f:
                    json.dump({"title": res['title'], "link": link, "source": "Nature Weekly"}, f, indent=4, ensure_ascii=False)
                
                file_map[idx] = filename
                text += f"{idx}. 📘 **{res['title'][:70]}...**\n\n"
                
                row.append(InlineKeyboardButton(idx, callback_data=f"p_{idx}"))
                if len(row) == 5:
                    keyboard.append(row)
                    row = []
            
            if row: keyboard.append(row)
            
            # Si el texto es muy largo para un solo mensaje de Telegram (4096 carac)
            if len(text) > 4000:
                await msg.delete()
                await update.message.reply_text(text[:4000] + "...", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            else:
                await msg.delete()
                await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await msg.edit_text("❌ No pude extraer la lista completa. Intenta de nuevo o revisa si Nature cambió su estructura.")
    except Exception as e:
        logging.error(f"Error en semanal masivo: {e}")
        await msg.edit_text("❌ Error al procesar la edición semanal.")

async def boletin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera un resumen semanal basado en las últimas 5 noticias publicadas."""
    if update.effective_user.id != ALLOWED_USER_ID: return
    
    msg = await update.message.reply_text("🗞️ Generando boletín semanal 'Vanguardia Weekly'...")
    
    # 1. Obtener las últimas 5 noticias reales del blog
    blog_dir = Path(BASE_DIR).parent / "src" / "content" / "blog"
    files = sorted(list(blog_dir.glob("*.md")), key=os.path.getmtime, reverse=True)[:5]
    
    if not files:
        await msg.edit_text("❌ No hay noticias publicadas para generar un boletín.")
        return

    summaries = []
    for f_path in files:
        try:
            content = f_path.read_text(encoding='utf-8')
            # Extracción más flexible de metadatos
            title_match = re.search(r'title:\s*"(.*?)"', content)
            desc_match = re.search(r'description:\s*"(.*?)"', content)
            if title_match and desc_match:
                summaries.append(f"NOTICIA: {title_match.group(1)}\nRESUMEN: {desc_match.group(1)}")
        except Exception as e:
            logging.error(f"Error leyendo post {f_path.name}: {e}")
            continue

    if not summaries:
        await msg.edit_text("❌ No pude leer los datos de las noticias publicadas.")
        return

    # 2. Pedir a Gemini que redacte el boletín (Modo Texto, no JSON para este caso)
    newsletter_prompt = (
        "Actúa como el Editor Jefe de Vanguardia Ciencia. Eres un experto en comunicación científica. "
        "Basándote en estas noticias de la semana, redacta un boletín semanal (Vanguardia Weekly) "
        "elegante, técnico y profesional en español. Conecta los temas entre sí y añade una reflexión editorial. "
        "Usa Markdown (negritas, listas) y emojis científicos.\n\n"
        "DATOS DE LA SEMANA:\n" + "\n\n".join(summaries)
    )
    
    try:
        # Para el boletín usamos respuesta directa de texto
        command = f'gemini -y --resume {GEMINI_SESSION} -p "{newsletter_prompt}"'
        process = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await process.communicate()
        text = stdout.decode('utf-8', errors='ignore').strip()
        
        # Limpiar códigos ANSI si existen
        clean_text = ANSI_ESCAPE.sub('', text).strip()
        
        if clean_text:
            header = "🗞️ **VANGUARDIA WEEKLY - BOLETÍN CIENTÍFICO**\n\n"
            full_msg = header + clean_text
            
            if len(full_msg) > 4000:
                for i in range(0, len(full_msg), 4000):
                    await update.message.reply_text(full_msg[i:i+4000], parse_mode="Markdown")
            else:
                await msg.delete()
                await update.message.reply_text(full_msg, parse_mode="Markdown")
        else:
            await msg.edit_text("❌ Gemini no generó el contenido del boletín.")
    except Exception as e:
        logging.error(f"Error en Gemini boletín: {e}")
        await msg.edit_text("❌ Error técnico al generar el boletín.")

async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Inicio"),
        BotCommand("radar", "Escanear noticias"),
        BotCommand("semanal", "Número actual de Nature"),
        BotCommand("bandeja", "Ver pendientes"),
        BotCommand("boletin", "Generar Newsletter semanal"),
        BotCommand("investigar", "PubMed [tema]"),
        BotCommand("stats", "Estadísticas web")
    ])

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    application.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("🔬 Vanguardia Editor v2.3 INTERACTIVO Activo")))
    application.add_handler(CommandHandler("radar", run_radar_cmd))
    application.add_handler(CommandHandler("bandeja", bandeja))
    application.add_handler(CommandHandler("semanal", semanal))
    application.add_handler(CommandHandler("investigar", investigar))
    application.add_handler(CommandHandler("boletin", boletin))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling()
