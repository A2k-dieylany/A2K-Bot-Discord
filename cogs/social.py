import os
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp

BUSINESS_NAME = "Sen Digital Solution"
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL", "")

def get_social_media_prompt(platform: str, topic: str) -> str:
    base = f"Tu es le Social Media Manager Expert de l'agence {BUSINESS_NAME}. "
    base += f"Ton objectif est de rédiger un post extrêmement captivant pour {platform} sur le sujet suivant : '{topic}'.\n\n"
    
    if platform.lower() == "linkedin":
        base += "RÈGLES STRICTES LINKEDIN (Agis comme un Copywriter B2B de haut niveau) :\n"
        base += "- INTERDIT d'utiliser des formules bateau comme 'Bonjour réseau', 'Aujourd'hui je voulais vous parler', ou '🚀 Exciting news'.\n"
        base += "- Utilise le framework PAS (Problème, Agitation, Solution).\n"
        base += "- La toute première ligne (le Hook) DOIT être percutante, clivante ou poser un problème douloureux (ex: '90% des entreprises perdent des clients à cause de...').\n"
        base += "- Saute une ligne après CHAQUE phrase pour créer un format très aéré (très important pour l'algorithme LinkedIn).\n"
        base += "- Ton : Direct, expert, sans jargon complexe, centré sur la valeur apportée.\n"
        base += "- Utilise maximum 3 emojis dans tout le post (ex: ❌, 👉, ✅).\n"
        base += "- Fais des listes à puces simples si tu énumères des avantages.\n"
        base += "- Termine par une question claire pour forcer l'audience à commenter (Call to Action).\n"
        base += "- Inclus 3 hashtags ciblés à la toute fin."
    elif platform.lower() == "facebook":
        base += "RÈGLES FACEBOOK :\n- Ton chaleureux, communautaire, accessible.\n- Cible les PME et entrepreneurs.\n- Commence par accrocher l'attention avec un problème ou une émotion.\n- Le texte peut être un peu plus détendu que sur LinkedIn.\n- N'hésite pas à utiliser des emojis pour dynamiser.\n- Appelle clairement à l'action (ex: 'Contactez-nous' ou 'Lien en commentaire').\n- 2-3 hashtags pertinents à la fin."
    else:
        base += "RÈGLES GÉNÉRALES :\n- Fais un post engageant, clair, avec des emojis et des hashtags adaptés."
        
    base += "\n\n⚠️ TRES IMPORTANT : Le texte DOIT faire moins de 1500 caractères au total. Sois percutant et concis.\n"
    base += "Génère uniquement le contenu du post (pas d'intro type 'Voici ton post')."
    return base

class SocialMediaView(discord.ui.View):
    def __init__(self, bot, user_id: int, platform: str, topic: str, content: str, image_url: str = None):
        super().__init__(timeout=86400)
        self.bot = bot
        self.user_id = user_id
        self.platform = platform
        self.topic = topic
        self.content = content
        self.image_url = image_url

    @discord.ui.button(label="✅ Publier", style=discord.ButtonStyle.success)
    async def btn_publish(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Tu n'es pas l'auteur de ce post.", ephemeral=True)
            return
            
        if not MAKE_WEBHOOK_URL:
            await interaction.response.send_message("❌ Erreur : MAKE_WEBHOOK_URL non configuré dans le .env", ephemeral=True)
            return

        await interaction.response.defer()
        
        payload = {
            "platform": self.platform,
            "topic": self.topic,
            "content": self.content,
            "image_url": self.image_url,
            "author": interaction.user.name
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(MAKE_WEBHOOK_URL, json=payload) as resp:
                    if resp.status in [200, 201, 202]:
                        for child in self.children:
                            child.disabled = True
                        await interaction.message.edit(view=self)
                        await interaction.followup.send(f"🚀 **Succès !** Le post a été envoyé à Make.com pour publication sur {self.platform} !")
                    else:
                        await interaction.followup.send(f"⚠️ Erreur HTTP {resp.status} depuis Make.com.")
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur de connexion au Webhook : {e}")

    @discord.ui.button(label="🔄 Regénérer", style=discord.ButtonStyle.primary)
    async def btn_regenerate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Tu n'es pas l'auteur.", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        prompt = get_social_media_prompt(self.platform, self.topic)
        prompt += "\n\n(IMPORTANT: L'utilisateur a demandé une nouvelle version différente de la précédente. Change l'angle d'approche ou le ton.)"
        
        new_content = await self.bot.gemini_generate(prompt)
        self.content = new_content
        
        msg_text = f"📝 **Brouillon {self.platform}**\n\n{new_content}"
        if len(msg_text) > 1990:
            msg_text = msg_text[:1990] + "..."
            
        if self.image_url:
            msg_text += f"\n\n🔗 Image attachée : {self.image_url}"
        
        await interaction.message.edit(content=msg_text, embed=None, view=self)
        await interaction.followup.send("🔄 Nouveau brouillon généré !", ephemeral=True)

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.danger)
    async def btn_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.user_id:
            await interaction.message.delete()
        else:
            await interaction.response.send_message("❌ Tu n'es pas l'auteur.", ephemeral=True)


class SocialCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="creer_post", description="Génère et publie un post sur les réseaux sociaux (via Make)")
    @app_commands.describe(plateforme="LinkedIn, Facebook, ou Instagram", sujet="Le sujet de ton post", image="Image à joindre (optionnelle)")
    @app_commands.choices(plateforme=[
        app_commands.Choice(name="LinkedIn", value="LinkedIn"),
        app_commands.Choice(name="Facebook", value="Facebook"),
        app_commands.Choice(name="Instagram", value="Instagram")
    ])
    async def creer_post(self, interaction: discord.Interaction, plateforme: app_commands.Choice[str], sujet: str, image: discord.Attachment = None):
        await interaction.response.defer()
        
        image_url = None
        if image:
            if "image" not in image.content_type:
                await interaction.followup.send("❌ Le fichier fourni n'est pas une image valide.")
                return
            image_url = image.url

        platform_name = plateforme.value
        prompt = get_social_media_prompt(platform_name, sujet)
        
        try:
            content = await self.bot.gemini_generate(prompt)
            
            msg_text = f"📝 **Brouillon {platform_name}**\n\n{content}"
            if len(msg_text) > 1990:
                msg_text = msg_text[:1990] + "..."
                
            if image_url:
                msg_text += f"\n\n🔗 Image attachée : {image_url}"
                
            view = SocialMediaView(self.bot, interaction.user.id, platform_name, sujet, content, image_url)
            await interaction.followup.send(content=msg_text, view=view)
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur lors de la génération IA : {e}")

async def setup(bot):
    await bot.add_cog(SocialCog(bot))
