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

    @app_commands.command(
        name="audit_site",
        description="🛡 Audit technique complet d'un site web — détecte failles, SEO, sécurité, performance"
    )
    @app_commands.describe(
        url="L'URL du site à auditer (ex: https://www.entreprise.com)"
    )
    async def cmd_audit_site(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer()

        # Étape 1 : Scan technique
        try:
            await interaction.followup.send(
                "🔬 **Scan technique en cours...**\n"
                "⏳ Analyse de : SSL, headers de sécurité, SEO, performance, mobile, technologies...",
                ephemeral=True
            )
            report = await scrape_website_technical(url)
        except Exception as e:
            await interaction.followup.send(
                f"❌ **Impossible d'auditer** `{url}`\nErreur : {e}"
            )
            return

        # Étape 2 : Résumé technique brut (embed avec les données factuelles)
        passed = sum(1 for k, v in {
            "SSL": report["ssl"],
            "Meta Desc": report["meta_description"] != "❌ ABSENT",
            "Titre": report["title"] != "❌ ABSENT",
            "Mobile": report["has_viewport"],
            "Favicon": report["has_favicon"],
            "robots.txt": report["has_robots_txt"],
            "sitemap.xml": report["has_sitemap"],
            "Analytics": report["has_analytics"],
            "Open Graph": report["has_og_tags"],
            "Schema": report["has_schema_markup"],
        }.items() if v)

        score_bar = "🟢" * passed + "🔴" * (10 - passed)
        tech_str = ", ".join(report["technologies_detected"][:8]) if report["technologies_detected"] else "Aucune"

        scan_embed = discord.Embed(
            title=f"🔬 Scan Technique — {url}",
            description=(
                f"**Score Checklist : {passed}/10** {score_bar}\n\n"
                f"⏱ Réponse : **{report['response_time_ms']}ms** | "
                f"📦 Taille : **{report['page_size_kb']} KB**\n"
                f"🛠 Technologies : {tech_str}"
            ),
            color=0x2ECC71 if passed >= 7 else (0xE67E22 if passed >= 4 else 0xE74C3C)
        )

        # Sécurité
        sec_status = []
        for h, v in report["security_headers"].items():
            status = "✅" if v != "❌ ABSENT" else "❌"
            sec_status.append(f"{status} {h.split('-')[-1]}")
        scan_embed.add_field(
            name="🔒 Sécurité (Headers)",
            value="\n".join(sec_status[:8]),
            inline=True
        )

        # SEO
        seo_checks = (
            f"{'✅' if report['title'] != '❌ ABSENT' else '❌'} Title\n"
            f"{'✅' if report['meta_description'] != '❌ ABSENT' else '❌'} Meta Desc\n"
            f"{'✅' if report['h1_tags'] else '❌'} H1 ({len(report['h1_tags'])})\n"
            f"{'✅' if report['has_robots_txt'] else '❌'} robots.txt\n"
            f"{'✅' if report['has_sitemap'] else '❌'} sitemap.xml\n"
            f"{'✅' if report['has_schema_markup'] else '❌'} Schema"
        )
        scan_embed.add_field(name="🔍 SEO", value=seo_checks, inline=True)

        # Mobile & Social
        misc = (
            f"{'✅' if report['has_viewport'] else '❌'} Mobile\n"
            f"{'✅' if report['ssl'] else '❌'} SSL/HTTPS\n"
            f"{'✅' if report['has_og_tags'] else '❌'} Open Graph\n"
            f"{'✅' if report['has_analytics'] else '❌'} Analytics\n"
            f"🖼 {report['images_without_alt']}/{report['images_total']} imgs sans alt"
        )
        scan_embed.add_field(name="📱 Mobile & Social", value=misc, inline=True)

        scan_embed.set_footer(text="⏳ Analyse IA détaillée en cours...")
        await interaction.followup.send(embed=scan_embed)

        # Étape 3 : Analyse IA approfondie
        prompt = get_technical_audit_prompt(report)

        try:
            analysis = await self.bot.gemini_generate(prompt)

            # Envoyer le rapport IA
            if len(analysis) <= 1990:
                await interaction.channel.send(f"## 🛡 Rapport d'Audit Complet\n\n{analysis}")
            else:
                parts = [analysis[i:i+1990] for i in range(0, len(analysis), 1990)]
                for i, part in enumerate(parts):
                    prefix = "## 🛡 Rapport d'Audit Complet\n\n" if i == 0 else ""
                    await interaction.channel.send(f"{prefix}{part}")

        except Exception as e:
            await interaction.channel.send(f"❌ Erreur lors de l'analyse IA : {e}")


# ══════════════════════════════════════════════════════════════
#  SCRAPER TECHNIQUE AVANCÉ (Audit de site)
# ══════════════════════════════════════════════════════════════

async def scrape_website_technical(url: str) -> dict:
    """Scrape un site web et collecte des données techniques détaillées."""
    if not url.startswith("http"):
        url = "https://" + url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    report = {
        "url": url,
        "ssl": False,
        "status_code": 0,
        "response_time_ms": 0,
        "title": "",
        "meta_description": "",
        "meta_keywords": "",
        "h1_tags": [],
        "h2_tags": [],
        "images_total": 0,
        "images_without_alt": 0,
        "internal_links": 0,
        "external_links": 0,
        "has_viewport": False,
        "has_favicon": False,
        "has_robots_txt": False,
        "has_sitemap": False,
        "has_analytics": False,
        "has_og_tags": False,
        "has_twitter_cards": False,
        "has_schema_markup": False,
        "has_ssl_redirect": False,
        "css_files": 0,
        "js_files": 0,
        "security_headers": {},
        "technologies_detected": [],
        "page_size_kb": 0,
        "text_content": "",
    }

    import time
    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        # ── 1. Requête principale ──
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20), allow_redirects=True) as resp:
                report["status_code"] = resp.status
                report["response_time_ms"] = round((time.time() - start_time) * 1000)
                report["ssl"] = str(resp.url).startswith("https")
                report["has_ssl_redirect"] = url.startswith("http://") and str(resp.url).startswith("https")

                # Headers de sécurité
                sec_headers = [
                    "Strict-Transport-Security", "Content-Security-Policy",
                    "X-Content-Type-Options", "X-Frame-Options",
                    "X-XSS-Protection", "Referrer-Policy",
                    "Permissions-Policy", "Access-Control-Allow-Origin"
                ]
                for h in sec_headers:
                    val = resp.headers.get(h)
                    report["security_headers"][h] = val if val else "❌ ABSENT"

                # Détection serveur
                server = resp.headers.get("Server", "")
                if server:
                    report["technologies_detected"].append(f"Serveur: {server}")
                powered_by = resp.headers.get("X-Powered-By", "")
                if powered_by:
                    report["technologies_detected"].append(f"Backend: {powered_by}")

                html = await resp.text()
                report["page_size_kb"] = round(len(html.encode('utf-8')) / 1024, 1)

        except Exception as e:
            raise Exception(f"Impossible de se connecter à {url}: {e}")

        # ── 2. robots.txt ──
        try:
            base_url = f"{resp.url.scheme}://{resp.url.host}"
            async with session.get(f"{base_url}/robots.txt", headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as r:
                report["has_robots_txt"] = r.status == 200
        except:
            pass

        # ── 3. sitemap.xml ──
        try:
            async with session.get(f"{base_url}/sitemap.xml", headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as r:
                report["has_sitemap"] = r.status == 200
        except:
            pass

    # ── 4. Parsing HTML ──
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title_tag = soup.find("title")
    report["title"] = title_tag.get_text(strip=True) if title_tag else "❌ ABSENT"

    # Meta Description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    report["meta_description"] = meta_desc["content"][:200] if meta_desc and meta_desc.get("content") else "❌ ABSENT"

    # Meta Keywords
    meta_kw = soup.find("meta", attrs={"name": "keywords"})
    report["meta_keywords"] = meta_kw["content"][:200] if meta_kw and meta_kw.get("content") else "❌ ABSENT"

    # H1 / H2
    report["h1_tags"] = [h.get_text(strip=True)[:100] for h in soup.find_all("h1")]
    report["h2_tags"] = [h.get_text(strip=True)[:80] for h in soup.find_all("h2")][:10]

    # Images
    images = soup.find_all("img")
    report["images_total"] = len(images)
    report["images_without_alt"] = sum(1 for img in images if not img.get("alt") or img.get("alt", "").strip() == "")

    # Links
    links = soup.find_all("a", href=True)
    for link in links:
        href = link["href"]
        if href.startswith("http") and resp.url.host not in href:
            report["external_links"] += 1
        else:
            report["internal_links"] += 1

    # Viewport (Mobile)
    viewport = soup.find("meta", attrs={"name": "viewport"})
    report["has_viewport"] = viewport is not None

    # Favicon
    favicon = soup.find("link", rel=lambda x: x and "icon" in " ".join(x).lower() if x else False)
    report["has_favicon"] = favicon is not None

    # Open Graph
    og_tag = soup.find("meta", property=re.compile(r"^og:"))
    report["has_og_tags"] = og_tag is not None

    # Twitter Cards
    tw_tag = soup.find("meta", attrs={"name": re.compile(r"^twitter:")})
    report["has_twitter_cards"] = tw_tag is not None

    # Schema.org / JSON-LD
    schema = soup.find("script", type="application/ld+json")
    report["has_schema_markup"] = schema is not None

    # Analytics / Tracking
    html_lower = html.lower()
    if "google-analytics" in html_lower or "gtag" in html_lower or "ga(" in html_lower:
        report["has_analytics"] = True
        report["technologies_detected"].append("Google Analytics")
    if "facebook.com/tr" in html_lower or "fbq(" in html_lower:
        report["technologies_detected"].append("Facebook Pixel")
    if "hotjar" in html_lower:
        report["technologies_detected"].append("Hotjar")

    # CMS Detection
    if "wp-content" in html_lower or "wordpress" in html_lower:
        report["technologies_detected"].append("WordPress")
    elif "shopify" in html_lower:
        report["technologies_detected"].append("Shopify")
    elif "wix.com" in html_lower:
        report["technologies_detected"].append("Wix")
    elif "squarespace" in html_lower:
        report["technologies_detected"].append("Squarespace")
    elif "webflow" in html_lower:
        report["technologies_detected"].append("Webflow")

    # Framework JS
    if "react" in html_lower or "__next" in html_lower:
        report["technologies_detected"].append("React/Next.js")
    elif "vue" in html_lower or "__nuxt" in html_lower:
        report["technologies_detected"].append("Vue/Nuxt")

    # CSS / JS count
    report["css_files"] = len(soup.find_all("link", rel="stylesheet"))
    report["js_files"] = len(soup.find_all("script", src=True))

    # Texte pour contexte IA
    for tag in soup(["script", "style", "nav", "footer", "noscript", "iframe", "svg"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    report["text_content"] = "\n".join(lines)[:5000]

    return report


def get_technical_audit_prompt(report: dict) -> str:
    """Prompt IA pour générer un rapport d'audit technique complet."""

    # Formatter les headers de sécurité
    sec_lines = "\n".join([f"  - {k}: {v}" for k, v in report["security_headers"].items()])

    # Formatter les technologies
    tech_str = ", ".join(report["technologies_detected"]) if report["technologies_detected"] else "Aucune détectée"

    # Calculer un score rapide
    checks = {
        "SSL": report["ssl"],
        "Meta Description": report["meta_description"] != "❌ ABSENT",
        "Titre": report["title"] != "❌ ABSENT",
        "Viewport Mobile": report["has_viewport"],
        "Favicon": report["has_favicon"],
        "robots.txt": report["has_robots_txt"],
        "sitemap.xml": report["has_sitemap"],
        "Analytics": report["has_analytics"],
        "Open Graph": report["has_og_tags"],
        "Schema Markup": report["has_schema_markup"],
    }
    passed = sum(1 for v in checks.values() if v)
    checklist = "\n".join([f"  {'✅' if v else '❌'} {k}" for k, v in checks.items()])

    h1_list = ", ".join(report["h1_tags"][:5]) if report["h1_tags"] else "❌ AUCUN H1"
    h2_list = ", ".join(report["h2_tags"][:5]) if report["h2_tags"] else "Aucun H2 trouvé"

    return (
        f"Tu es un expert en audit technique de sites web pour l'agence Sen Digital Solution.\n\n"
        f"DONNÉES TECHNIQUES COLLECTÉES SUR LE SITE : {report['url']}\n"
        f"══════════════════════════════════════════\n"
        f"⏱ Temps de réponse : {report['response_time_ms']}ms\n"
        f"📦 Taille de la page : {report['page_size_kb']} KB\n"
        f"🔒 SSL/HTTPS : {'✅ Oui' if report['ssl'] else '❌ Non'}\n"
        f"🔄 Redirection HTTP→HTTPS : {'✅ Oui' if report['has_ssl_redirect'] else '❌ Non'}\n"
        f"📱 Viewport Mobile : {'✅ Oui' if report['has_viewport'] else '❌ Non'}\n"
        f"🖼 Favicon : {'✅ Oui' if report['has_favicon'] else '❌ Non'}\n\n"
        f"📊 SEO :\n"
        f"  Titre : {report['title']}\n"
        f"  Meta Description : {report['meta_description']}\n"
        f"  H1 : {h1_list}\n"
        f"  H2 : {h2_list}\n"
        f"  robots.txt : {'✅' if report['has_robots_txt'] else '❌'}\n"
        f"  sitemap.xml : {'✅' if report['has_sitemap'] else '❌'}\n"
        f"  Schema Markup : {'✅' if report['has_schema_markup'] else '❌'}\n\n"
        f"🖼 Images : {report['images_total']} total, {report['images_without_alt']} sans alt\n"
        f"🔗 Liens : {report['internal_links']} internes, {report['external_links']} externes\n"
        f"📂 Ressources : {report['css_files']} CSS, {report['js_files']} JS\n\n"
        f"📣 Réseaux sociaux :\n"
        f"  Open Graph : {'✅' if report['has_og_tags'] else '❌'}\n"
        f"  Twitter Cards : {'✅' if report['has_twitter_cards'] else '❌'}\n"
        f"  Analytics : {'✅' if report['has_analytics'] else '❌'}\n\n"
        f"🛡 Headers de Sécurité :\n{sec_lines}\n\n"
        f"🛠 Technologies détectées : {tech_str}\n\n"
        f"📋 Checklist rapide ({passed}/10) :\n{checklist}\n\n"
        f"Contenu texte (extrait) :\n{report['text_content'][:3000]}\n\n"
        f"══════════════════════════════════════════\n"
        f"MISSION : Génère un **Rapport d'Audit Technique Complet** en suivant ce format :\n\n"
        f"## 🏆 Score Global : X/100\n"
        f"Un score basé sur les données ci-dessus. Affiche une barre de progression avec des emojis.\n\n"
        f"## ⚡ Performance\n"
        f"Analyse du temps de réponse, taille de la page, nombre de ressources. Recommandations.\n\n"
        f"## 🔒 Sécurité (CRITIQUE)\n"
        f"Analyse de chaque header de sécurité manquant. Explique les RISQUES concrets (piratage, injection, clickjacking). Classe par gravité (🔴 Critique / 🟡 Moyen / 🟢 OK).\n\n"
        f"## 📱 Mobile & Responsive\n"
        f"Analyse de la compatibilité mobile.\n\n"
        f"## 🔍 SEO (Search Engine Optimization)\n"
        f"Analyse complète : title, meta, H1, H2, images alt, robots.txt, sitemap, schema. Note chaque critère.\n\n"
        f"## 📣 Présence Sociale & Tracking\n"
        f"Open Graph, Twitter Cards, Analytics, Pixels.\n\n"
        f"## 🔴 Top 5 des Failles Critiques\n"
        f"Les 5 problèmes les plus graves, classés par impact business. Pour chacun :\n"
        f"- 🔴 **Faille** : Description\n"
        f"- 💰 **Impact** : Conséquence financière/business\n"
        f"- 🔧 **Correction** : Comment SDS peut résoudre ça\n\n"
        f"## 💰 Devis Estimatif\n"
        f"Propose une fourchette de prix pour corriger toutes les failles (par SDS).\n\n"
        f"⚠️ IMPORTANT : Sois technique et précis. Utilise les données réelles collectées ci-dessus. "
        f"Ce rapport sera présenté AU PROSPECT pour le convaincre. Il doit être impressionnant et factuel."
    )


# ══════════════════════════════════════════════════════════════
#  COG PRINCIPAL (suite) — Commande Audit Technique
# ══════════════════════════════════════════════════════════════

# (La commande est ajoutée dans le Cog existant ci-dessous)


async def setup(bot):
    await bot.add_cog(ProspectsCog(bot))
