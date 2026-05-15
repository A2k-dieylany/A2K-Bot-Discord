"""
╔══════════════════════════════════════════════════════════════╗
║        🤖 AI DISCORD BOT — Agent Polyvalent (Gemini)         ║
║     + AUTOMATISATION WHATSAPP (SAV IA, Planning, Webhook)    ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import discord
from discord import app_commands
from discord.ext import commands
import google.generativeai as genai
from dotenv import load_dotenv
from collections import defaultdict
import aiohttp
from aiohttp import web
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import sqlite3

# ── Configuration ──────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BOT_NAME      = os.getenv("BOT_NAME", "MonBot")
MAX_HISTORY   = int(os.getenv("MAX_HISTORY", 20))
MODEL_NAME    = "gemini-2.5-flash-lite"   # Modèle version "lite" avec un énorme quota gratuit

# ── WhatsApp (Green API) ───────────────────────────────────────
WA_ID_INSTANCE = os.getenv("WA_ID_INSTANCE")
WA_API_TOKEN   = os.getenv("WA_API_TOKEN")

# ── Canal Discord pour les logs WhatsApp ──────────────────────
WA_LOG_CHANNEL = int(os.getenv("WA_LOG_CHANNEL", "0"))

# ── Informations Business ──────────────────────────────────────
BUSINESS_NAME  = os.getenv("BUSINESS_NAME", "notre entreprise")
BUSINESS_INFO  = os.getenv("BUSINESS_INFO", "Nous proposons des services de qualité.")

# ── Base de Connaissances (Le Cerveau) ─────────────────────────
try:
    with open("connaissances.txt", "r", encoding="utf-8") as f:
        BASE_DE_CONNAISSANCES = f.read()
except FileNotFoundError:
    BASE_DE_CONNAISSANCES = "Aucune information supplémentaire."

# ── Clients ────────────────────────────────────────────────────
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ── Mémoire de conversation par salon/thread (Discord) ─────────
conversation_memory: dict[int, list] = defaultdict(list)

# ── Base de Données SQLite (Mémoire WhatsApp) ──────────────────
conn = sqlite3.connect("memory.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS wa_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT,
        role TEXT,
        content TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# ── Scheduler pour les messages programmés ────────────────────
scheduler = AsyncIOScheduler(timezone="Africa/Dakar")
wa_planning: list[dict] = []
planning_counter = 0

# ── Prompts système ────────────────────────────────────────────
SYSTEM_PROMPT = """Tu es un assistant IA ultra-puissant et polyvalent intégré à Discord.
Tu es expert en :
- Programmation (Python, JavaScript, TypeScript, Rust, Go, Java, C/C++, SQL, HTML/CSS, etc.)
- Débogage et optimisation de code
- Architecture logicielle et conception de systèmes
- Mathématiques avancées, statistiques et logique
- Rédaction, correction et amélioration de textes
- Analyse et résumé de documents
- Gestion de projets et planification
- Traduction dans toutes les langues
- Conseils professionnels et stratégiques

Règles importantes :
- Réponds toujours en français sauf si on te demande une autre langue
- Pour le code, utilise TOUJOURS des blocs markdown (```langage ... ```)
- Sois précis, structuré et professionnel
- Si une tâche est complexe, décompose-la en étapes claires
- Sois direct, efficace, et va à l'essentiel
"""

SAV_PROMPT = f"""Tu es Max, l'assistante de Dieylany (qui dirige l'agence {BUSINESS_NAME}).
Voici ce que fait l'agence : {BUSINESS_INFO}

*** BASE DE CONNAISSANCES DE L'AGENCE ***
Voici les informations exactes de l'agence que tu dois utiliser pour répondre aux questions. Ne propose jamais de prix ou de délais qui ne sont pas ici :
{BASE_DE_CONNAISSANCES}
*****************************************

TON RÔLE :
Tu dois accueillir les clients, répondre à leurs questions, les guider dans leurs choix, et récupérer les informations clés de leur projet de manière fluide, avant de passer le relais à Dieylany ou un autre humain de l'équipe.

TON TON & TA PERSONNALITÉ :
- Sois très chaleureuse, humaine, naturelle et professionnelle.
- Utilise des emojis pour rendre la conversation conviviale 😊.
- Fais des réponses courtes, directes et aérées (max 2 à 3 phrases par réponse) car c'est WhatsApp.
- Adapte-toi à la langue de l'interlocuteur (s'il parle français, anglais, wolof...).

RÈGLES STRICTES :
1. Dès le premier message avec un nouveau client, tu DOIS TOUJOURS te présenter sous cette forme exacte : "Bonjour [Nom du client si connu, sinon bonjour simple] 👋 ! Je suis Max, l'assistante de Dieylany..." puis enchainer naturellement.
2. IMPORTANT : Tu as des YEUX et des OREILLES. Si le client t'envoie une image ou une note vocale, tu es capable de les analyser et de les écouter ! Fais-y référence dans ta réponse (ex: "J'ai bien écouté ton vocal..."). Pour les autres documents PDF/Word, dis que Dieylany les regardera.
3. Si le client demande à parler à un humain, rassure-le en lui disant que tu as notifié Dieylany et qu'il va prendre le relais sur cette conversation d'ici quelques instants.
4. Si on te pose une question complexe ou hors de tes connaissances, explique avec tact que tu notes la question pour que Dieylany lui réponde avec précision.
5. Termine souvent tes réponses par une question simple pour encourager le client à détailler son besoin (ex: "Quel type de site avez-vous en tête ?").
6. Si le client semble très intéressé, prêt à passer commande, ou s'il demande formellement à parler à un humain/Dieylany, tu DOIS OBLIGATOIREMENT ajouter ce code secret tout à la fin de ta réponse : [ALERTE_PROSPECT]. Ce code me permettra de déclencher une alarme. Ne le mets pas pour les questions banales.
"""

model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    system_instruction=SYSTEM_PROMPT
)

wa_model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    system_instruction=SAV_PROMPT
)

# ══════════════════════════════════════════════════════════════
#  FONCTIONS UTILITAIRES (Discord IA)
# ══════════════════════════════════════════════════════════════

def add_to_memory(session_id: int, role: str, content: str):
    conversation_memory[session_id].append({"role": role, "content": content})
    if len(conversation_memory[session_id]) > MAX_HISTORY:
        conversation_memory[session_id] = conversation_memory[session_id][-MAX_HISTORY:]

def get_history(session_id: int) -> list:
    return conversation_memory.get(session_id, [])

async def ask_gemini(session_id: int, user_message: str) -> str:
    add_to_memory(session_id, "user", user_message)
    
    contents = []
    for msg in get_history(session_id):
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [msg["content"]]})
        
    try:
        response = await model.generate_content_async(
            contents,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=2000,
            )
        )
        reply = response.text
        add_to_memory(session_id, "assistant", reply)
        return reply
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Quota exceeded" in error_msg:
            return "⏳ Oups, j'ai reçu trop de questions en même temps ! Peux-tu patienter 15 secondes et me reposer la question ? 😊"
        return f"❌ Erreur : {e}"

def split_message(text: str, limit: int = 1990) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks

class ActionView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=86400)
        self.user_id = user_id

    @discord.ui.button(label="🗑️ Supprimer", style=discord.ButtonStyle.danger)
    async def btn_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.user_id:
            await interaction.message.delete()
        else:
            await interaction.response.send_message("❌ Seul l'auteur peut supprimer ce message.", ephemeral=True)

async def send_long_reply(interaction: discord.Interaction, text: str):
    parts = split_message(text)
    view = ActionView(interaction.user.id)
    if len(parts) == 1:
        await interaction.followup.send(parts[0], view=view)
    else:
        await interaction.followup.send(parts[0])
        for i, part in enumerate(parts[1:]):
            if i == len(parts) - 2:
                await interaction.channel.send(part, view=view)
            else:
                await interaction.channel.send(part)

async def send_embed_reply(interaction: discord.Interaction, title: str, text: str, color: int):
    view = ActionView(interaction.user.id)
    if len(text) <= 4096:
        embed = discord.Embed(title=title, description=text, color=color)
        await interaction.followup.send(embed=embed, view=view)
    else:
        parts = []
        temp_text = text
        while len(temp_text) > 4096:
            cut = temp_text.rfind("\n", 0, 4096)
            if cut == -1: cut = 4096
            parts.append(temp_text[:cut])
            temp_text = temp_text[cut:].lstrip("\n")
        if temp_text: parts.append(temp_text)
        
        embed = discord.Embed(title=title, description=parts[0], color=color)
        await interaction.followup.send(embed=embed)
        for i, part in enumerate(parts[1:]):
            embed = discord.Embed(title=f"{title} (Suite)", description=part, color=color)
            if i == len(parts) - 2:
                await interaction.channel.send(embed=embed, view=view)
            else:
                await interaction.channel.send(embed=embed)

# ══════════════════════════════════════════════════════════════
#  WHATSAPP — Fonctions de base et SAV
# ══════════════════════════════════════════════════════════════

async def send_whatsapp(phone: str, message: str) -> dict:
    phone = phone.replace("+", "").replace(" ", "").replace("-", "")
    chat_id = f"{phone}@c.us"
    url = f"https://api.green-api.com/waInstance{WA_ID_INSTANCE}/sendMessage/{WA_API_TOKEN}"
    body = {"chatId": chat_id, "message": message}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body) as resp:
            return await resp.json()

def add_to_wa_memory(phone: str, role: str, content: str):
    cursor.execute("INSERT INTO wa_memory (phone, role, content) VALUES (?, ?, ?)", (phone, role, content))
    conn.commit()

def get_wa_memory(phone: str, limit: int = 10) -> list:
    # Récupérer les X derniers messages triés par date décroissante, puis les remettre dans l'ordre chronologique
    cursor.execute("SELECT role, content FROM (SELECT role, content, timestamp FROM wa_memory WHERE phone = ? ORDER BY timestamp DESC LIMIT ?) ORDER BY timestamp ASC", (phone, limit))
    return [{"role": r[0], "content": r[1]} for r in cursor.fetchall()]

async def ask_gemini_wa(phone: str, user_message: str, media_part=None) -> str:
    add_to_wa_memory(phone, "user", user_message)
    contents = []
    
    # On charge l'historique depuis SQLite
    history = get_wa_memory(phone, limit=10)
    for msg in history:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [msg["content"]]})
        
    if media_part:
        contents[-1]["parts"].insert(0, media_part)
        
    try:
        response = await wa_model.generate_content_async(
            contents,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1000,
            )
        )
        reply = response.text
        add_to_wa_memory(phone, "assistant", reply)
        return reply
    except Exception as e:
        error_msg = str(e)
        print(f"🔴 ERREUR GEMINI DÉTAILLÉE : {error_msg}")
        if "429" in error_msg or "Quota exceeded" in error_msg:
            return "⏳ Oups, on dirait que je réfléchis trop vite ! Laisse-moi 15 secondes pour souffler et renvoie-moi ton message. 😊"
        return f"❌ Erreur : {e}"

async def poll_whatsapp_messages():
    """Vérifie les nouveaux messages WhatsApp toutes les 5 secondes (Bot SAV)."""
    url = f"https://api.green-api.com/waInstance{WA_ID_INSTANCE}/receiveNotification/{WA_API_TOKEN}"
    delete_url = f"https://api.green-api.com/waInstance{WA_ID_INSTANCE}/deleteNotification/{WA_API_TOKEN}"

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(5)
                        continue
                    data = await resp.json()

                if data and data.get("body"):
                    receipt_id = data["receiptId"]
                    body = data["body"]

                    # Traiter les messages textes, images, et vocaux
                    type_msg = body.get("messageData", {}).get("typeMessage")
                    if body.get("typeWebhook") == "incomingMessageReceived" and type_msg in ["textMessage", "imageMessage", "audioMessage", "pttMessage"]:

                        sender = body["senderData"]["sender"]  # ex: 221771234567@c.us
                        phone  = sender.replace("@c.us", "")
                        name   = body["senderData"].get("senderName", phone)
                        
                        text = ""
                        media_part = None
                        
                        if type_msg == "textMessage":
                            text = body["messageData"]["textMessageData"]["textMessage"]
                        elif type_msg in ["imageMessage", "audioMessage", "pttMessage"]:
                            text = body["messageData"]["fileMessageData"].get("caption", "")
                            
                            if type_msg in ["audioMessage", "pttMessage"]:
                                text = "Un message vocal a été envoyé, voici l'audio :"
                            elif not text:
                                text = "Une image a été envoyée, voici l'image :"
                                
                            download_url = body["messageData"]["fileMessageData"].get("downloadUrl")
                            if download_url:
                                try:
                                    async with session.get(download_url) as file_resp:
                                        if file_resp.status == 200:
                                            file_bytes = await file_resp.read()
                                            raw_mime = body["messageData"]["fileMessageData"].get("mimeType", "")
                                            mime_type = raw_mime.split(";")[0] if raw_mime else ("audio/ogg" if "audio" in type_msg or "ptt" in type_msg else "image/jpeg")
                                            media_part = {"mime_type": mime_type, "data": file_bytes}
                                            print(f"✅ Média téléchargé avec succès ({len(file_bytes)} bytes, {mime_type})")
                                        else:
                                            error_body = await file_resp.text()
                                            print(f"⚠️ Échec téléchargement HTTP {file_resp.status}: {error_body}")
                                            text = "[Erreur système : le téléchargement du média a échoué. Dis au client que tu n'as pas pu lire son fichier à cause d'un bug technique.]"
                                except Exception as e:
                                    print("⚠️ Exception lors du téléchargement média :", e)
                                    text = "[Erreur système : bug lors du téléchargement. Dis au client que tu n'as pas pu lire son fichier.]"
                            else:
                                print("⚠️ Aucune downloadUrl trouvée dans le webhook !")
                                text = "[Erreur système : aucun lien de téléchargement fourni par WhatsApp.]"

                        print(f"📱 Message WA reçu de {name} ({phone}): {text}")

                        # Générer réponse IA
                        reply = await ask_gemini_wa(phone, text, media_part)

                        # Détection prospect chaud
                        is_hot = False
                        if "[ALERTE_PROSPECT]" in reply:
                            is_hot = True
                            reply = reply.replace("[ALERTE_PROSPECT]", "").strip()

                        # Délai artificiel pour humaniser Max (simule le temps de frappe)
                        # Par exemple: 0.04 sec par caractère, bloqué entre 2s et 6s
                        delay = max(2.0, min(6.0, len(reply) * 0.04))
                        await asyncio.sleep(delay)

                        # Envoyer la réponse sur WhatsApp
                        await send_whatsapp(phone, reply)

                        # Logger sur Discord
                        if WA_LOG_CHANNEL:
                            channel = bot.get_channel(WA_LOG_CHANNEL)
                            if channel:
                                embed = discord.Embed(
                                    title="🔥 PROSPECT CHAUD ! Action requise" if is_hot else "📱 Nouveau message WhatsApp",
                                    color=0xFF4500 if is_hot else 0x25D366
                                )
                                embed.add_field(name="👤 De", value=f"{name} (`{phone}`)", inline=False)
                                embed.add_field(name="💬 Message client", value=text if text else "(Fichier/Image envoyé)", inline=False)
                                embed.add_field(name="🤖 Réponse Max", value=reply, inline=False)
                                embed.timestamp = datetime.now()
                                content = "@everyone 🚨 **Dieylany, un prospect t'attend sur WhatsApp !**" if is_hot else None
                                await channel.send(content=content, embed=embed)

                    # Supprimer la notification traitée
                    async with session.delete(f"{delete_url}/{receipt_id}") as _:
                        pass

            except Exception as e:
                print(f"⚠️ Erreur polling WA : {e}")

            await asyncio.sleep(5)

# ══════════════════════════════════════════════════════════════
#  WHATSAPP — Planification & Webhook
# ══════════════════════════════════════════════════════════════

async def execute_planned_message(numeros: list, message: str, label: str):
    """Exécute un envoi programmé."""
    print(f"⏰ Exécution planning '{label}' → {len(numeros)} destinataires")
    for num in numeros:
        try:
            await send_whatsapp(num, message)
            await asyncio.sleep(1)  # Éviter le spam
        except Exception as e:
            print(f"❌ Erreur envoi {num}: {e}")

    if WA_LOG_CHANNEL:
        channel = bot.get_channel(WA_LOG_CHANNEL)
        if channel:
            await channel.send(
                f"⏰ **Planning exécuté : {label}**\n"
                f"📢 Envoyé à **{len(numeros)}** contacts\n"
                f"💬 Message : *{message[:100]}...*" if len(message) > 100 else
                f"⏰ **Planning exécuté : {label}**\n"
                f"📢 Envoyé à **{len(numeros)}** contacts\n"
                f"💬 Message : *{message}*"
            )

async def handle_form_notification(request: web.Request) -> web.Response:
    """Endpoint HTTP POST /notify pour notifications de formulaire"""
    try:
        data = await request.json()
        phone   = data.get("phone", "")
        name    = data.get("name", "Client")
        message = data.get("message", "")

        if not phone:
            return web.json_response({"error": "phone requis"}, status=400)

        # Si pas de message, générer un message IA de bienvenue
        if not message:
            prompt = (
                f"Un client nommé {name} vient de remplir un formulaire sur notre site. "
                f"Rédige un message WhatsApp de bienvenue chaleureux et professionnel "
                f"pour {BUSINESS_NAME}. Max 3 lignes."
            )
            try:
                response = await model.generate_content_async(prompt)
                message = response.text
            except Exception:
                message = f"Bonjour {name}, merci de nous avoir contacté ! Nous revenons vers vous rapidement."

        await send_whatsapp(phone, message)

        if WA_LOG_CHANNEL:
            channel = bot.get_channel(WA_LOG_CHANNEL)
            if channel:
                embed = discord.Embed(title="📋 Nouveau formulaire soumis !", color=0x4285F4)
                embed.add_field(name="👤 Nom", value=name, inline=True)
                embed.add_field(name="📱 Téléphone", value=phone, inline=True)
                embed.add_field(name="💬 Message envoyé", value=message, inline=False)
                embed.timestamp = datetime.now()
                await channel.send(embed=embed)

        return web.json_response({"success": True, "message_sent": message})

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def start_webhook_server():
    """Lance le serveur HTTP pour les notifications formulaire."""
    app_web = web.Application()
    app_web.router.add_post("/notify", handle_form_notification)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("🌐 Serveur webhook démarré sur http://localhost:8080/notify")

# ══════════════════════════════════════════════════════════════
#  ÉVÉNEMENTS BOT
# ══════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"╔══════════════════════════════════════════╗")
    print(f"║  ✅ {BOT_NAME} est en ligne !              ")
    print(f"║  🤖 Modèle : {MODEL_NAME}    ")
    print(f"║  📋 Serveurs : {len(bot.guilds)}           ")
    print(f"╚══════════════════════════════════════════╝")
    await bot.tree.sync()
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="vos questions | /ask"
        )
    )
    
    # Lancer les automatisations en arrière-plan
    if WA_ID_INSTANCE and WA_API_TOKEN:
        bot.loop.create_task(poll_whatsapp_messages())
        bot.loop.create_task(start_webhook_server())
        scheduler.start()
        print("✅ Automatisations WhatsApp actives (SAV IA, Webhook, Planning) !")
    else:
        print("⚠️ WhatsApp non configuré (Green API missing)")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    await bot.process_commands(message)

    # Le bot répond à TOUS les messages (sauf s'ils commencent par !)
    if not message.content.startswith("!"):
        text = message.content.replace(f"<@{bot.user.id}>", "").strip()
        
        attached_files_content = ""
        if message.attachments:
            for att in message.attachments:
                if att.size < 1000000: # Limite de 1Mo
                    try:
                        file_bytes = await att.read()
                        file_text = file_bytes.decode('utf-8')
                        attached_files_content += f"\n\n--- Fichier '{att.filename}' ---\n```\n{file_text[:4000]}\n```"
                    except UnicodeDecodeError:
                        pass # Ignore les fichiers binaires
                        
        if not text and not attached_files_content:
            await message.reply("👋 Pose-moi une question ou envoie-moi un fichier texte/code !")
            return
            
        final_prompt = text + attached_files_content

        async with message.channel.typing():
            reply = await ask_gemini(message.channel.id, final_prompt)
            parts = split_message(reply)
            view = ActionView(message.author.id)
            if len(parts) == 1:
                await message.reply(parts[0], view=view)
            else:
                await message.reply(parts[0])
                for i, part in enumerate(parts[1:]):
                    if i == len(parts) - 2:
                        await message.channel.send(part, view=view)
                    else:
                        await message.channel.send(part)

# ══════════════════════════════════════════════════════════════
#  COMMANDES SLASH
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="ask", description="Pose n'importe quelle question à l'IA (fichier supporté)")
@app_commands.describe(question="Ta question", fichier="Un fichier texte ou code (optionnel)")
async def cmd_ask(interaction: discord.Interaction, question: str, fichier: discord.Attachment = None):
    await interaction.response.defer()
    prompt = question
    if fichier and fichier.size < 1000000:
        try:
            file_bytes = await fichier.read()
            file_text = file_bytes.decode('utf-8')
            prompt += f"\n\n--- Fichier '{fichier.filename}' ---\n```\n{file_text[:4000]}\n```"
        except UnicodeDecodeError:
            pass
    reply = await ask_gemini(interaction.channel_id, prompt)
    await send_long_reply(interaction, f"💬 **{interaction.user.display_name}** : {question}\n\n{reply}")

@bot.tree.command(name="code", description="Génère du code dans le langage de ton choix")
@app_commands.describe(langage="Langage (ex: Python, JavaScript...)", description="Ce que doit faire le code")
async def cmd_code(interaction: discord.Interaction, langage: str, description: str):
    await interaction.response.defer()
    prompt = (f"Génère du code {langage} pour : {description}\n\n"
              f"Fournis : 1. Le code complet dans un bloc ```{langage.lower()} "
              f"2. Explication courte 3. Comment l'utiliser")
    reply = await ask_gemini(interaction.channel_id, prompt)
    await send_long_reply(interaction, f"⚙️ **Code {langage}** — *{description}*\n\n{reply}")

@bot.tree.command(name="debug", description="Débogue ton code et corrige les erreurs")
@app_commands.describe(code="Le code problématique", erreur="Le message d'erreur")
async def cmd_debug(interaction: discord.Interaction, code: str, erreur: str = "Non précisée"):
    await interaction.response.defer()
    prompt = (f"Débogue ce code :\n```\n{code}\n```\nErreur : {erreur}\n\n"
              f"Fournis : 1. Le bug identifié 2. Le code corrigé 3. L'explication")
    reply = await ask_gemini(interaction.channel_id, prompt)
    await send_long_reply(interaction, f"🐛 **Débogage :**\n\n{reply}")

@bot.tree.command(name="expliquer", description="Explique un bloc de code")
@app_commands.describe(code="Le code à expliquer")
async def cmd_expliquer(interaction: discord.Interaction, code: str):
    await interaction.response.defer()
    prompt = f"Explique ce code clairement :\n```\n{code}\n```"
    reply = await ask_gemini(interaction.channel_id, prompt)
    await send_long_reply(interaction, f"📖 **Explication :**\n\n{reply}")

@bot.tree.command(name="traduire", description="Traduit un texte dans la langue de ton choix")
@app_commands.describe(texte="Le texte à traduire", langue="Langue cible (ex: Anglais, Wolof...)")
async def cmd_traduire(interaction: discord.Interaction, texte: str, langue: str):
    await interaction.response.defer()
    prompt = f"Traduis ce texte en {langue} :\n\n{texte}"
    reply = await ask_gemini(interaction.channel_id, prompt)
    await send_embed_reply(interaction, f"🌍 Traduction → {langue}", reply, 0x1ABC9C)

@bot.tree.command(name="resume", description="Résume un texte long en points clés")
@app_commands.describe(texte="Le texte à résumer")
async def cmd_resume(interaction: discord.Interaction, texte: str):
    await interaction.response.defer()
    prompt = f"Résume ce texte avec : 1. TL;DR en 2 phrases 2. Points clés 3. Conclusion\n\n{texte}"
    reply = await ask_gemini(interaction.channel_id, prompt)
    await send_embed_reply(interaction, "📝 Résumé du texte", reply, 0x9B59B6)

@bot.tree.command(name="tache", description="Décompose une tâche complexe en étapes")
@app_commands.describe(tache="La tâche complexe à accomplir")
async def cmd_tache(interaction: discord.Interaction, tache: str):
    await interaction.response.defer()
    prompt = (f"Décompose cette tâche en étapes concrètes : {tache}\n\n"
              f"Inclus : analyse, étapes détaillées, outils recommandés, pièges à éviter")
    reply = await ask_gemini(interaction.channel_id, prompt)
    await send_embed_reply(interaction, f"✅ Décomposition : {tache[:200]}", reply, 0x3498DB)

@bot.tree.command(name="plan", description="Crée un plan de projet professionnel")
@app_commands.describe(projet="Description du projet", delai="Délai (ex: 2 semaines)")
async def cmd_plan(interaction: discord.Interaction, projet: str, delai: str = "Non défini"):
    await interaction.response.defer()
    prompt = (f"Crée un plan de projet pour : {projet} (délai : {delai})\n"
              f"Inclus : objectifs, phases, livrables, risques, KPIs")
    reply = await ask_gemini(interaction.channel_id, prompt)
    await send_embed_reply(interaction, f"📋 Plan de projet : {projet[:200]}", reply, 0x2ECC71)

@bot.tree.command(name="math", description="Résout des problèmes mathématiques")
@app_commands.describe(probleme="Le problème à résoudre")
async def cmd_math(interaction: discord.Interaction, probleme: str):
    await interaction.response.defer()
    prompt = f"Résous step by step : {probleme}\nDonne : démarche, réponse finale, vérification"
    reply = await ask_gemini(interaction.channel_id, prompt)
    await send_embed_reply(interaction, "🔢 Mathématiques", reply, 0xE67E22)

@bot.tree.command(name="corriger", description="Corrige et améliore un texte")
@app_commands.describe(texte="Le texte à corriger", style="Style (professionnel, académique...)")
async def cmd_corriger(interaction: discord.Interaction, texte: str, style: str = "professionnel"):
    await interaction.response.defer()
    prompt = f"Corrige et améliore en style {style} :\n\n{texte}\n\nDonne : texte corrigé + liste des corrections"
    reply = await ask_gemini(interaction.channel_id, prompt)
    await send_embed_reply(interaction, f"✍️ Correction (Style: {style})", reply, 0xE74C3C)

@bot.tree.command(name="clear", description="Efface l'historique du salon actuel")
async def cmd_clear(interaction: discord.Interaction):
    conversation_memory[interaction.channel_id].clear()
    await interaction.response.send_message("🗑️ Historique de ce salon effacé ! On repart de zéro.", ephemeral=True)

# ══════════════════════════════════════════════════════════════
#  COMMANDES WHATSAPP (Manuel & Planning)
# ══════════════════════════════════════════════════════════════

@bot.tree.command(name="whatsapp", description="Envoie un message WhatsApp depuis Discord")
@app_commands.describe(
    telephone="Numéro avec indicatif pays (ex: 221771234567)",
    message="Le message à envoyer"
)
async def cmd_whatsapp(interaction: discord.Interaction, telephone: str, message: str):
    await interaction.response.defer()
    try:
        result = await send_whatsapp(telephone, message)
        if "idMessage" in result:
            await interaction.followup.send(
                f"✅ **Message WhatsApp envoyé !**\n"
                f"📱 Destinataire : `{telephone}`\n"
                f"💬 Message : {message}"
            )
        else:
            await interaction.followup.send(f"❌ Erreur : {result}")
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur WhatsApp : {e}")

@bot.tree.command(name="wa_ia", description="Génère un message IA et l'envoie sur WhatsApp")
@app_commands.describe(
    telephone="Numéro avec indicatif (ex: 221771234567)",
    sujet="Sujet du message (ex: rappel réunion demain 10h, promo -20%...)"
)
async def cmd_wa_ia(interaction: discord.Interaction, telephone: str, sujet: str):
    await interaction.response.defer()
    prompt = (
        f"Rédige un message WhatsApp professionnel et naturel sur ce sujet : {sujet}\n\n"
        f"Court (max 3 lignes), chaleureux, direct. Juste le texte, rien d'autre."
    )
    message_genere = await ask_gemini(interaction.channel_id, prompt)
    try:
        result = await send_whatsapp(telephone, message_genere)
        if "idMessage" in result:
            await interaction.followup.send(
                f"🤖 **Message IA envoyé sur WhatsApp !**\n"
                f"📱 Destinataire : `{telephone}`\n\n"
                f"💬 **Message :**\n{message_genere}"
            )
        else:
            await interaction.followup.send(f"🤖 Message généré :\n{message_genere}\n\n❌ Erreur envoi : {result}")
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}")

@bot.tree.command(name="wa_broadcast", description="Envoie un message WhatsApp à plusieurs personnes")
@app_commands.describe(
    numeros="Numéros séparés par des virgules (ex: 221771234567,221781234567)",
    message="Le message à envoyer à tous"
)
async def cmd_wa_broadcast(interaction: discord.Interaction, numeros: str, message: str):
    await interaction.response.defer()
    liste = [n.strip() for n in numeros.split(",")]
    resultats = []
    for num in liste:
        try:
            result = await send_whatsapp(num, message)
            resultats.append(f"✅ `{num}`" if "idMessage" in result else f"❌ `{num}`")
            await asyncio.sleep(1)
        except Exception as e:
            resultats.append(f"❌ `{num}` — {e}")
    await interaction.followup.send(
        f"📢 **Broadcast terminé !**\n💬 *{message}*\n\n" + "\n".join(resultats)
    )

@bot.tree.command(name="wa_planning_add", description="Programme un envoi WhatsApp automatique")
@app_commands.describe(
    heure="Heure d'envoi (ex: 08:00)",
    numeros="Numéros séparés par virgules",
    message="Message à envoyer automatiquement"
)
async def cmd_planning_add(interaction: discord.Interaction, heure: str, numeros: str, message: str):
    global planning_counter
    await interaction.response.defer()
    try:
        h, m = heure.split(":")
        liste = [n.strip() for n in numeros.split(",")]
        planning_counter += 1
        pid = planning_counter
        label = f"Planning #{pid} à {heure}"

        # Ajouter au scheduler
        scheduler.add_job(
            execute_planned_message,
            "cron",
            hour=int(h),
            minute=int(m),
            args=[liste, message, label],
            id=f"plan_{pid}"
        )

        wa_planning.append({
            "id": pid, "heure": heure,
            "numeros": liste, "message": message
        })

        await interaction.followup.send(
            f"⏰ **Planning #{pid} ajouté !**\n"
            f"🕐 Heure : **{heure}** (tous les jours)\n"
            f"👥 Contacts : **{len(liste)}** numéros\n"
            f"💬 Message : *{message}*"
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}\nFormat heure : HH:MM (ex: 08:00)")

@bot.tree.command(name="wa_planning_list", description="Voir les messages programmés")
async def cmd_planning_list(interaction: discord.Interaction):
    if not wa_planning:
        await interaction.response.send_message("📭 Aucun message programmé.", ephemeral=True)
        return
    embed = discord.Embed(title="⏰ Messages WhatsApp programmés", color=0x25D366)
    for p in wa_planning:
        embed.add_field(
            name=f"#{p['id']} — {p['heure']} tous les jours",
            value=f"👥 {len(p['numeros'])} contacts\n💬 {p['message'][:80]}...",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="wa_planning_remove", description="Supprimer un message programmé")
@app_commands.describe(id_planning="L'ID du planning à supprimer")
async def cmd_planning_remove(interaction: discord.Interaction, id_planning: int):
    global wa_planning
    try:
        scheduler.remove_job(f"plan_{id_planning}")
        wa_planning = [p for p in wa_planning if p["id"] != id_planning]
        await interaction.response.send_message(f"🗑️ Planning #{id_planning} supprimé !")
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur : {e}")

@bot.tree.command(name="info", description="Affiche les commandes disponibles")
async def cmd_info(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"🤖 {BOT_NAME} — Agent IA + WhatsApp Automation",
        description=f"Propulsé par **Gemini 1.5 Flash** & Green API",
        color=0x5865F2
    )
    embed.add_field(name="💬 Conversation IA", value="`/ask` `/clear` `@mention`\n*📎 Tu peux joindre un fichier !*", inline=False)
    embed.add_field(name="💻 Code & Texte", value="`/code` `/debug` `/expliquer` `/traduire` `/resume` `/corriger`", inline=False)
    embed.add_field(name="🎯 Productivité", value="`/tache` `/plan` `/math`", inline=False)
    embed.add_field(name="📱 WhatsApp Manuel", value="`/whatsapp` `/wa_ia` `/wa_broadcast`", inline=False)
    embed.add_field(name="⏰ WhatsApp Auto", value="`/wa_planning_add` `/wa_planning_list` `/wa_planning_remove`\n`🤖 Bot SAV Auto` `📋 Webhook Formulaires`", inline=False)
    embed.set_footer(text=f"Modèle : {MODEL_NAME} | Mémoire : {MAX_HISTORY} messages")
    await interaction.response.send_message(embed=embed)

# ══════════════════════════════════════════════════════════════
#  LANCEMENT
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise ValueError("❌ DISCORD_TOKEN manquant dans .env !")
    if not GEMINI_API_KEY:
        raise ValueError("❌ GEMINI_API_KEY manquant dans .env !")
    print("🚀 Démarrage du bot...")
    bot.run(DISCORD_TOKEN)