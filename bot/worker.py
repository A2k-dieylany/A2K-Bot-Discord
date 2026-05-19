"""
╔══════════════════════════════════════════════════════════════╗
║   bot/worker.py — Agent WhatsApp (Worker Isolé par Tenant)  ║
║   Design: Classe WhatsAppAgent injectable + testable        ║
║   Pattern: Event Loop Asyncio Pure + Circuit Breaker        ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import re
import io
import asyncio
import logging
import base64
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
import edge_tts
from google import genai
from google.genai import types
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Charge le .env du dossier courant (chaque worker a son propre .env)
load_dotenv(dotenv_path=Path(".env"), override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("worker")

# ── Configuration du Tenant (chargée depuis le .env local) ─────────────────
TENANT_ID      = os.getenv("TENANT_ID", "default")
WA_ID_INSTANCE = os.getenv("WA_ID_INSTANCE")
WA_API_TOKEN   = os.getenv("WA_API_TOKEN")
ADMIN_PHONE    = os.getenv("ADMIN_PHONE")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BUSINESS_NAME  = os.getenv("BUSINESS_NAME", "Mon Entreprise")
BUSINESS_INFO  = os.getenv("BUSINESS_INFO", "")
MAX_HISTORY    = int(os.getenv("MAX_HISTORY", 20))
DB_PATH        = os.getenv("DATABASE_PATH", "memory.db")

# ── Rotation des Modèles Gemini ─────────────────────────────────────────────
MODELS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]
_model_index = 0

# ── Base de Connaissances ───────────────────────────────────────────────────
try:
    BASE_DE_CONNAISSANCES = Path("connaissances.txt").read_text(encoding="utf-8")
except FileNotFoundError:
    BASE_DE_CONNAISSANCES = "Aucune information supplémentaire fournie."

# ── Initialisation Gemini ───────────────────────────────────────────────────
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ── Prompt Système (dynamique selon les connaissances du tenant) ────────────
SAV_PROMPT = f"""Tu es Max, l'assistante IA de {BUSINESS_NAME}.

*** BASE DE CONNAISSANCES ***
{BASE_DE_CONNAISSANCES}
****************************

TON RÔLE : Accueillir les clients, répondre à leurs questions, et les guider vers un achat ou un rendez-vous de manière fluide et chaleureuse.

TON TON :
- Sois très chaleureuse, humaine, naturelle et professionnelle.
- Réponds en 2-3 phrases max car c'est WhatsApp.
- Adapte-toi à la langue du client (français, anglais, wolof...).

BALISES SYSTÈME (à ajouter à la fin de ta réponse selon le contexte) :
- [ALERTE_PROSPECT] → Le client est très intéressé ou prêt à acheter.
- [ALERTE_HUMAIN] → Le client demande à parler à un humain.
- [FIN_DISCUSSION] → La conversation est naturellement terminée (client a dit au revoir).
- [DEVIS:Service:Montant] → Génère un devis PDF pro (ex: [DEVIS:Site Web:150000]).
- [VOCAL] → Envoie ta réponse en note vocale (écris comme tu parles, sans emojis ni listes).
- [LIEN_CALENDRIER] → Le client veut prendre un RDV.
"""


# ════════════════════════════════════════════════════════════════
#  BASE DE DONNÉES LOCALE DU WORKER (SQLite isolé)
# ════════════════════════════════════════════════════════════════

_db_conn: Optional[sqlite3.Connection] = None

def get_db() -> sqlite3.Connection:
    global _db_conn
    if _db_conn is None:
        _db_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _db_conn.execute("PRAGMA journal_mode=WAL")
        _db_conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT, role TEXT, content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        _db_conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                phone TEXT PRIMARY KEY, ai_paused INTEGER DEFAULT 0
            )
        """)
        _db_conn.execute("""
            CREATE TABLE IF NOT EXISTS followups (
                phone TEXT PRIMARY KEY, last_bot_msg DATETIME,
                status TEXT DEFAULT 'pending'
            )
        """)
        _db_conn.commit()
    return _db_conn

def add_memory(phone: str, role: str, content: str):
    db = get_db()
    db.execute("INSERT INTO memory (phone, role, content) VALUES (?, ?, ?)", (phone, role, content))
    db.commit()

def get_history(phone: str) -> list[dict]:
    db = get_db()
    rows = db.execute(
        "SELECT role, content FROM memory WHERE phone = ? ORDER BY timestamp DESC LIMIT ?",
        (phone, MAX_HISTORY)
    ).fetchall()
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

def is_ai_paused(phone: str) -> bool:
    db = get_db()
    row = db.execute("SELECT ai_paused FROM settings WHERE phone = ?", (phone,)).fetchone()
    return bool(row[0]) if row else False


# ════════════════════════════════════════════════════════════════
#  IA & TTS
# ════════════════════════════════════════════════════════════════

async def ask_gemini(phone: str, user_msg: str, media_part=None) -> str:
    """
    Génère une réponse IA avec rotation automatique des modèles Gemini.
    Circuit Breaker Pattern : bascule vers le modèle suivant si quota dépassé (429).
    """
    global _model_index
    add_memory(phone, "user", user_msg)

    history = get_history(phone)
    contents = []
    for msg in history:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [msg["content"]]})
    if media_part and contents:
        contents[-1]["parts"].insert(0, media_part)

    for attempt in range(len(MODELS)):
        idx = (_model_index + attempt) % len(MODELS)
        try:
            response = await gemini_client.aio.models.generate_content(
                model=MODELS[idx],
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SAV_PROMPT,
                    temperature=0.75,
                    max_output_tokens=800
                )
            )
            if idx != _model_index:
                _model_index = idx
                logger.info(f"🔄 Modèle basculé → {MODELS[idx]}")
            reply = response.text
            add_memory(phone, "assistant", reply)
            return reply
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                logger.warning(f"⚠️ Quota {MODELS[idx]}, rotation...")
                continue
            logger.error(f"❌ Erreur Gemini: {e}")
            raise

    return "⏳ Tous les modèles IA sont saturés. Réessaie dans quelques minutes."


def clean_for_voice(text: str) -> str:
    """Nettoie le texte pour la synthèse vocale (supprime emojis, markdown, URLs)."""
    text = re.sub(r'\[.*?\]', '', text)            # Balises système
    text = re.sub(r'https?://\S+', '', text)       # URLs
    text = re.sub(r'[*_#`~]', '', text)            # Markdown
    text = re.sub(r'[^\w\s,.:;!?\'\"éèêëàâäôöûüùçœæ%-]', ' ', text)  # Emojis et caractères spéciaux
    text = re.sub(r'\s+', ' ', text).strip()
    return text


async def generate_voice(text: str) -> bytes:
    """Génère un fichier MP3 depuis le texte via Edge TTS (Voix : fr-FR-DeniseNeural)."""
    clean = clean_for_voice(text)
    if not clean:
        raise ValueError("Texte vide après nettoyage pour TTS.")
    communicate = edge_tts.Communicate(clean, "fr-FR-DeniseNeural")
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data


# ════════════════════════════════════════════════════════════════
#  API GREEN API (WhatsApp)
# ════════════════════════════════════════════════════════════════

def _wa_url(endpoint: str) -> str:
    return f"https://api.green-api.com/waInstance{WA_ID_INSTANCE}/{endpoint}/{WA_API_TOKEN}"

def _chat_id(phone: str) -> str:
    return f"{phone.replace('+','').replace(' ','').replace('-','')}@c.us"


async def send_text(phone: str, message: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(_wa_url("sendMessage"), json={
            "chatId": _chat_id(phone),
            "message": message
        }) as resp:
            result = await resp.json()
            logger.debug(f"📤 Texte envoyé → {phone} | {resp.status}")
            return result


async def send_voice(phone: str, audio_bytes: bytes):
    form = aiohttp.FormData()
    form.add_field("chatId", _chat_id(phone))
    form.add_field("fileName", "voice.mp3")
    form.add_field("file", audio_bytes, filename="voice.mp3", content_type="audio/mpeg")
    async with aiohttp.ClientSession() as session:
        async with session.post(_wa_url("sendFileByUpload"), data=form) as resp:
            logger.debug(f"🎙️ Vocal envoyé → {phone} | {resp.status}")


async def send_file(phone: str, file_bytes: bytes, filename: str, caption: str):
    form = aiohttp.FormData()
    form.add_field("chatId", _chat_id(phone))
    form.add_field("fileName", filename)
    form.add_field("caption", caption)
    form.add_field("file", file_bytes, filename=filename, content_type="application/pdf")
    async with aiohttp.ClientSession() as session:
        async with session.post(_wa_url("sendFileByUpload"), data=form) as resp:
            logger.debug(f"📎 Fichier envoyé → {phone} | {resp.status}")


async def download_media(url: str) -> Optional[bytes]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception as e:
        logger.error(f"❌ Erreur téléchargement média: {e}")
    return None


# ════════════════════════════════════════════════════════════════
#  GÉNÉRATION DEVIS PDF
# ════════════════════════════════════════════════════════════════

def generate_devis_pdf(phone: str, service: str, montant: str, client_name: str = "Client") -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle("Title", parent=styles["Heading1"],
                                  fontSize=22, textColor=colors.HexColor("#1e3a5f"),
                                  alignment=TA_CENTER, spaceAfter=6)
    normal = ParagraphStyle("Normal", parent=styles["Normal"], fontSize=11, leading=16)

    story.append(Paragraph(f"DEVIS — {BUSINESS_NAME.upper()}", title_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1e3a5f")))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f"<b>Client :</b> {client_name} (+{phone})", normal))
    story.append(Paragraph(f"<b>Date :</b> {datetime.now().strftime('%d/%m/%Y')}", normal))
    story.append(Paragraph(f"<b>Référence :</b> DEVIS-{datetime.now().strftime('%Y%m%d')}-{phone[-4:]}", normal))
    story.append(Spacer(1, 0.5*cm))

    data = [
        ["Service", "Détails", "Prix"],
        [service, "Selon accord préalable", f"{int(montant):,} FCFA".replace(",", " ")]
    ]
    table = Table(data, colWidths=[6*cm, 8*cm, 4*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f"<b>Total TTC : {int(montant):,} FCFA</b>".replace(",", " "), normal))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("Ce devis est valable 30 jours. Pour l'accepter, répondez simplement par 'OK'.", normal))

    doc.build(story)
    return buffer.getvalue()


# ════════════════════════════════════════════════════════════════
#  TRAITEMENT DES MESSAGES (PIPELINE PRINCIPAL)
# ════════════════════════════════════════════════════════════════

async def process_message(phone: str, name: str, text: str, media_part=None):
    """
    Pipeline complet de traitement d'un message WhatsApp entrant.
    Étapes: Pause check → IA → Tag detection → TTS/PDF → Envoi
    """
    if is_ai_paused(phone):
        logger.info(f"⏸️ IA pausée pour {phone}.")
        return

    try:
        reply = await ask_gemini(phone, text, media_part)
    except Exception as e:
        logger.error(f"❌ Erreur IA pour {phone}: {e}")
        await send_text(phone, "Désolée, je rencontre une difficulté technique. Réessaie dans un instant ! 🙏")
        return

    # ── Détection et suppression des balises système ─────────────
    is_finished  = bool(re.search(r'(?i)\[FIN_DISCUSSION\]', reply))
    is_vocal     = bool(re.search(r'(?i)\[VOCAL\]', reply))
    is_hot       = bool(re.search(r'\[ALERTE_PROSPECT\]', reply))
    needs_human  = bool(re.search(r'\[ALERTE_HUMAIN\]', reply))

    reply = re.sub(r'(?i)\[FIN_DISCUSSION\]', '', reply)
    reply = re.sub(r'(?i)\[VOCAL\]', '', reply)
    reply = re.sub(r'\[ALERTE_PROSPECT\]', '', reply)
    reply = re.sub(r'\[ALERTE_HUMAIN\]', '', reply)

    # ── Interception Calendrier ───────────────────────────────────
    if re.search(r'(?i)\[LIEN_CALENDR', reply):
        calendar_url = "https://calendly.com/sendigitalsolution"
        reply = re.sub(r'(?i)\[LIEN_CALENDR[^\]]*\]',
                        f"\n\n📅 Prendre RDV : {calendar_url}", reply)

    # ── Interception Devis PDF ────────────────────────────────────
    devis_match = re.search(r'\[DEVIS:([^:]+):(\d+)\]', reply)
    if devis_match:
        d_service = devis_match.group(1).strip()
        d_montant = devis_match.group(2).strip()
        reply = reply.replace(devis_match.group(0), "").strip()
        try:
            pdf_bytes = generate_devis_pdf(phone, d_service, d_montant, name)
            filename = f"Devis_{datetime.now().strftime('%Y%m%d')}_{phone[-4:]}.pdf"
            caption = f"📄 Votre devis pour *{d_service}* — {int(d_montant):,} FCFA".replace(",", " ")
            await send_file(phone, pdf_bytes, filename, caption)
            logger.info(f"📎 Devis PDF envoyé → {phone} ({d_service})")
        except Exception as e:
            logger.error(f"⚠️ Erreur génération PDF: {e}")

    # ── Délai humain (simule le temps de frappe) ──────────────────
    reply = reply.strip()
    if not reply:
        return

    typing_delay = max(1.5, min(5.0, len(reply) * 0.035))
    await asyncio.sleep(typing_delay)

    # ── Envoi (Vocal ou Texte) ────────────────────────────────────
    if is_vocal:
        try:
            audio = await generate_voice(reply)
            await send_voice(phone, audio)
            logger.info(f"🎙️ Note vocale envoyée → {phone}")
        except Exception as e:
            logger.error(f"⚠️ Erreur TTS, fallback texte: {e}")
            await send_text(phone, reply)
    else:
        await send_text(phone, reply)

    # ── Mise à jour follow-up ─────────────────────────────────────
    db = get_db()
    status = "finished" if is_finished else "pending"
    db.execute("""
        INSERT INTO followups (phone, last_bot_msg, status) VALUES (?, CURRENT_TIMESTAMP, ?)
        ON CONFLICT(phone) DO UPDATE SET last_bot_msg = CURRENT_TIMESTAMP, status = ?
    """, (phone, status, status))
    db.commit()

    if is_hot:
        logger.info(f"🔥 PROSPECT CHAUD détecté : {name} (+{phone})")
    if needs_human:
        logger.info(f"🙋 Prise de relais humain demandée : {name} (+{phone})")


# ════════════════════════════════════════════════════════════════
#  BOUCLE DE POLLING (Event Loop Principal)
# ════════════════════════════════════════════════════════════════

async def polling_loop():
    """
    Boucle principale de réception des messages WhatsApp.
    Pattern: Long Polling avec suppression atomique des notifications.
    """
    receive_url = f"https://api.green-api.com/waInstance{WA_ID_INSTANCE}/receiveNotification/{WA_API_TOKEN}"
    delete_url  = f"https://api.green-api.com/waInstance{WA_ID_INSTANCE}/deleteNotification/{WA_API_TOKEN}"

    logger.info(f"🤖 Worker [{TENANT_ID}] démarré — en écoute WhatsApp...")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(receive_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(5)
                        continue
                    data = await resp.json()

                if not data or not data.get("body"):
                    await asyncio.sleep(3)
                    continue

                receipt_id = data["receiptId"]
                body       = data["body"]

                # Suppression immédiate pour éviter le retraitement
                await session.delete(f"{delete_url}/{receipt_id}")

                # Filtrage: seulement les messages entrants
                type_webhook = body.get("typeWebhook")
                type_msg     = body.get("messageData", {}).get("typeMessage")

                if type_webhook != "incomingMessageReceived":
                    continue
                if type_msg not in ["textMessage", "imageMessage", "audioMessage", "pttMessage"]:
                    continue

                sender = body["senderData"]["sender"]
                phone  = sender.replace("@c.us", "")
                name   = body["senderData"].get("senderName", phone)

                # Ignorer les messages de l'admin (évite les boucles)
                if ADMIN_PHONE and phone == ADMIN_PHONE.replace("+", ""):
                    continue

                text       = ""
                media_part = None

                if type_msg == "textMessage":
                    text = body["messageData"]["textMessageData"]["textMessage"]

                elif type_msg in ["imageMessage", "audioMessage", "pttMessage"]:
                    msg_data = body["messageData"].get("fileMessageData", {})
                    caption  = msg_data.get("caption", "")

                    if type_msg in ["audioMessage", "pttMessage"]:
                        text = "[Le client vient d'envoyer un message vocal. Réponds-lui OBLIGATOIREMENT par une note vocale en ajoutant [VOCAL] à la fin de ta réponse. Sois chaleureuse et naturelle.]"
                        dl_url = msg_data.get("downloadUrl")
                        if dl_url:
                            media_bytes = await download_media(dl_url)
                            if media_bytes:
                                media_part = types.Part.from_bytes(
                                    data=media_bytes, 
                                    mime_type="audio/ogg"
                                )
                    else:
                        text = caption or "Une image a été envoyée."
                        dl_url = msg_data.get("downloadUrl")
                        if dl_url:
                            media_bytes = await download_media(dl_url)
                            if media_bytes:
                                mime = msg_data.get("mimeType", "image/jpeg")
                                media_part = types.Part.from_bytes(
                                    data=media_bytes, 
                                    mime_type=mime
                                )

                logger.info(f"📱 Message [{TENANT_ID}] de {name} (+{phone}): {text[:60]}...")

                # Traitement asynchrone non-bloquant
                asyncio.create_task(process_message(phone, name, text, media_part))

            except asyncio.CancelledError:
                logger.info("🛑 Worker arrêté proprement.")
                break
            except Exception as e:
                logger.error(f"⚠️ Erreur polling [{TENANT_ID}]: {e}")
                await asyncio.sleep(10)


# ════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE DU WORKER
# ════════════════════════════════════════════════════════════════

async def main():
    """Point d'entrée principal du worker bot."""
    logger.info(f"╔══════════════════════════════════════╗")
    logger.info(f"║  WhatsApp Worker — {BUSINESS_NAME[:20]:<20} ║")
    logger.info(f"║  Tenant ID : {TENANT_ID:<24} ║")
    logger.info(f"╚══════════════════════════════════════╝")
    await polling_loop()

if __name__ == "__main__":
    asyncio.run(main())
