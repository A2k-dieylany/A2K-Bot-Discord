import os
import shutil
from aiohttp import web

# Dossier où seront stockés les configurations des clients
CLIENTS_DIR = "clients"
if not os.path.exists(CLIENTS_DIR):
    os.makedirs(CLIENTS_DIR)

async def index(request):
    """Affiche le Dashboard d'administration SaaS (Phase 1 MVP)."""
    with open("saas_dashboard.html", "r", encoding="utf-8") as f:
        html = f.read()
    return web.Response(text=html, content_type='text/html')

async def create_client(request):
    """Reçoit le formulaire et génère les fichiers pour le nouveau bot client."""
    data = await request.post()
    client_id = data.get("client_id", "").strip().lower().replace(" ", "_")
    business_name = data.get("business_name", "").strip()
    business_info = data.get("business_info", "").strip()
    admin_phone = data.get("admin_phone", "").strip()
    wa_id_instance = data.get("wa_id_instance", "").strip()
    wa_api_token = data.get("wa_api_token", "").strip()
    port = data.get("port", "8081").strip()

    if not client_id:
        return web.Response(text="Erreur : L'ID client est requis.", status=400)

    # Créer le dossier du client
    client_path = os.path.join(CLIENTS_DIR, client_id)
    if not os.path.exists(client_path):
        os.makedirs(client_path)

    # 1. Générer le .env
    env_content = f"""# ════════════════════════════════════════
# Configuration du Bot pour {business_name}
# ════════════════════════════════════════

DISCORD_TOKEN=
GEMINI_API_KEY=AIzaSyDR4x7ZYm6pWZEpMVnY77DtgekrLqT7urk
BOT_NAME={client_id}_bot
MAX_HISTORY=20

WA_ID_INSTANCE={wa_id_instance}
WA_API_TOKEN={wa_api_token}
WA_LOG_CHANNEL=0

BUSINESS_NAME="{business_name}"
BUSINESS_INFO="{business_info}"
ADMIN_PHONE="{admin_phone}"
"""
    with open(os.path.join(client_path, ".env"), "w", encoding="utf-8") as f:
        f.write(env_content)

    # 2. Générer le connaissances.txt
    connaissances_content = f"""# BASE DE CONNAISSANCES DE {business_name.upper()}
{business_info}

[Insérez ici le menu, les tarifs, ou d'autres règles métiers spécifiques au client]
"""
    with open(os.path.join(client_path, "connaissances.txt"), "w", encoding="utf-8") as f:
        f.write(connaissances_content)

    # 3. Générer le docker-compose.yml spécifique au client
    docker_content = f"""version: '3.8'
services:
  bot_{client_id}:
    build: 
      context: ../../
      dockerfile: Dockerfile
    container_name: bot_{client_id}
    restart: always
    ports:
      - "{port}:8080"
    volumes:
      - ./.env:/app/.env
      - ./connaissances.txt:/app/connaissances.txt
      # La base de données est stockée localement dans le dossier client
      - ./memory.db:/app/memory.db
"""
    with open(os.path.join(client_path, "docker-compose.yml"), "w", encoding="utf-8") as f:
        f.write(docker_content)

    success_msg = f"""
    <h2>✅ Bot généré avec succès pour {business_name} !</h2>
    <p>Les fichiers ont été créés dans le dossier : <b>clients/{client_id}</b></p>
    <br/>
    <h3>🚀 Comment lancer ce bot (Phase 1) :</h3>
    <p>Ouvre ton terminal et tape :</p>
    <pre style="background:#eee; padding:10px; border-radius:5px;">cd clients/{client_id}
docker-compose up -d</pre>
    <p>Le bot écoutera sur le port <b>{port}</b>. N'oublie pas de configurer le webhook sur Green API :<br/>
    <code>http://TON_IP_VPS:{port}/notify</code></p>
    <br/>
    <a href="/">Retour au Dashboard</a>
    """
    return web.Response(text=success_msg, content_type='text/html')

app = web.Application()
app.router.add_get('/', index)
app.router.add_post('/create', create_client)

if __name__ == '__main__':
    print("🚀 SaaS Admin MVP lancé sur http://localhost:5000")
    web.run_app(app, port=5000)
