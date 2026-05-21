import discord
from discord.ext import commands
from discord import app_commands

class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ask", description="Pose n'importe quelle question à l'IA (fichier supporté)")
    @app_commands.describe(question="Ta question", fichier="Un fichier texte ou code (optionnel)")
    async def cmd_ask(self, interaction: discord.Interaction, question: str, fichier: discord.Attachment = None):
        await interaction.response.defer()
        prompt = question
        if fichier and fichier.size < 1000000:
            try:
                file_bytes = await fichier.read()
                file_text = file_bytes.decode('utf-8')
                prompt += f"\n\n--- Fichier '{fichier.filename}' ---\n```\n{file_text[:4000]}\n```"
            except UnicodeDecodeError:
                pass
        reply = await self.bot.ask_gemini(interaction.channel_id, prompt)
        await self.bot.send_long_reply(interaction, f"💬 **{interaction.user.display_name}** : {question}\n\n{reply}")

    @app_commands.command(name="code", description="Génère du code dans le langage de ton choix")
    @app_commands.describe(langage="Langage (ex: Python, JavaScript...)", description="Ce que doit faire le code")
    async def cmd_code(self, interaction: discord.Interaction, langage: str, description: str):
        await interaction.response.defer()
        prompt = (f"Génère du code {langage} pour : {description}\n\n"
                  f"Fournis : 1. Le code complet dans un bloc ```{langage.lower()} "
                  f"2. Explication courte 3. Comment l'utiliser")
        reply = await self.bot.ask_gemini(interaction.channel_id, prompt)
        await self.bot.send_long_reply(interaction, f"⚙️ **Code {langage}** — *{description}*\n\n{reply}")

    @app_commands.command(name="debug", description="Débogue ton code et corrige les erreurs")
    @app_commands.describe(code="Le code problématique", erreur="Le message d'erreur")
    async def cmd_debug(self, interaction: discord.Interaction, code: str, erreur: str = "Non précisée"):
        await interaction.response.defer()
        prompt = (f"Débogue ce code :\n```\n{code}\n```\nErreur : {erreur}\n\n"
                  f"Fournis : 1. Le bug identifié 2. Le code corrigé 3. L'explication")
        reply = await self.bot.ask_gemini(interaction.channel_id, prompt)
        await self.bot.send_long_reply(interaction, f"🐛 **Débogage :**\n\n{reply}")

    @app_commands.command(name="expliquer", description="Explique un bloc de code")
    @app_commands.describe(code="Le code à expliquer")
    async def cmd_expliquer(self, interaction: discord.Interaction, code: str):
        await interaction.response.defer()
        prompt = f"Explique ce code clairement :\n```\n{code}\n```"
        reply = await self.bot.ask_gemini(interaction.channel_id, prompt)
        await self.bot.send_long_reply(interaction, f"📖 **Explication :**\n\n{reply}")

    @app_commands.command(name="traduire", description="Traduit un texte dans la langue de ton choix")
    @app_commands.describe(texte="Le texte à traduire", langue="Langue cible (ex: Anglais, Wolof...)")
    async def cmd_traduire(self, interaction: discord.Interaction, texte: str, langue: str):
        await interaction.response.defer()
        prompt = f"Traduis ce texte en {langue} :\n\n{texte}"
        reply = await self.bot.ask_gemini(interaction.channel_id, prompt)
        await self.bot.send_embed_reply(interaction, f"🌍 Traduction → {langue}", reply, 0x1ABC9C)

    @app_commands.command(name="resume", description="Résume un texte long en points clés")
    @app_commands.describe(texte="Le texte à résumer")
    async def cmd_resume(self, interaction: discord.Interaction, texte: str):
        await interaction.response.defer()
        prompt = f"Résume ce texte avec : 1. TL;DR en 2 phrases 2. Points clés 3. Conclusion\n\n{texte}"
        reply = await self.bot.ask_gemini(interaction.channel_id, prompt)
        await self.bot.send_embed_reply(interaction, "📝 Résumé du texte", reply, 0x9B59B6)

    @app_commands.command(name="tache", description="Décompose une tâche complexe en étapes")
    @app_commands.describe(tache="La tâche complexe à accomplir")
    async def cmd_tache(self, interaction: discord.Interaction, tache: str):
        await interaction.response.defer()
        prompt = (f"Décompose cette tâche en étapes concrètes : {tache}\n\n"
                  f"Inclus : analyse, étapes détaillées, outils recommandés, pièges à éviter")
        reply = await self.bot.ask_gemini(interaction.channel_id, prompt)
        await self.bot.send_embed_reply(interaction, f"✅ Décomposition : {tache[:200]}", reply, 0x3498DB)

    @app_commands.command(name="plan", description="Crée un plan de projet professionnel")
    @app_commands.describe(projet="Description du projet", delai="Délai (ex: 2 semaines)")
    async def cmd_plan(self, interaction: discord.Interaction, projet: str, delai: str = "Non défini"):
        await interaction.response.defer()
        prompt = (f"Crée un plan de projet pour : {projet} (délai : {delai})\n"
                  f"Inclus : objectifs, phases, livrables, risques, KPIs")
        reply = await self.bot.ask_gemini(interaction.channel_id, prompt)
        await self.bot.send_embed_reply(interaction, f"📋 Plan de projet : {projet[:200]}", reply, 0x2ECC71)

    @app_commands.command(name="math", description="Résout des problèmes mathématiques")
    @app_commands.describe(probleme="Le problème à résoudre")
    async def cmd_math(self, interaction: discord.Interaction, probleme: str):
        await interaction.response.defer()
        prompt = f"Résous step by step : {probleme}\nDonne : démarche, réponse finale, vérification"
        reply = await self.bot.ask_gemini(interaction.channel_id, prompt)
        await self.bot.send_embed_reply(interaction, "🔢 Mathématiques", reply, 0xE67E22)

    @app_commands.command(name="corriger", description="Corrige et améliore un texte")
    @app_commands.describe(texte="Le texte à corriger", style="Style (professionnel, académique...)")
    async def cmd_corriger(self, interaction: discord.Interaction, texte: str, style: str = "professionnel"):
        await interaction.response.defer()
        prompt = f"Corrige et améliore en style {style} :\n\n{texte}\n\nDonne : texte corrigé + liste des corrections"
        reply = await self.bot.ask_gemini(interaction.channel_id, prompt)
        await self.bot.send_embed_reply(interaction, f"✍️ Correction (Style: {style})", reply, 0xE74C3C)

async def setup(bot):
    await bot.add_cog(AICog(bot))
