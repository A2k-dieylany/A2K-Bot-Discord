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
import edge_tts
from datetime import datetime
import sqlite3
import io
import base64
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import re
try:
    import gspread
    from google.oauth2.service_account import Credentials as GCredentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

# ── Configuration ──────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BOT_NAME      = os.getenv("BOT_NAME", "MonBot")
MAX_HISTORY   = int(os.getenv("MAX_HISTORY", 20))
# Liste de modèles par ordre de préférence — rotation automatique si quota dépassé
MODELS_ROTATION = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
]
current_model_index = 0
MODEL_NAME = MODELS_ROTATION[0]

# ── WhatsApp (Green API) ───────────────────────────────────────
WA_ID_INSTANCE = os.getenv("WA_ID_INSTANCE")
WA_API_TOKEN   = os.getenv("WA_API_TOKEN")

# ── Canal Discord pour les logs WhatsApp ──────────────────────
WA_LOG_CHANNEL = int(os.getenv("WA_LOG_CHANNEL", "0"))

# ── Informations Business ──────────────────────────────────────
BUSINESS_NAME="Sen Digital Solution"
BUSINESS_INFO="Sen Digital Solution (SDS) est une agence experte en automatisation d'entreprises, intégration d'Intelligence Artificielle et développement d'écosystèmes web sur-mesure."
ADMIN_PHONE    = os.getenv("ADMIN_PHONE")

# ── Google Sheets CRM ──────────────────────────────────────────
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
gc = None
if GSPREAD_AVAILABLE and os.path.exists("google_credentials.json"):
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        credentials = GCredentials.from_service_account_file('google_credentials.json', scopes=scopes)
        gc = gspread.authorize(credentials)
        print("✅ Google Sheets CRM connecté avec succès !")
    except Exception as e:
        print(f"⚠️ Erreur de connexion à Google Sheets : {e}")

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
cursor.execute('''
    CREATE TABLE IF NOT EXISTS wa_settings (
        phone TEXT PRIMARY KEY,
        ai_paused BOOLEAN DEFAULT 0
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS wa_followups (
        phone TEXT PRIMARY KEY,
        last_bot_msg DATETIME,
        status TEXT DEFAULT 'pending'
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
3. Si le client demande à parler à un humain, rassure-le en lui disant que tu as notifié Dieylany et qu'il va prendre le relais. IMPORTANT : Ajoute le texte caché EXACTEMENT [ALERTE_HUMAIN] à la fin de ton message.
4. Si on te pose une question complexe ou hors de tes connaissances, explique avec tact que tu notes la question pour que Dieylany lui réponde avec précision.
5. Termine souvent tes réponses par une question simple pour encourager le client à détailler son besoin (ex: "Quel type de site avez-vous en tête ?").
6. Si le client semble très intéressé, prêt à passer commande, ou s'il demande formellement à parler à un humain/Dieylany, tu DOIS OBLIGATOIREMENT ajouter ce code secret tout à la fin de ta réponse : [ALERTE_PROSPECT]. Ce code me permettra de déclencher une alarme. Ne le mets pas pour les questions banales.
7. IMPORTANT : Si le client veut acheter un service (ex: payer 50000 FCFA), confirme d'abord avec lui. S'il est prêt à payer, insère EXACTEMENT la balise [LIEN_PAIEMENT_X] (où X est le prix en chiffres sans espaces, ex: [LIEN_PAIEMENT_50000]) à la fin de ta réponse. Dis-lui qu'un lien sécurisé (Wave/Orange Money) vient d'être généré ci-dessous.
8. IMPORTANT : Si le client veut prendre un rendez-vous (appel téléphonique, visio, etc.), propose-lui d'utiliser notre agenda. S'il est d'accord, insère EXACTEMENT la balise [LIEN_CALENDRIER] à la fin de ta réponse.
9. IMPORTANT : Si tu estimes que la discussion est totalement terminée de manière naturelle (ex: le client a dit au revoir, "merci c'est tout", ou a pris son RDV), insère EXACTEMENT la balise [FIN_DISCUSSION] à la fin de ta réponse. Cela permettra au bot de savoir qu'il ne doit plus relancer le client.
10. IMPORTANT : Si le client demande un devis formel OU si un service et son prix sont confirmés, insère la balise [DEVIS:NomDuService:Montant] (ex: [DEVIS:Site Vitrine Premium:150000]) à la fin de ta réponse. Je génèrerai un beau devis PDF professionnel et l'enverrai directement sur WhatsApp.
11. NOUVEAU POUVOIR : Tu peux envoyer des NOTES VOCALES. Si tu estimes qu'une note vocale serait plus chaleureuse, ajoute EXACTEMENT la balise [VOCAL] à la fin de ton texte. 
    ATTENTION : Si tu utilises [VOCAL], ton texte DOIT être écrit pour être PRONONCÉ à l'oral. N'utilise AUCUNE liste à puces, pas de tirets, pas de structure complexe. Écris comme tu parles, avec de courtes phrases. Pas d'émojis dans le texte si c'est un vocal.
"""

def get_active_model(system_instruction: str = None):
    """Retourne un modèle Gemini actif. Fait une rotation si quota dépassé."""
    return genai.GenerativeModel(
        model_name=MODELS_ROTATION[current_model_index],
        system_instruction=system_instruction
    )

# ══════════════════════════════════════════════════════════════
#  GÉNÉRATION DE DEVIS PDF PROFESSIONNEL
# ══════════════════════════════════════════════════════════════

def generate_devis_pdf(client_phone: str, service: str, montant: str, client_name: str = "Client") -> bytes:
    """Génère un devis PDF professionnel aux couleurs de Sen Digital Solution."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    
    styles = getSampleStyleSheet()
    
    # Couleurs SDS
    DARK_BG   = colors.HexColor('#0A0E1A')
    ACCENT    = colors.HexColor('#6C63FF')
    GOLD      = colors.HexColor('#FFD700')
    LIGHT_TXT = colors.HexColor('#CCCCCC')
    WHITE     = colors.white
    
    title_style = ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=22, textColor=WHITE, alignment=TA_CENTER, spaceAfter=6)
    sub_style   = ParagraphStyle('sub', fontName='Helvetica', fontSize=11, textColor=LIGHT_TXT, alignment=TA_CENTER, spaceAfter=4)
    label_style = ParagraphStyle('label', fontName='Helvetica-Bold', fontSize=10, textColor=ACCENT)
    value_style = ParagraphStyle('value', fontName='Helvetica', fontSize=10, textColor=colors.black)
    footer_style= ParagraphStyle('footer', fontName='Helvetica-Oblique', fontSize=8, textColor=LIGHT_TXT, alignment=TA_CENTER)
    
    now = datetime.now()
    devis_num = f"SDS-{now.strftime('%Y%m%d')}-{client_phone[-4:]}"
    
    story = []
    
    # En-tête colorée
    header_data = [[
        Paragraph("<b>SEN DIGITAL SOLUTION</b>", title_style),
    ]]
    header_table = Table(header_data, colWidths=[17*cm])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), DARK_BG),
        ('TOPPADDING', (0,0), (-1,-1), 18),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('ROUNDEDCORNERS', [8]),
    ]))
    story.append(header_table)
    
    # Sous-titre
    sub_data = [[
        Paragraph("Agence IA & Automatisation | sendigitalsolution.com", sub_style),
    ]]
    sub_table = Table(sub_data, colWidths=[17*cm])
    sub_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), DARK_BG),
        ('BOTTOMPADDING', (0,0), (-1,-1), 18),
    ]))
    story.append(sub_table)
    story.append(Spacer(1, 0.5*cm))
    
    # Titre DEVIS
    story.append(Paragraph(f"<font color='#{ACCENT.hexval()[2:]}'>DEVIS N°</font> {devis_num}", ParagraphStyle('dnum', fontName='Helvetica-Bold', fontSize=16, alignment=TA_LEFT, spaceAfter=4)))
    story.append(Paragraph(f"Date : {now.strftime('%d/%m/%Y')} | Valable 30 jours", ParagraphStyle('date', fontName='Helvetica', fontSize=9, textColor=colors.grey, spaceAfter=12)))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT))
    story.append(Spacer(1, 0.4*cm))
    
    # Informations client
    client_data = [
        [Paragraph("CLIENT", label_style), Paragraph("AGENCE", label_style)],
        [Paragraph(client_name, value_style), Paragraph("Sen Digital Solution", value_style)],
        [Paragraph(f"WhatsApp : +{client_phone}", value_style), Paragraph("sendigitalsolution@gmail.com", value_style)],
        [Paragraph("", value_style), Paragraph("Dakar, Sénégal", value_style)],
    ]
    client_table = Table(client_data, colWidths=[8.5*cm, 8.5*cm])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), colors.HexColor('#F0EEFF')),
        ('FONTNAME', (0,0), (1,0), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,0), (1,0), ACCENT),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 0.6*cm))
    
    # Détail de la prestation
    story.append(Paragraph("DÉTAIL DE LA PRESTATION", label_style))
    story.append(Spacer(1, 0.2*cm))
    
    montant_int = int(montant.replace(' ', '').replace(',',''))
    tva = 0  # Pas de TVA (Afrique de l'Ouest adapté)
    
    items_data = [
        [Paragraph("<b>Description</b>", ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=10, textColor=WHITE)),
         Paragraph("<b>Qté</b>", ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=10, textColor=WHITE, alignment=TA_CENTER)),
         Paragraph("<b>Prix unitaire</b>", ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=10, textColor=WHITE, alignment=TA_RIGHT)),
         Paragraph("<b>Total</b>", ParagraphStyle('th', fontName='Helvetica-Bold', fontSize=10, textColor=WHITE, alignment=TA_RIGHT))],
        [Paragraph(service, value_style),
         Paragraph("1", ParagraphStyle('v', fontName='Helvetica', fontSize=10, alignment=TA_CENTER)),
         Paragraph(f"{montant_int:,} FCFA".replace(',', ' '), ParagraphStyle('v', fontName='Helvetica', fontSize=10, alignment=TA_RIGHT)),
         Paragraph(f"{montant_int:,} FCFA".replace(',', ' '), ParagraphStyle('v', fontName='Helvetica', fontSize=10, alignment=TA_RIGHT))],
        [Paragraph("<i>✓ Hébergement + Nom de domaine offerts (1 an)</i>", ParagraphStyle('incl', fontName='Helvetica-Oblique', fontSize=8, textColor=colors.HexColor('#27AE60'))),
         Paragraph("", value_style), Paragraph("", value_style), Paragraph("", value_style)],
        [Paragraph("<i>✓ 3 mois de maintenance gratuite post-livraison</i>", ParagraphStyle('incl', fontName='Helvetica-Oblique', fontSize=8, textColor=colors.HexColor('#27AE60'))),
         Paragraph("", value_style), Paragraph("", value_style), Paragraph("", value_style)],
    ]
    items_table = Table(items_data, colWidths=[9*cm, 2*cm, 3*cm, 3*cm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), ACCENT),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#F9F9F9')),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 0.3*cm))
    
    # Total
    total_data = [
        [Paragraph("Sous-total", value_style), Paragraph(f"{montant_int:,} FCFA".replace(',', ' '), ParagraphStyle('r', fontName='Helvetica', fontSize=10, alignment=TA_RIGHT))],
        [Paragraph("Acompte (50%)", ParagraphStyle('acc', fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#E74C3C'))),
         Paragraph(f"{montant_int//2:,} FCFA".replace(',', ' '), ParagraphStyle('r', fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#E74C3C'), alignment=TA_RIGHT))],
        [Paragraph("<b>TOTAL TTC</b>", ParagraphStyle('tot', fontName='Helvetica-Bold', fontSize=12, textColor=WHITE)),
         Paragraph(f"<b>{montant_int:,} FCFA</b>".replace(',', ' '), ParagraphStyle('r', fontName='Helvetica-Bold', fontSize=12, textColor=WHITE, alignment=TA_RIGHT))],
    ]
    total_table = Table(total_data, colWidths=[13*cm, 4*cm])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0,2), (-1,2), ACCENT),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 0.8*cm))
    
    # Moyens de paiement
    story.append(Paragraph("<b>Moyens de paiement acceptés :</b> Wave 🌊 • Orange Money 🟠 • Virement bancaire • PayPal", ParagraphStyle('pay', fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#555555'))))
    story.append(Spacer(1, 0.8*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E0E0E0')))
    story.append(Spacer(1, 0.3*cm))
    
    # Pied de page
    story.append(Paragraph("Merci de votre confiance ❤️ | Sen Digital Solution — Votre partenaire en transformation digitale & IA", footer_style))
    story.append(Paragraph("Ce devis a été généré automatiquement par Max, l'assistant IA de Sen Digital Solution.", footer_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.read()

async def send_whatsapp_file(phone: str, file_bytes: bytes, filename: str, caption: str = ""):
    """Envoie un fichier (PDF, image...) sur WhatsApp via Green API."""
    phone = str(phone).replace("+", "").replace(" ", "").replace("-", "")
    chat_id = f"{phone}@c.us"
    url = f"https://api.green-api.com/waInstance{WA_ID_INSTANCE}/sendFileByUpload/{WA_API_TOKEN}"
    
    form = aiohttp.FormData()
    form.add_field('chatId', chat_id)
    form.add_field('caption', caption)
    form.add_field('fileName', filename)
    form.add_field('file', file_bytes, filename=filename, content_type='application/pdf')
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=form) as resp:
            result = await resp.json()
            print(f"📎 Envoi fichier WA → {phone} | Statut: {resp.status} | {result}")
            return result

# ══════════════════════════════════════════════════════════════
#  IA VOCALE (Text-to-Speech)
# ══════════════════════════════════════════════════════════════

def clean_text_for_voice(text: str) -> str:
    """Nettoie le texte avant synthèse vocale (enlève markdown, emojis et URLs complexes)."""
    import re
    # Supprime le markdown basique (*, _, #)
    text = re.sub(r'[*_#]', '', text)
    # Supprime les emojis
    text = re.sub(r'[^\w\s,.:;!?\'"éèêëàâäôöûüç%-]', ' ', text)
    # Réduit les espaces multiples
    text = re.sub(r'\s+', ' ', text).strip()
    return text

async def generate_voice(text: str) -> bytes:
    """Génère un fichier audio (Ogg) à partir du texte avec Edge TTS."""
    clean_text = clean_text_for_voice(text)
    # Voix féminine premium française
    communicate = edge_tts.Communicate(clean_text, "fr-FR-DeniseNeural")
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data

async def send_whatsapp_voice(phone: str, file_bytes: bytes):
    """Envoie un fichier audio en tant que NOTE VOCALE sur WhatsApp."""
    phone = str(phone).replace("+", "").replace(" ", "").replace("-", "")
    chat_id = f"{phone}@c.us"
    url = f"https://api.green-api.com/waInstance{WA_ID_INSTANCE}/sendFileByUpload/{WA_API_TOKEN}"
    
    form = aiohttp.FormData()
    form.add_field('chatId', chat_id)
    form.add_field('fileName', 'voice_message.ogg')
    # Pour qu'il s'affiche comme un vrai vocal (PTT), on utilise audio/ogg
    form.add_field('file', file_bytes, filename='voice_message.ogg', content_type='audio/ogg')
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=form) as resp:
            result = await resp.json()
            print(f"🎙️ Envoi vocal WA → {phone} | Statut: {resp.status} | {result}")
            return result

async def gemini_generate(prompt_or_contents, system_instruction: str = None, is_wa: bool = False) -> str:
    """Génère du contenu avec rotation automatique des modèles en cas de quota 429."""
    global current_model_index
    
    for attempt in range(len(MODELS_ROTATION)):
        idx = (current_model_index + attempt) % len(MODELS_ROTATION)
        model_name = MODELS_ROTATION[idx]
        try:
            active_model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction
            )
            if isinstance(prompt_or_contents, str):
                response = await active_model.generate_content_async(prompt_or_contents)
            else:
                response = await active_model.generate_content_async(
                    prompt_or_contents,
                    generation_config=genai.types.GenerationConfig(temperature=0.7, max_output_tokens=1000)
                )
            if idx != current_model_index:
                print(f"🔄 Modèle actif changé → {model_name}")
                current_model_index = idx
            return response.text
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e):
                print(f"⚠️ Quota dépassé sur {model_name}, tentative avec le prochain modèle...")
                continue
            raise e
    
    return "⏳ Tous les modèles IA ont atteint leur quota. Réessaie dans quelques minutes."

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
        reply = await gemini_generate(contents, system_instruction=SYSTEM_PROMPT)
        add_to_memory(session_id, "assistant", reply)
        return reply
    except Exception as e:
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
#  GOOGLE SHEETS CRM SYNC
# ══════════════════════════════════════════════════════════════

def sync_lead_to_crm(phone: str, name: str, status: str, details: str = ""):
    """Ajoute ou met à jour un prospect dans le Google Sheet CRM."""
    if not gc or not GOOGLE_SHEET_ID:
        return
    
    try:
        sheet = gc.open_by_key(GOOGLE_SHEET_ID).sheet1
        records = sheet.get_all_records()
        
        # Trouver si le numéro existe déjà
        row_idx = None
        for i, row in enumerate(records):
            if str(row.get("Téléphone", "")).replace("+", "") == str(phone).replace("+", ""):
                row_idx = i + 2  # +2 car index 0 est la ligne 2 du sheet (ligne 1 = header)
                break
                
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if row_idx:
            # Mise à jour
            sheet.update(f"C{row_idx}:E{row_idx}", [[status, details, now_str]])
        else:
            # Création, avec l'en-tête attendu : Nom | Téléphone | Statut | Détails | Dernière interaction
            # S'il n'y a pas d'en-tête, on le crée (basique)
            if not records and len(sheet.row_values(1)) == 0:
                sheet.append_row(["Nom", "Téléphone", "Statut", "Détails", "Dernière interaction"])
                
            sheet.append_row([name, f"+{phone}", status, details, now_str])
            
    except Exception as e:
        print(f"⚠️ Erreur de synchro CRM Google Sheets : {e}")

# ══════════════════════════════════════════════════════════════

async def send_whatsapp(phone: str, message: str) -> dict:
    phone = str(phone).replace("+", "").replace(" ", "").replace("-", "")
    chat_id = f"{phone}@c.us"
    url = f"https://api.green-api.com/waInstance{WA_ID_INSTANCE}/sendMessage/{WA_API_TOKEN}"
    body = {"chatId": chat_id, "message": message}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body) as resp:
            result = await resp.json()
            print(f"📤 Envoi WA → {phone} | Statut: {resp.status} | Réponse: {result}")
            return result


def add_to_wa_memory(phone: str, role: str, content: str):
    cursor.execute("INSERT INTO wa_memory (phone, role, content) VALUES (?, ?, ?)", (phone, role, content))
    conn.commit()

def get_wa_memory(phone: str, limit: int = 10) -> list:
    # Récupérer les X derniers messages triés par date décroissante, puis les remettre dans l'ordre chronologique
    cursor.execute("SELECT role, content FROM (SELECT role, content, timestamp FROM wa_memory WHERE phone = ? ORDER BY timestamp DESC LIMIT ?) ORDER BY timestamp ASC", (phone, limit))
    return [{"role": r[0], "content": r[1]} for r in cursor.fetchall()]

async def ask_gemini_wa(phone: str, user_message: str, media_part=None) -> str:
    if user_message:
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
        reply = await gemini_generate(contents, system_instruction=SAV_PROMPT, is_wa=True)
        add_to_wa_memory(phone, "assistant", reply)
        return reply
    except Exception as e:
        print(f"🔴 Erreur inattendue ask_gemini_wa : {e}")
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
                        
                        # Ajouter le message utilisateur à la mémoire AVANT la vérification de pause
                        add_to_wa_memory(phone, "user", text)
                        
                        # Mettre à jour le statut de relance (le client a répondu)
                        cursor.execute("""
                            INSERT INTO wa_followups (phone, status) 
                            VALUES (?, 'replied')
                            ON CONFLICT(phone) DO UPDATE SET status = 'replied'
                        """, (phone,))
                        conn.commit()

                        # Vérifier si l'IA est en pause pour ce client
                        cursor.execute("SELECT ai_paused FROM wa_settings WHERE phone = ?", (phone,))
                        row = cursor.fetchone()
                        
                        if row and row[0]:
                            print(f"⏸️ IA en pause pour {phone}. Message stocké mais ignoré par Max.")
                        else:
                            # Générer réponse IA (ask_gemini_wa ne doit plus ajouter le user_message puisqu'on l'a déjà fait)
                            reply = await ask_gemini_wa(phone, "", media_part)
                            
                            # Détection de fin de discussion
                            is_finished = False
                            if "[FIN_DISCUSSION]" in reply:
                                is_finished = True
                                reply = reply.replace("[FIN_DISCUSSION]", "").strip()
                                
                            # Enregistrer le statut de relance pour ce client
                            new_status = 'finished' if is_finished else 'pending'
                            cursor.execute("""
                                INSERT INTO wa_followups (phone, last_bot_msg, status) 
                                VALUES (?, CURRENT_TIMESTAMP, ?)
                                ON CONFLICT(phone) DO UPDATE SET last_bot_msg = CURRENT_TIMESTAMP, status = ?
                            """, (phone, new_status, new_status))
                            conn.commit()
                            
                            # Détection prospect chaud
                            is_hot = False
                            needs_human = False
                            if "[ALERTE_PROSPECT]" in reply:
                                is_hot = True
                                reply = reply.replace("[ALERTE_PROSPECT]", "").strip()
                            if "[ALERTE_HUMAIN]" in reply:
                                needs_human = True
                                reply = reply.replace("[ALERTE_HUMAIN]", "").strip()
                                
                            # Synchronisation CRM
                            crm_status = "En cours"
                            if is_finished:
                                crm_status = "Terminé"
                            elif is_hot:
                                crm_status = "🔥 Prospect Chaud"
                            elif needs_human:
                                crm_status = "⚠️ Demande Humain"
                                
                            sync_lead_to_crm(phone, name, crm_status, "A échangé avec Max.")
                                
                            # Interception de la balise de paiement
                            import re
                            payment_match = re.search(r'\[LIEN_PAIEMENT_(\d+)\]', reply)
                            if payment_match:
                                amount = payment_match.group(1)
                                payment_link = f"http://localhost:8080/pay?amount={amount}&phone={phone.replace('+', '')}"
                                reply = reply.replace(payment_match.group(0), f"\n\n👉 *Lien de paiement sécurisé* ({amount} FCFA) : {payment_link}").strip()
                                
                            # Interception de la balise calendrier
                            if "[LIEN_CALENDRIER]" in reply or "[LIEN_CALENDLY]" in reply:
                                calendar_link = "https://calendly.com/sendigitalsolution"
                                reply = reply.replace("[LIEN_CALENDRIER]", f"\n\n📅 *Prendre Rendez-vous avec Dieylany* : {calendar_link}")
                                reply = reply.replace("[LIEN_CALENDLY]", f"\n\n📅 *Prendre Rendez-vous avec Dieylany* : {calendar_link}")
                                reply = reply.strip()
                            
                            # Interception de la balise [DEVIS:Service:Montant]
                            import re as _re
                            devis_match = _re.search(r'\[DEVIS:([^:]+):(\d+)\]', reply)
                            if devis_match:
                                devis_service = devis_match.group(1).strip()
                                devis_montant = devis_match.group(2).strip()
                                reply = reply.replace(devis_match.group(0), "").strip()
                                
                                try:
                                    pdf_bytes = generate_devis_pdf(
                                        client_phone=phone,
                                        service=devis_service,
                                        montant=devis_montant,
                                        client_name=name
                                    )
                                    filename = f"Devis_SDS_{datetime.now().strftime('%Y%m%d')}_{phone[-4:]}.pdf"
                                    caption = f"📄 Voici votre devis pour *{devis_service}* — {int(devis_montant):,} FCFA".replace(',', ' ')
                                    await send_whatsapp_file(phone, pdf_bytes, filename, caption)
                                    print(f"📎 Devis PDF généré et envoyé à {phone} ({devis_service} — {devis_montant} FCFA)")
                                    sync_lead_to_crm(phone, name, "Devis Envoyé", f"Devis: {devis_service} ({devis_montant} CFA)")
                                    
                                    if WA_LOG_CHANNEL:
                                        channel = bot.get_channel(WA_LOG_CHANNEL)
                                        if channel:
                                            await channel.send(f"📄 **Devis PDF envoyé !**\n👤 Client : `{name}` (+{phone})\n🛒 Service : {devis_service}\n💰 Montant : {int(devis_montant):,} FCFA".replace(',', ' '))
                                except Exception as pdf_err:
                                    print(f"⚠️ Erreur génération PDF : {pdf_err}")

                            # Interception de la balise VOCAL
                            is_vocal = False
                            if "[VOCAL]" in reply:
                                is_vocal = True
                                reply = reply.replace("[VOCAL]", "").strip()

                            # Délai artificiel pour humaniser Max (simule le temps de frappe)
                            delay = max(2.0, min(6.0, len(reply) * 0.04))
                            await asyncio.sleep(delay)
                            
                            # Envoyer la réponse sur WhatsApp
                            if is_vocal and reply:
                                try:
                                    print("🎙️ Génération de la note vocale en cours...")
                                    audio_bytes = await generate_voice(reply)
                                    await send_whatsapp_voice(phone, audio_bytes)
                                except Exception as e:
                                    print(f"⚠️ Erreur génération/envoi vocal : {e}")
                                    await send_whatsapp(phone, reply) # Fallback en texte
                            elif reply:
                                await send_whatsapp(phone, reply)
                            
                            # Logger sur Discord
                            if WA_LOG_CHANNEL:
                                channel = bot.get_channel(WA_LOG_CHANNEL)
                                if channel:
                                    embed = discord.Embed(
                                        title="🔥 PROSPECT CHAUD ! Action requise" if is_hot else ("🗣️ Demande d'Humain" if needs_human else "📱 Nouveau message WhatsApp"),
                                        color=0xFF4500 if is_hot else (0xF59E0B if needs_human else 0x25D366)
                                    )
                                    embed.add_field(name="👤 De", value=f"{name} (`{phone}`)", inline=False)
                                    embed.add_field(name="💬 Message client", value=text if text else "(Fichier/Image envoyé)", inline=False)
                                    embed.add_field(name="🤖 Réponse Max", value=reply, inline=False)
                                    embed.timestamp = datetime.now()
                                    content = "@everyone 🚨 **Dieylany, un prospect t'attend sur WhatsApp !**" if (is_hot or needs_human) else None
                                    await channel.send(content=content, embed=embed)
                                    
                            # Notifier sur WhatsApp Perso si urgent
                            if (is_hot or needs_human) and ADMIN_PHONE:
                                type_alerte = "PROSPECT CHAUD" if is_hot else "DEMANDE D'HUMAIN"
                                admin_msg = f"🚨 *ALERTE {type_alerte}* 🚨\n\n👤 Client : +{phone}\n💬 Il a dit : {text}\n🤖 Max : {reply}\n\nVa vite sur le dashboard ou réponds depuis ton WhatsApp professionnel !"
                                await send_whatsapp(ADMIN_PHONE, admin_msg)

                    # Supprimer la notification traitée
                    async with session.delete(f"{delete_url}/{receipt_id}") as _:
                        pass

            except Exception as e:
                print(f"⚠️ Erreur polling WA : {e}")

            await asyncio.sleep(5)

# ══════════════════════════════════════════════════════════════
#  WHATSAPP — Planification & Webhook & Rapports
# ══════════════════════════════════════════════════════════════

async def generate_and_send_report():
    """Génère un rapport hebdo des statistiques et l'envoie sur Discord et WhatsApp perso."""
    try:
        cursor.execute("SELECT COUNT(DISTINCT phone) FROM wa_memory WHERE role = 'user'")
        total_clients = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM wa_memory")
        total_messages = cursor.fetchone()[0] or 0
        
        report_text = (
            f"📊 *RAPPORT HEBDOMADAIRE - {BUSINESS_NAME}* 📊\n\n"
            f"👥 *Nouveaux Contacts :* {total_clients}\n"
            f"💬 *Messages Échangés :* {total_messages}\n\n"
            f"💡 Ton assistant Max a géré tout ça pendant que tu te concentrais sur ton business. Bon week-end boss ! 🚀"
        )
        
        # Envoi Discord
        if WA_LOG_CHANNEL:
            channel = bot.get_channel(WA_LOG_CHANNEL)
            if channel:
                await channel.send(f"📈 **Rapport Hebdomadaire Généré**\n\n{report_text}")
                
        # Envoi WhatsApp perso
        if ADMIN_PHONE:
            await send_whatsapp(ADMIN_PHONE, report_text)
            print(f"✅ Rapport hebdo envoyé à l'admin ({ADMIN_PHONE})")
    except Exception as e:
        print(f"⚠️ Erreur lors de la génération du rapport : {e}")

@bot.tree.command(name="wa_rapport", description="Génère et t'envoie le rapport de stats sur WhatsApp instantanément")
async def cmd_wa_rapport(interaction: discord.Interaction):
    await interaction.response.send_message("📊 Génération du rapport en cours... Vérifie ton WhatsApp !", ephemeral=True)
    await generate_and_send_report()

async def check_and_send_followups(force=False):
    """Vérifie toutes les 30 minutes s'il faut relancer des clients après 48h de silence."""
    try:
        # Chercher ceux en 'pending'
        query = "SELECT phone FROM wa_followups WHERE status = 'pending'"
        if not force:
            query += " AND last_bot_msg <= datetime('now', '-48 hours')"
            
        cursor.execute(query)
        rows = cursor.fetchall()
        for r in rows:
            phone = r[0]
            
            # Récupérer l'historique pour donner du contexte à l'IA
            history = get_wa_memory(phone, limit=5)
            prompt = f"Tu es Max, l'assistant de {BUSINESS_NAME}. Le prospect au numéro {phone} n'a pas répondu à ton dernier message depuis 48h. Voici les derniers échanges :\n"
            for msg in history:
                prompt += f"{'Client' if msg['role'] == 'user' else 'Max'}: {msg['content']}\n"
            prompt += "\nObjectif : Rédige un SEUL petit message WhatsApp très court et ultra-naturel (1 à 2 phrases max) pour le relancer en douceur, montrer qu'on est disponible et ré-engager la conversation. Ne donne pas l'impression d'être un robot."
            
            response = await wa_model.generate_content_async(prompt)
            followup_msg = response.text.strip()
            
            # Marquer comme relancé pour ne plus le spammer
            cursor.execute("UPDATE wa_followups SET status = 'followed_up', last_bot_msg = CURRENT_TIMESTAMP WHERE phone = ?", (phone,))
            conn.commit()
            
            # Envoyer le message
            await send_whatsapp(phone, followup_msg)
            add_to_wa_memory(phone, "assistant", followup_msg)
            
            # Notifier l'admin
            if WA_LOG_CHANNEL:
                channel = bot.get_channel(WA_LOG_CHANNEL)
                if channel:
                    await channel.send(f"⏰ **Drip Marketing (Automatique)** : Max vient de relancer `+{phone}` après 48h de silence !\n*Message envoyé :* {followup_msg}")
                    
    except Exception as e:
        print(f"⚠️ Erreur lors des relances automatiques : {e}")

@bot.tree.command(name="wa_force_relance", description="[Admin] Force la vérification immédiate des relances Drip Marketing")
async def cmd_wa_force_relance(interaction: discord.Interaction):
    await interaction.response.send_message("🔍 Lancement forcé de la relance (ignore la limite des 48h)...", ephemeral=True)
    await check_and_send_followups(force=True)

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

# ── Webhook HTTP & Dashboard ───────────────────────────────────

async def show_dashboard(request):
    """Affiche une page HTML avec l'historique des conversations SQLite."""
    import json
    import os
    
    cursor.execute('''
        SELECT phone, role, content, timestamp 
        FROM wa_memory 
        ORDER BY timestamp DESC 
        LIMIT 300
    ''')
    rows = cursor.fetchall()
    
    cursor.execute('SELECT phone, ai_paused FROM wa_settings')
    settings = {row[0]: bool(row[1]) for row in cursor.fetchall()}
    
    # Organiser les messages par numéro de téléphone
    conversations = {}
    for r in rows:
        phone, role, content, timestamp = r
        if phone not in conversations:
            conversations[phone] = []
        conversations[phone].append({'role': role, 'content': content, 'timestamp': timestamp})
        
    data_to_inject = {}
    for phone, msgs in conversations.items():
        data_to_inject[phone] = {
            "messages": msgs,
            "ai_paused": settings.get(phone, False)
        }
        
    try:
        with open("dashboard.html", "r", encoding="utf-8") as f:
            html_template = f.read()
    except FileNotFoundError:
        return web.Response(text="Erreur : le fichier dashboard.html est introuvable.", status=500)
        
    # Injecter les données JSON dans le HTML de manière sécurisée
    html = html_template.replace("__DATA_JSON__", json.dumps(data_to_inject))
    
    return web.Response(text=html, content_type='text/html')

async def export_contacts(request: web.Request) -> web.Response:
    """Endpoint pour exporter tous les numéros en CSV pour le marketing."""
    cursor.execute("SELECT DISTINCT phone FROM wa_memory")
    rows = cursor.fetchall()
    
    csv_content = "Telephone\n"
    for r in rows:
        csv_content += f"{r[0]}\n"
        
    return web.Response(
        text=csv_content,
        content_type='text/csv',
        headers={"Content-Disposition": "attachment; filename=clients_whatsapp.csv"}
    )

async def toggle_ai(request: web.Request) -> web.Response:
    """Active ou désactive l'IA pour un numéro donné."""
    try:
        data = await request.json()
        phone = data.get("phone")
        if not phone: return web.json_response({"error": "phone requis"}, status=400)
        
        cursor.execute("SELECT ai_paused FROM wa_settings WHERE phone = ?", (phone,))
        row = cursor.fetchone()
        new_status = not row[0] if row else True
        
        cursor.execute("INSERT OR REPLACE INTO wa_settings (phone, ai_paused) VALUES (?, ?)", (phone, new_status))
        conn.commit()
        return web.json_response({"success": True, "ai_paused": new_status})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def send_manual(request: web.Request) -> web.Response:
    """Envoie un message WhatsApp depuis le Dashboard en tant qu'humain."""
    try:
        data = await request.json()
        phone = data.get("phone")
        message = data.get("message")
        if not phone or not message: return web.json_response({"error": "Données invalides"}, status=400)
        
        # Envoi WhatsApp
        await send_whatsapp(phone, message)
        
        # Sauvegarde en base
        add_to_wa_memory(phone, "assistant", message)
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def show_payment_page(request: web.Request) -> web.Response:
    """Affiche une fausse page de paiement pour la démo Wave/Orange Money."""
    amount = request.query.get("amount", "0")
    phone = request.query.get("phone", "Inconnu")
    
    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Paiement Sécurisé - A2K</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f3f4f6; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            .card {{ background: white; padding: 30px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); width: 100%; max-width: 400px; text-align: center; }}
            h2 {{ color: #1f2937; margin-bottom: 10px; font-size: 22px; }}
            .amount {{ font-size: 36px; font-weight: bold; color: #10b981; margin: 20px 0; }}
            .btn-wave {{ background: #1da1f2; color: white; border: none; padding: 15px; width: 100%; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; margin-bottom: 15px; transition: 0.2s; }}
            .btn-wave:hover {{ background: #0c85d0; }}
            .btn-orange {{ background: #ff7900; color: white; border: none; padding: 15px; width: 100%; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; transition: 0.2s; }}
            .btn-orange:hover {{ background: #e66d00; }}
            .footer {{ margin-top: 20px; font-size: 12px; color: #9ca3af; }}
        </style>
    </head>
    <body>
        <div class="card" id="payment-card">
            <h2>🛍️ Finalisez votre Commande</h2>
            <p style="color: #6b7280; font-size: 14px;">Destinataire : <strong>A2K Agency</strong></p>
            <div class="amount">{amount} FCFA</div>
            <button class="btn-wave" onclick="pay('Wave')">Payer avec Wave 🌊</button>
            <button class="btn-orange" onclick="pay('Orange Money')">Payer avec Orange Money 🟠</button>
            <div class="footer">🔒 Paiement 100% sécurisé</div>
        </div>
        <script>
            function pay(method) {{
                const card = document.getElementById('payment-card');
                card.innerHTML = "<h2>⏳ Traitement en cours...</h2><p>Veuillez valider sur votre téléphone.</p>";
                
                // Simulation du délai de validation
                setTimeout(() => {{
                    fetch('/process_payment', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{phone: '{phone}', amount: '{amount}', method: method}})
                    }}).then(() => {{
                        card.innerHTML = "<h2>✅ Paiement Réussi !</h2><p style='color: #10b981;'>Merci de votre confiance.</p><p style='font-size:14px; color:#6b7280;'>Un reçu vous a été envoyé sur WhatsApp.</p>";
                    }});
                }}, 2000);
            }}
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def process_payment(request: web.Request) -> web.Response:
    """Endpoint appelé quand le client valide le paiement sur la page web."""
    try:
        data = await request.json()
        phone = data.get("phone")
        amount = data.get("amount")
        method = data.get("method")
        
        # Le bot reprend la parole pour confirmer
        message = f"✅ *Confirmation de Paiement*\n\nSuper ! Nous avons bien reçu votre paiement de *{amount} FCFA* via {method}. 🎉\n\nL'équipe A2K prend en charge votre projet immédiatement !"
        
        # On désactive la pause si l'humain avait pris le relais, car c'est une notification auto
        cursor.execute("UPDATE wa_settings SET ai_paused = 0 WHERE phone = ?", (phone,))
        conn.commit()
        
        await send_whatsapp(phone, message)
        add_to_wa_memory(phone, "assistant", message)
        
        # Notifier l'équipe sur Discord
        if WA_LOG_CHANNEL:
            channel = bot.get_channel(WA_LOG_CHANNEL)
            if channel:
                embed = discord.Embed(title="💸 NOUVEAU PAIEMENT REÇU !", color=0x10B981)
                embed.add_field(name="📱 Client", value=f"+{phone}", inline=True)
                embed.add_field(name="💰 Montant", value=f"{amount} FCFA", inline=True)
                embed.add_field(name="💳 Moyen", value=method, inline=True)
                await channel.send("@everyone 💸 **Cha-Ching !**", embed=embed)
                
        # Notifier sur WhatsApp perso
        if ADMIN_PHONE:
            admin_msg = f"💸 *NOUVEAU PAIEMENT !* 💸\n\n👤 Client : +{phone}\n💰 Montant : {amount} FCFA\n💳 Moyen : {method}"
            await send_whatsapp(ADMIN_PHONE, admin_msg)
                
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def show_calendar_page(request: web.Request) -> web.Response:
    """Affiche une interface de prise de rendez-vous interactive."""
    phone = request.query.get("phone", "")
    
    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Prendre Rendez-vous - A2K</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f3f4f6; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
            .card {{ background: white; padding: 30px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); width: 100%; max-width: 450px; }}
            h2 {{ color: #1f2937; margin-top: 0; font-size: 24px; }}
            h3 {{ font-size: 16px; color: #4b5563; margin-top: 25px; margin-bottom: 10px; border-bottom: 2px solid #e5e7eb; padding-bottom: 5px; }}
            .date-grid, .time-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
            .btn {{ padding: 12px 5px; border: 2px solid #e5e7eb; background: white; border-radius: 10px; cursor: pointer; transition: 0.2s; text-align: center; font-weight: 600; font-size: 14px; color: #374151; }}
            .btn:hover {{ border-color: #3b82f6; color: #3b82f6; background: #eff6ff; }}
            .btn.selected {{ background: #3b82f6; color: white; border-color: #3b82f6; }}
            .submit-btn {{ background: #10b981; color: white; border: none; padding: 16px; width: 100%; border-radius: 10px; font-size: 16px; font-weight: bold; cursor: pointer; transition: 0.2s; margin-top: 30px; }}
            .submit-btn:hover {{ background: #059669; transform: translateY(-2px); }}
            .submit-btn:disabled {{ background: #d1d5db; cursor: not-allowed; transform: none; }}
        </style>
    </head>
    <body>
        <div class="card" id="calendar-card">
            <h2>📅 Planifier un Appel</h2>
            <p style="color: #6b7280; font-size: 15px; margin-bottom: 20px;">Choisissez une date et une heure pour discuter de votre projet avec Dieylany.</p>
            
            <h3>1. Choisissez une Date</h3>
            <div class="date-grid" id="dates"></div>
            
            <h3>2. Choisissez une Heure</h3>
            <div class="time-grid" id="times">
                <button class="btn time-btn" onclick="selectTime(this, '10:00')">10:00</button>
                <button class="btn time-btn" onclick="selectTime(this, '14:00')">14:00</button>
                <button class="btn time-btn" onclick="selectTime(this, '16:30')">16:30</button>
            </div>
            
            <button class="submit-btn" id="confirm-btn" onclick="bookMeeting()" disabled>Confirmer le Rendez-vous</button>
        </div>
        
        <script>
            let selectedDate = null;
            let selectedTime = null;
            
            const datesContainer = document.getElementById('dates');
            let currentDay = new Date();
            let added = 0;
            
            // Générer les 3 prochains jours ouvrés
            while(added < 3) {{
                currentDay.setDate(currentDay.getDate() + 1);
                if(currentDay.getDay() !== 0 && currentDay.getDay() !== 6) {{
                    const dateStr = currentDay.toLocaleDateString('fr-FR', {{weekday: 'short', day: 'numeric', month: 'short'}});
                    const isoDate = currentDay.toISOString().split('T')[0];
                    datesContainer.innerHTML += `<button class="btn date-btn" onclick="selectDate(this, '${{isoDate}}', '${{dateStr}}')">${{dateStr}}</button>`;
                    added++;
                }}
            }}
            
            function selectDate(btn, iso, str) {{
                document.querySelectorAll('.date-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                selectedDate = str;
                checkReady();
            }}
            
            function selectTime(btn, time) {{
                document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                selectedTime = time;
                checkReady();
            }}
            
            function checkReady() {{
                document.getElementById('confirm-btn').disabled = !(selectedDate && selectedTime);
            }}
            
            function bookMeeting() {{
                const card = document.getElementById('calendar-card');
                card.innerHTML = "<h2>⏳ Réservation en cours...</h2><p>Validation avec l'agenda de Dieylany.</p>";
                
                fetch('/book_meeting', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{phone: '{phone}', date: selectedDate, time: selectedTime}})
                }}).then(() => {{
                    card.innerHTML = "<h2>✅ Rendez-vous Confirmé !</h2><p style='color: #10b981;'>C'est noté dans l'agenda.</p><p style='font-size:15px; color:#4b5563;'>Dieylany vous appellera le <strong>" + selectedDate + " à " + selectedTime + "</strong>.</p><p style='font-size:14px; color:#9ca3af; margin-top:20px;'>Vous pouvez fermer cette page, une confirmation vous a été envoyée sur WhatsApp.</p>";
                }});
            }}
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def book_meeting(request: web.Request) -> web.Response:
    """Endpoint appelé quand le client valide un créneau."""
    try:
        data = await request.json()
        phone = data.get("phone")
        date = data.get("date")
        time = data.get("time")
        
        message = f"✅ *Rendez-vous Confirmé !*\n\nParfait, c'est noté dans l'agenda. 📅\nDieylany vous contactera le *{date} à {time}* pour discuter de votre projet. À très vite ! 👋"
        
        cursor.execute("UPDATE wa_settings SET ai_paused = 0 WHERE phone = ?", (phone,))
        conn.commit()
        
        await send_whatsapp(phone, message)
        add_to_wa_memory(phone, "assistant", message)
        
        if WA_LOG_CHANNEL:
            channel = bot.get_channel(WA_LOG_CHANNEL)
            if channel:
                embed = discord.Embed(title="📅 NOUVEAU RENDEZ-VOUS !", color=0x3B82F6)
                embed.add_field(name="📱 Client", value=f"+{phone}", inline=True)
                embed.add_field(name="📆 Date", value=date, inline=True)
                embed.add_field(name="⏰ Heure", value=time, inline=True)
                await channel.send("@everyone 📅 **Nouveau call booké ! Prépare tes notes.**", embed=embed)
                
        if ADMIN_PHONE:
            admin_msg = f"📅 *NOUVEAU RENDEZ-VOUS* 📅\n\n👤 Client : +{phone}\n📆 Date : {date}\n⏰ Heure : {time}\n\nC'est noté dans l'agenda ! 👋"
            await send_whatsapp(ADMIN_PHONE, admin_msg)
                
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

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
                
        if ADMIN_PHONE:
            admin_msg = f"📋 *NOUVEAU LEAD WEB* 📋\n\n👤 Nom : {name}\n📱 Tél : +{phone}\n💬 Message : {message}\n\nL'IA a répondu au client pour l'accueillir."
            await send_whatsapp(ADMIN_PHONE, admin_msg)

        return web.json_response({"success": True, "message_sent": message})

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def start_web_server():
    """Démarre le serveur aiohttp."""
    app = web.Application()
    app.router.add_get('/', show_dashboard)
    app.router.add_get('/export', export_contacts)
    app.router.add_post('/toggle_ai', toggle_ai)
    app.router.add_post('/send_manual', send_manual)
    app.router.add_get('/pay', show_payment_page)
    app.router.add_post('/process_payment', process_payment)
    app.router.add_get('/calendar', show_calendar_page)
    app.router.add_post('/book_meeting', book_meeting)
    app.router.add_post('/notify', handle_form_notification)
    runner = web.AppRunner(app)
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
        bot.loop.create_task(start_web_server())
        
        # Planifier le rapport hebdomadaire (Ex: tous les vendredis à 18h)
        scheduler.add_job(
            generate_and_send_report,
            "cron",
            day_of_week="fri",
            hour=18,
            minute=0,
            id="weekly_report"
        )
        
        # Planifier les relances (vérifie toutes les 30 minutes)
        scheduler.add_job(
            check_and_send_followups,
            "interval",
            minutes=30,
            id="drip_marketing"
        )
        
        scheduler.start()
        print("✅ Automatisations WhatsApp actives (SAV IA, Webhook, Planning, Rapports) !")
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