import asyncio
import discord
from discord.ext import commands
from discord import app_commands


class WhatsAppCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="whatsapp", description="Envoie un message WhatsApp depuis Discord")
    @app_commands.describe(
        telephone="Numéro avec indicatif pays (ex: 221771234567)",
        message="Le message à envoyer"
    )
    async def cmd_whatsapp(self, interaction: discord.Interaction, telephone: str, message: str):
        await interaction.response.defer()
        try:
            result = await self.bot.send_whatsapp(telephone, message)
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

    @app_commands.command(name="wa_ia", description="Génère un message IA et l'envoie sur WhatsApp")
    @app_commands.describe(
        telephone="Numéro avec indicatif (ex: 221771234567)",
        sujet="Sujet du message (ex: rappel réunion demain 10h, promo -20%...)"
    )
    async def cmd_wa_ia(self, interaction: discord.Interaction, telephone: str, sujet: str):
        await interaction.response.defer()
        prompt = (
            f"Rédige un message WhatsApp professionnel et naturel sur ce sujet : {sujet}\n\n"
            f"Court (max 3 lignes), chaleureux, direct. Juste le texte, rien d'autre."
        )
        message_genere = await self.bot.ask_gemini(interaction.channel_id, prompt)
        try:
            result = await self.bot.send_whatsapp(telephone, message_genere)
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

    @app_commands.command(name="wa_broadcast", description="Envoie un message WhatsApp à plusieurs personnes")
    @app_commands.describe(
        numeros="Numéros séparés par des virgules (ex: 221771234567,221781234567)",
        message="Le message à envoyer à tous"
    )
    async def cmd_wa_broadcast(self, interaction: discord.Interaction, numeros: str, message: str):
        await interaction.response.defer()
        liste = [n.strip() for n in numeros.split(",")]
        resultats = []
        for num in liste:
            try:
                result = await self.bot.send_whatsapp(num, message)
                resultats.append(f"✅ `{num}`" if "idMessage" in result else f"❌ `{num}`")
                await asyncio.sleep(1)
            except Exception as e:
                resultats.append(f"❌ `{num}` — {e}")
        await interaction.followup.send(
            f"📢 **Broadcast terminé !**\n💬 *{message}*\n\n" + "\n".join(resultats)
        )

    @app_commands.command(name="wa_planning_add", description="Programme un envoi WhatsApp automatique")
    @app_commands.describe(
        heure="Heure d'envoi (ex: 08:00)",
        numeros="Numéros séparés par virgules",
        message="Message à envoyer automatiquement"
    )
    async def cmd_planning_add(self, interaction: discord.Interaction, heure: str, numeros: str, message: str):
        await interaction.response.defer()
        try:
            h, m = heure.split(":")
            liste = [n.strip() for n in numeros.split(",")]
            self.bot.planning_counter += 1
            pid = self.bot.planning_counter

            label = f"Planning #{pid} à {heure}"

            self.bot.scheduler.add_job(
                self.bot.execute_planned_message,
                "cron",
                hour=int(h),
                minute=int(m),
                args=[liste, message, label],
                id=f"plan_{pid}"
            )

            self.bot.wa_planning.append({
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

    @app_commands.command(name="wa_planning_list", description="Voir les messages programmés")
    async def cmd_planning_list(self, interaction: discord.Interaction):
        if not self.bot.wa_planning:
            await interaction.response.send_message("📭 Aucun message programmé.", ephemeral=True)
            return
        embed = discord.Embed(title="⏰ Messages WhatsApp programmés", color=0x25D366)
        for p in self.bot.wa_planning:
            embed.add_field(
                name=f"#{p['id']} — {p['heure']} tous les jours",
                value=f"👥 {len(p['numeros'])} contacts\n💬 {p['message'][:80]}...",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="wa_planning_remove", description="Supprimer un message programmé")
    @app_commands.describe(id_planning="L'ID du planning à supprimer")
    async def cmd_planning_remove(self, interaction: discord.Interaction, id_planning: int):
        try:
            self.bot.scheduler.remove_job(f"plan_{id_planning}")
            self.bot.wa_planning[:] = [p for p in self.bot.wa_planning if p["id"] != id_planning]
            await interaction.response.send_message(f"🗑️ Planning #{id_planning} supprimé !")
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur : {e}")

    @app_commands.command(name="wa_rapport", description="Génère et t'envoie le rapport de stats sur WhatsApp instantanément")
    async def cmd_wa_rapport(self, interaction: discord.Interaction):
        await interaction.response.send_message("📊 Génération du rapport en cours... Vérifie ton WhatsApp !", ephemeral=True)
        await self.bot.generate_and_send_report()

    @app_commands.command(name="wa_force_relance", description="[Admin] Force la vérification immédiate des relances Drip Marketing")
    async def cmd_wa_force_relance(self, interaction: discord.Interaction):
        await interaction.response.send_message("🔍 Lancement forcé de la relance (ignore la limite des 48h)...", ephemeral=True)
        await self.bot.check_and_send_followups(force=True)


async def setup(bot):
    await bot.add_cog(WhatsAppCog(bot))
