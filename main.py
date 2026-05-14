"""
╔══════════════════════════════════════════════════════════════╗
║        🤖 AI DISCORD BOT — Agent Polyvalent (Groq FREE)      ║
║               Propulsé par Groq + Llama 3.3 70B              ║
╚══════════════════════════════════════════════════════════════╝

Fonctionnalités :
  /ask        — Poser n'importe quelle question
  /code       — Générer du code dans n'importe quel langage
  /debug      — Déboguer un code avec son message d'erreur
  /expliquer  — Expliquer un bloc de code
  /traduire   — Traduire un texte dans n'importe quelle langue
  /resume     — Résumer un texte long
  /tache      — Décomposer une tâche complexe en étapes claires
  /plan       — Créer un plan de projet professionnel
  /math       — Résoudre des problèmes mathématiques
  /corriger   — Corriger et améliorer un texte
  /clear      — Effacer l'historique de conversation
  @mention    — Conversation directe avec mémoire contextuelle
"""

import os
import discord
from discord import app_commands
from discord.ext import commands
from groq import AsyncGroq
from dotenv import load_dotenv
from collections import defaultdict

# ── Configuration ──────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
BOT_NAME      = os.getenv("BOT_NAME", "MonBot")
MAX_HISTORY   = int(os.getenv("MAX_HISTORY", 20))
MODEL         = "llama-3.3-70b-versatile"   # Modèle gratuit et très puissant

# ── Clients ────────────────────────────────────────────────────
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ── Mémoire de conversation par salon/thread ───────────────────
conversation_memory: dict[int, list] = defaultdict(list)

# ── Prompt système ─────────────────────────────────────────────
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

# ══════════════════════════════════════════════════════════════
#  FONCTIONS UTILITAIRES
# ══════════════════════════════════════════════════════════════

def add_to_memory(session_id: int, role: str, content: str):
    conversation_memory[session_id].append({"role": role, "content": content})
    if len(conversation_memory[session_id]) > MAX_HISTORY:
        conversation_memory[session_id] = conversation_memory[session_id][-MAX_HISTORY:]

def get_history(session_id: int) -> list:
    return conversation_memory.get(session_id, [])

async def ask_groq(session_id: int, user_message: str) -> str:
    add_to_memory(session_id, "user", user_message)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + get_history(session_id)
    try:
        response = await groq_client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=2000,
            temperature=0.7
        )
        reply = response.choices[0].message.content
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
#  ÉVÉNEMENTS BOT
# ══════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"╔══════════════════════════════════════════╗")
    print(f"║  ✅ {BOT_NAME} est en ligne !              ")
    print(f"║  🤖 Modèle : {MODEL}    ")
    print(f"║  📋 Serveurs : {len(bot.guilds)}           ")
    print(f"╚══════════════════════════════════════════╝")
    await bot.tree.sync()
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="vos questions | /ask"
        )
    )

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    await bot.process_commands(message)

    # Le bot répond maintenant à TOUS les messages (sauf s'ils commencent par !)
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
                        pass # Ignore les images/fichiers binaires
                        
        if not text and not attached_files_content:
            await message.reply("👋 Pose-moi une question ou envoie-moi un fichier texte/code !")
            return
            
        final_prompt = text + attached_files_content

        async with message.channel.typing():
            reply = await ask_groq(message.channel.id, final_prompt)
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

    reply = await ask_groq(interaction.channel_id, prompt)
    await send_long_reply(interaction, f"💬 **{interaction.user.display_name}** : {question}\n\n{reply}")

@bot.tree.command(name="code", description="Génère du code dans le langage de ton choix")
@app_commands.describe(langage="Langage (ex: Python, JavaScript...)", description="Ce que doit faire le code")
async def cmd_code(interaction: discord.Interaction, langage: str, description: str):
    await interaction.response.defer()
    prompt = (f"Génère du code {langage} pour : {description}\n\n"
              f"Fournis : 1. Le code complet dans un bloc ```{langage.lower()} "
              f"2. Explication courte 3. Comment l'utiliser")
    reply = await ask_groq(interaction.channel_id, prompt)
    await send_long_reply(interaction, f"⚙️ **Code {langage}** — *{description}*\n\n{reply}")

@bot.tree.command(name="debug", description="Débogue ton code et corrige les erreurs")
@app_commands.describe(code="Le code problématique", erreur="Le message d'erreur")
async def cmd_debug(interaction: discord.Interaction, code: str, erreur: str = "Non précisée"):
    await interaction.response.defer()
    prompt = (f"Débogue ce code :\n```\n{code}\n```\nErreur : {erreur}\n\n"
              f"Fournis : 1. Le bug identifié 2. Le code corrigé 3. L'explication")
    reply = await ask_groq(interaction.channel_id, prompt)
    await send_long_reply(interaction, f"🐛 **Débogage :**\n\n{reply}")

@bot.tree.command(name="expliquer", description="Explique un bloc de code")
@app_commands.describe(code="Le code à expliquer")
async def cmd_expliquer(interaction: discord.Interaction, code: str):
    await interaction.response.defer()
    prompt = f"Explique ce code clairement :\n```\n{code}\n```"
    reply = await ask_groq(interaction.channel_id, prompt)
    await send_long_reply(interaction, f"📖 **Explication :**\n\n{reply}")

@bot.tree.command(name="traduire", description="Traduit un texte dans la langue de ton choix")
@app_commands.describe(texte="Le texte à traduire", langue="Langue cible (ex: Anglais, Wolof...)")
async def cmd_traduire(interaction: discord.Interaction, texte: str, langue: str):
    await interaction.response.defer()
    prompt = f"Traduis ce texte en {langue} :\n\n{texte}"
    reply = await ask_groq(interaction.channel_id, prompt)
    await send_embed_reply(interaction, f"🌍 Traduction → {langue}", reply, 0x1ABC9C)

@bot.tree.command(name="resume", description="Résume un texte long en points clés")
@app_commands.describe(texte="Le texte à résumer")
async def cmd_resume(interaction: discord.Interaction, texte: str):
    await interaction.response.defer()
    prompt = f"Résume ce texte avec : 1. TL;DR en 2 phrases 2. Points clés 3. Conclusion\n\n{texte}"
    reply = await ask_groq(interaction.channel_id, prompt)
    await send_embed_reply(interaction, "📝 Résumé du texte", reply, 0x9B59B6)

@bot.tree.command(name="tache", description="Décompose une tâche complexe en étapes")
@app_commands.describe(tache="La tâche complexe à accomplir")
async def cmd_tache(interaction: discord.Interaction, tache: str):
    await interaction.response.defer()
    prompt = (f"Décompose cette tâche en étapes concrètes : {tache}\n\n"
              f"Inclus : analyse, étapes détaillées, outils recommandés, pièges à éviter")
    reply = await ask_groq(interaction.channel_id, prompt)
    await send_embed_reply(interaction, f"✅ Décomposition : {tache[:200]}", reply, 0x3498DB)

@bot.tree.command(name="plan", description="Crée un plan de projet professionnel")
@app_commands.describe(projet="Description du projet", delai="Délai (ex: 2 semaines)")
async def cmd_plan(interaction: discord.Interaction, projet: str, delai: str = "Non défini"):
    await interaction.response.defer()
    prompt = (f"Crée un plan de projet pour : {projet} (délai : {delai})\n"
              f"Inclus : objectifs, phases, livrables, risques, KPIs")
    reply = await ask_groq(interaction.channel_id, prompt)
    await send_embed_reply(interaction, f"📋 Plan de projet : {projet[:200]}", reply, 0x2ECC71)

@bot.tree.command(name="math", description="Résout des problèmes mathématiques")
@app_commands.describe(probleme="Le problème à résoudre")
async def cmd_math(interaction: discord.Interaction, probleme: str):
    await interaction.response.defer()
    prompt = f"Résous step by step : {probleme}\nDonne : démarche, réponse finale, vérification"
    reply = await ask_groq(interaction.channel_id, prompt)
    await send_embed_reply(interaction, "🔢 Mathématiques", reply, 0xE67E22)

@bot.tree.command(name="corriger", description="Corrige et améliore un texte")
@app_commands.describe(texte="Le texte à corriger", style="Style (professionnel, académique...)")
async def cmd_corriger(interaction: discord.Interaction, texte: str, style: str = "professionnel"):
    await interaction.response.defer()
    prompt = f"Corrige et améliore en style {style} :\n\n{texte}\n\nDonne : texte corrigé + liste des corrections"
    reply = await ask_groq(interaction.channel_id, prompt)
    await send_embed_reply(interaction, f"✍️ Correction (Style: {style})", reply, 0xE74C3C)

@bot.tree.command(name="clear", description="Efface l'historique du salon actuel")
async def cmd_clear(interaction: discord.Interaction):
    conversation_memory[interaction.channel_id].clear()
    await interaction.response.send_message("🗑️ Historique de ce salon effacé ! On repart de zéro.", ephemeral=True)

@bot.tree.command(name="info", description="Affiche les commandes disponibles")
async def cmd_info(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"🤖 {BOT_NAME} — Agent IA Polyvalent",
        description=f"Propulsé par **Groq + Llama 3.3 70B** — 100% Gratuit !",
        color=0x5865F2
    )
    embed.add_field(name="💬 Conversation", value="`/ask` `/clear` `@mention`\n*📎 Tu peux joindre un fichier (code, txt) !*", inline=False)
    embed.add_field(name="💻 Code", value="`/code` `/debug` `/expliquer`", inline=False)
    embed.add_field(name="📝 Texte", value="`/traduire` `/resume` `/corriger`", inline=False)
    embed.add_field(name="🎯 Productivité", value="`/tache` `/plan` `/math`", inline=False)
    embed.set_footer(text=f"Modèle : {MODEL} | Mémoire : {MAX_HISTORY} messages")
    await interaction.response.send_message(embed=embed)

# ══════════════════════════════════════════════════════════════
#  LANCEMENT
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise ValueError("❌ DISCORD_TOKEN manquant dans .env !")
    if not GROQ_API_KEY:
        raise ValueError("❌ GROQ_API_KEY manquant dans .env !")
    print("🚀 Démarrage du bot...")
    bot.run(DISCORD_TOKEN)