"""
╔══════════════════════════════════════════════════════════════╗
║     🎯 COG PROSPECTS — Analyse & Approche Commerciale B2B   ║
║     Module d'intelligence commerciale pour Sen Digital Sol.  ║
╚══════════════════════════════════════════════════════════════╝
"""

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from bs4 import BeautifulSoup
import re


# ══════════════════════════════════════════════════════════════
#  PROMPTS IA SPÉCIALISÉS PROSPECTION
# ══════════════════════════════════════════════════════════════

def get_prospect_analysis_prompt(site_text: str, url: str) -> str:
    """Prompt pour analyser un site web et générer une fiche prospect."""
    return (
        f"Tu es un expert en analyse commerciale B2B pour l'agence Sen Digital Solution (SDS).\n\n"
        f"Voici le texte extrait du site web du prospect ({url}) :\n"
        f"---\n{site_text[:6000]}\n---\n\n"
        f"MISSION : Génère une **Fiche Prospect Complète** en suivant ce format EXACT :\n\n"
        f"## 🏢 Entreprise\n"
        f"- **Nom** : (déduit du site)\n"
        f"- **Secteur** : (ex: Restauration, Mode, BTP...)\n"
        f"- **Localisation** : (si trouvée)\n"
        f"- **Résumé** : (1-2 phrases sur ce qu'ils font)\n\n"
        f"## 🔍 Diagnostic Digital\n"
        f"Analyse critique du site : design, UX, SEO, contenu, e-commerce, présence réseaux sociaux.\n"
        f"Note chaque critère sur 10 avec un emoji (🟢 bon, 🟡 moyen, 🔴 mauvais).\n\n"
        f"## 💡 Problèmes Identifiés (Framework PAS)\n"
        f"Liste les 3 problèmes business les plus graves que SDS pourrait résoudre.\n"
        f"Pour chaque problème : Problème → Agitation (conséquence financière) → Solution SDS.\n\n"
        f"## 🎯 Score de Qualification\n"
        f"- **Score** : X/100 (probabilité de conversion en client SDS)\n"
        f"- **Priorité** : 🔥 Chaud / 🟡 Tiède / 🔵 Froid\n"
        f"- **Budget estimé** : Fourchette de prix pour les services SDS recommandés\n\n"
        f"## 📧 Messages d'Approche (Prêts à Envoyer)\n\n"
        f"### LinkedIn (Message de connexion — max 300 caractères)\n"
        f"Un message court, direct et personnalisé.\n\n"
        f"### Email de Prospection (Cold Email — Framework AIDA)\n"
        f"Objet percutant + corps du mail. Ton : expert, pas vendeur. Max 150 mots.\n\n"
        f"### Script d'Appel Téléphonique (30 secondes)\n"
        f"Un script naturel et conversationnel pour un premier appel.\n\n"
        f"⚠️ IMPORTANT : Sois spécifique au prospect. INTERDIT de rester générique. "
        f"Chaque message doit contenir des références concrètes à leur activité."
    )


def get_prospect_manual_prompt(entreprise: str, secteur: str, probleme: str) -> str:
    """Prompt pour générer une approche commerciale à partir d'infos manuelles."""
    return (
        f"Tu es un expert en prospection commerciale B2B pour l'agence Sen Digital Solution (SDS).\n\n"
        f"INFORMATIONS SUR LE PROSPECT :\n"
        f"- **Entreprise** : {entreprise}\n"
        f"- **Secteur** : {secteur}\n"
        f"- **Problème/Besoin identifié** : {probleme}\n\n"
        f"MISSION : Génère les éléments d'approche suivants :\n\n"
        f"## 🎯 Qualification Rapide\n"
        f"- **Score** : X/100\n"
        f"- **Priorité** : 🔥 Chaud / 🟡 Tiède / 🔵 Froid\n"
        f"- **Services SDS recommandés** : (site web, automatisation, IA, marketing...)\n"
        f"- **Budget estimé** : Fourchette réaliste\n\n"
        f"## 💡 Analyse du Besoin (Framework PAS)\n"
        f"Problème → Agitation (conséquence financière si rien n'est fait) → Solution SDS concrète.\n\n"
        f"## 📧 Messages d'Approche (Prêts à Envoyer)\n\n"
        f"### LinkedIn (Message de connexion — max 300 caractères)\n"
        f"Court, direct, personnalisé.\n\n"
        f"### Email de Prospection (Cold Email — Framework AIDA)\n"
        f"Objet percutant + corps du mail. Max 150 mots.\n\n"
        f"### Message WhatsApp (Approche directe — max 3 lignes)\n"
        f"Naturel, chaleureux, professionnel.\n\n"
        f"⚠️ IMPORTANT : Sois ultra-spécifique. Chaque message doit mentionner le nom de l'entreprise "
        f"et faire référence à leur situation concrète. INTERDIT d'être générique."
    )


# ══════════════════════════════════════════════════════════════
#  WEB SCRAPER (Extraction de texte depuis un site web)
# ══════════════════════════════════════════════════════════════

async def scrape_website(url: str) -> str:
    """Extrait le texte principal d'un site web."""
    if not url.startswith("http"):
        url = "https://" + url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                raise Exception(f"Le site a répondu avec le code HTTP {resp.status}")
            html = await resp.text()

    soup = BeautifulSoup(html, "html.parser")

    # Supprimer les éléments non pertinents
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe", "svg"]):
        tag.decompose()

    # Extraire le texte
    text = soup.get_text(separator="\n", strip=True)

    # Nettoyer les lignes vides excessives
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)

    # Extraire aussi les méta-données utiles
    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_desc = f"Meta Description: {meta_tag['content']}\n"

    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = f"Titre du site: {title_tag.get_text()}\n"

    return f"{title}{meta_desc}\n{clean_text[:8000]}"


# ══════════════════════════════════════════════════════════════
#  VIEWS INTERACTIVES
# ══════════════════════════════════════════════════════════════

class ProspectApprovalView(discord.ui.View):
    """Boutons pour envoyer directement le message d'approche via WhatsApp."""
    def __init__(self, user_id: int, linkedin_msg: str, email_msg: str, wa_msg: str = None):
        super().__init__(timeout=86400)
        self.user_id = user_id
        self.linkedin_msg = linkedin_msg
        self.email_msg = email_msg
        self.wa_msg = wa_msg

    @discord.ui.button(label="📋 Copier LinkedIn", style=discord.ButtonStyle.primary)
    async def btn_linkedin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Tu n'es pas l'auteur.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"📋 **Message LinkedIn (copie-colle):**\n```\n{self.linkedin_msg}\n```",
            ephemeral=True
        )

    @discord.ui.button(label="📧 Copier Email", style=discord.ButtonStyle.secondary)
    async def btn_email(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Tu n'es pas l'auteur.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"📧 **Email de prospection (copie-colle):**\n```\n{self.email_msg}\n```",
            ephemeral=True
        )

    @discord.ui.button(label="🔄 Regénérer", style=discord.ButtonStyle.success)
    async def btn_regenerate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Tu n'es pas l'auteur.", ephemeral=True)
            return
        await interaction.response.send_message(
            "💡 Utilise la même commande pour regénérer une analyse avec un angle différent !",
            ephemeral=True
        )


# ══════════════════════════════════════════════════════════════
#  COG PRINCIPAL
# ══════════════════════════════════════════════════════════════

class ProspectsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="prospect_url",
        description="🎯 Analyse le site web d'un prospect et génère une approche commerciale complète"
    )
    @app_commands.describe(
        url="L'URL du site web du prospect (ex: https://www.entreprise.com)"
    )
    async def cmd_prospect_url(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()

        # Étape 1 : Scraper le site
        try:
            await interaction.followup.send("🔍 **Étape 1/2** — Analyse du site web en cours...", ephemeral=True)
            site_text = await scrape_website(url)
        except Exception as e:
            await interaction.followup.send(
                f"❌ **Impossible de lire le site** `{url}`\n"
                f"Erreur : {e}\n\n"
                f"💡 Essaie `/prospect_manuel` pour entrer les infos manuellement."
            )
            return

        # Étape 2 : Analyse IA
        prompt = get_prospect_analysis_prompt(site_text, url)

        try:
            analysis = await self.bot.gemini_generate(prompt)

            # Extraire les messages d'approche pour les boutons
            linkedin_msg = self._extract_section(analysis, "LinkedIn")
            email_msg = self._extract_section(analysis, "Email")

            # Construire l'embed
            embed = discord.Embed(
                title=f"🎯 Fiche Prospect — {url}",
                description=analysis[:4096],
                color=0xFF6B35
            )
            embed.set_footer(text=f"Analysé par {self.bot.user.name} | Sen Digital Solution")

            view = ProspectApprovalView(
                interaction.user.id,
                linkedin_msg,
                email_msg
            )

            await interaction.followup.send(embed=embed, view=view)

            # Si l'analyse dépasse 4096 caractères, envoyer la suite
            if len(analysis) > 4096:
                remaining = analysis[4096:]
                parts = [remaining[i:i+1990] for i in range(0, len(remaining), 1990)]
                for part in parts:
                    await interaction.channel.send(part)

        except Exception as e:
            await interaction.followup.send(f"❌ Erreur lors de l'analyse IA : {e}")

    @app_commands.command(
        name="prospect_manuel",
        description="🎯 Génère une approche commerciale B2B à partir d'infos manuelles"
    )
    @app_commands.describe(
        entreprise="Nom de l'entreprise (ex: Boutique Aminata)",
        secteur="Secteur d'activité (ex: Mode, Restauration, BTP...)",
        probleme="Problème ou besoin identifié (ex: Pas de site web, pas de visibilité en ligne)"
    )
    async def cmd_prospect_manuel(
        self,
        interaction: discord.Interaction,
        entreprise: str,
        secteur: str,
        probleme: str
    ):
        await interaction.response.defer()

        prompt = get_prospect_manual_prompt(entreprise, secteur, probleme)

        try:
            analysis = await self.bot.gemini_generate(prompt)

            # Extraire les messages pour les boutons
            linkedin_msg = self._extract_section(analysis, "LinkedIn")
            email_msg = self._extract_section(analysis, "Email")
            wa_msg = self._extract_section(analysis, "WhatsApp")

            embed = discord.Embed(
                title=f"🎯 Approche Commerciale — {entreprise}",
                description=analysis[:4096],
                color=0x2ECC71
            )
            embed.set_footer(text=f"Généré par {self.bot.user.name} | Sen Digital Solution")

            view = ProspectApprovalView(
                interaction.user.id,
                linkedin_msg,
                email_msg,
                wa_msg
            )

            await interaction.followup.send(embed=embed, view=view)

            if len(analysis) > 4096:
                remaining = analysis[4096:]
                parts = [remaining[i:i+1990] for i in range(0, len(remaining), 1990)]
                for part in parts:
                    await interaction.channel.send(part)

        except Exception as e:
            await interaction.followup.send(f"❌ Erreur lors de la génération : {e}")

    def _extract_section(self, text: str, keyword: str) -> str:
        """Extrait une section de texte basée sur un mot-clé (LinkedIn, Email, WhatsApp)."""
        lines = text.split("\n")
        capture = False
        result = []
        for line in lines:
            if keyword.lower() in line.lower() and ("###" in line or "**" in line):
                capture = True
                continue
            elif capture and line.startswith("###"):
                break
            elif capture and line.startswith("## "):
                break
            elif capture:
                result.append(line)

        extracted = "\n".join(result).strip()
        return extracted if extracted else f"(Section {keyword} non trouvée — consulte l'analyse complète)"


async def setup(bot):
    await bot.add_cog(ProspectsCog(bot))
