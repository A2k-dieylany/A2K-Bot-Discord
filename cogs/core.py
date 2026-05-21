import os
import discord
from discord.ext import commands
from discord import app_commands

BOT_NAME = os.getenv("BOT_NAME", "MonBot")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", 20))
# On utilise la variable de main.py si elle existe, sinon par défaut
MODEL_NAME = "gemini-2.5-flash"

class CoreCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="clear", description="Efface l'historique du salon actuel")
    async def cmd_clear(self, interaction: discord.Interaction):
        # On accède au dictionnaire de mémoire globale via l'instance du bot
        if hasattr(self.bot, 'conversation_memory') and interaction.channel_id in self.bot.conversation_memory:
            self.bot.conversation_memory[interaction.channel_id].clear()
            await interaction.response.send_message("🧹 Historique de ce salon effacé ! On repart de zéro.", ephemeral=True)
        else:
            await interaction.response.send_message("🧹 Aucun historique récent trouvé pour ce salon.", ephemeral=True)

    @app_commands.command(name="info", description="Affiche les commandes disponibles")
    async def cmd_info(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"🤖 {BOT_NAME} - Agent IA + WhatsApp Automation",
            description=f"Propulsé par **Gemini 2.5 Flash** & Green API",
            color=0x5865F2
        )
        embed.add_field(name="💬 Conversation IA", value="`/ask` `/clear` `@mention`\n*📎 Tu peux joindre un fichier !*", inline=False)
        embed.add_field(name="💻 Code & Texte", value="`/code` `/debug` `/expliquer` `/traduire` `/resume` `/corriger`", inline=False)
        embed.add_field(name="🚀 Productivité", value="`/tache` `/plan` `/math` `/creer_post`", inline=False)
        embed.add_field(name="📞 WhatsApp Manuel", value="`/whatsapp` `/wa_ia` `/wa_broadcast`", inline=False)
        embed.add_field(name="⏱️ WhatsApp Auto", value="`/wa_planning_add` `/wa_planning_list` `/wa_planning_remove`\n`🤖 Bot SAV Auto` `✅ Webhook Formulaires`", inline=False)
        
        current_model = getattr(self.bot, 'MODEL_NAME', MODEL_NAME)
        embed.set_footer(text=f"Modèle : {current_model} | Mémoire : {MAX_HISTORY} messages")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(CoreCog(bot))
