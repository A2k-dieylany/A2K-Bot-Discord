"""
╔══════════════════════════════════════════════════════════════╗
║     🎛️ COG DASHBOARD — Interface Graphique Discord          ║
║     Panneau de contrôle interactif pour Sen Digital Sol.     ║
╚══════════════════════════════════════════════════════════════╝
"""

import discord
from discord.ext import commands
from discord import app_commands


class FollowupDelaySelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="Désactiver les relances", description="Arrête l'envoi automatique", emoji="🔴", value="0"),
            discord.SelectOption(label="Relance après 24h", description="Plus agressif", emoji="⚡", value="24"),
            discord.SelectOption(label="Relance après 48h", description="Recommandé (Standard)", emoji="✅", value="48"),
            discord.SelectOption(label="Relance après 72h", description="Plus doux", emoji="⏳", value="72"),
        ]
        
        # Déterminer la valeur actuelle
        current_delay = self.bot.config.get("followup_delay_hours", 48)
        current_active = self.bot.config.get("auto_followup", True)
        current_val = "0" if not current_active else str(current_delay)
        
        # Mettre l'option actuelle en "default"
        for opt in options:
            if opt.value == current_val:
                opt.default = True

        super().__init__(placeholder="Paramétrer le délai de relance", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        val = int(self.values[0])
        if val == 0:
            self.bot.config["auto_followup"] = False
            msg = "🔴 **Relances automatiques WhatsApp DÉSACTIVÉES.**"
        else:
            self.bot.config["auto_followup"] = True
            self.bot.config["followup_delay_hours"] = val
            msg = f"✅ **Délai des relances WhatsApp mis à jour : {val} heures.**"
        
        # Mettre à jour l'affichage du menu
        for opt in self.options:
            opt.default = (opt.value == self.values[0])
            
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(msg, ephemeral=True)


class DashboardView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)  # Persistant
        self.bot = bot
        
        # Ajouter le menu déroulant
        self.add_item(FollowupDelaySelect(bot))

    @discord.ui.button(label="🔄 Actualiser", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self._generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🚀 Forcer Relance", style=discord.ButtonStyle.primary, emoji="🚀", row=1)
    async def btn_force_followup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        # On appelle la fonction de main.py
        try:
            await self.bot.check_and_send_followups(force=True)
            await interaction.followup.send("✅ **Lancement forcé de la relance WhatsApp effectué.**")
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur lors du lancement de la relance : {e}")

    @discord.ui.button(label="🧹 Vider Mémoire IA", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def btn_clear_memory(self, interaction: discord.Interaction, button: discord.ui.Button):
        # On réinitialise la mémoire conversationnelle globale
        for key in list(self.bot.conversation_memory.keys()):
            self.bot.conversation_memory[key] = []
        await interaction.response.send_message("🧹 **Mémoire de toutes les conversations IA vidée.**", ephemeral=True)

    def _generate_embed(self) -> discord.Embed:
        # Status
        status_ia = "🟢 Actif" if self.bot.config.get("gemini_ready", True) else "🔴 Hors ligne"
        status_wa = "🟢 Connecté"  # Supposé connecté si la commande marche
        
        # DB Stats
        try:
            self.bot.cursor.execute("SELECT COUNT(*) FROM wa_followups WHERE status = 'pending'")
            pending_count = self.bot.cursor.fetchone()[0]
        except:
            pending_count = 0
            
        try:
            self.bot.cursor.execute("SELECT COUNT(*) FROM wa_conversations")
            conv_count = self.bot.cursor.fetchone()[0]
        except:
            conv_count = 0

        # Config Actuelle
        auto = self.bot.config.get("auto_followup", True)
        delay = self.bot.config.get("followup_delay_hours", 48)
        conf_relance = f"✅ Actif ({delay}h)" if auto else "🔴 Désactivé"

        embed = discord.Embed(
            title="🎛️ Panneau de Contrôle - Sen Digital Solution",
            description="Interface de gestion des automatisations et de l'intelligence artificielle.",
            color=0x2b2d31
        )
        
        embed.add_field(name="🤖 État des Services", value=f"**IA (Gemini) :** {status_ia}\n**API WhatsApp :** {status_wa}", inline=False)
        embed.add_field(name="📈 Statistiques WhatsApp", value=f"**Conversations totales :** {conv_count}\n**Prospects en attente de relance :** {pending_count}", inline=False)
        embed.add_field(name="⚙️ Configuration Actuelle", value=f"**Drip Marketing (Relance auto) :** {conf_relance}", inline=False)
        
        embed.set_footer(text="Système opérationnel • Actualisé à l'instant")
        return embed


class DashboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="dashboard",
        description="🎛️ Affiche le panneau de contrôle interactif (Stats, Relances, IA)"
    )
    async def cmd_dashboard(self, interaction: discord.Interaction):
        view = DashboardView(self.bot)
        embed = view._generate_embed()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(DashboardCog(bot))
