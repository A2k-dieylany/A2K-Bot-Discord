"""
╔══════════════════════════════════════════════════════════════╗
║   orchestrator/app.py — API Central (FastAPI)              ║
║   Control Plane: Admin CRUD + Webhook Router Multi-Tenant  ║
║   Sécurité: JWT Auth + Rate Limiting + CORS                ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn
import aiohttp

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.database import tenant_repo, conversation_repo, get_connection
from core.security import security
from orchestrator.pm2_service import pm2_service

# ── Configuration ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "change_this_secret_in_prod")

# ── Application FastAPI ──────────────────────────────────────────────────────
app = FastAPI(
    title="BotSaaS Orchestrator API",
    description="Control Plane pour la plateforme SaaS de bots WhatsApp IA",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS — En production, remplacer par le domaine exact du dashboard Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Authentification Simple (Bearer Token pour MVP) ─────────────────────────
def verify_admin(request: Request):
    """
    Middleware d'authentification admin basique.
    Phase 1 MVP : token secret statique.
    Phase 2 : Remplacer par JWT avec refresh tokens.
    """
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token != ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Accès non autorisé. Token invalide.",
        )
    return True

async def verify_green_api(instance_id: str, token: str) -> bool:
    """Vérifie si les identifiants Green API sont valides (renvoient 200)."""
    url = f"https://api.green-api.com/waInstance{instance_id}/getStateInstance/{token}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                return resp.status == 200
    except Exception:
        return False

# ── Schémas Pydantic (Validation des Données) ────────────────────────────────
class CreateTenantRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Nom de l'entreprise cliente")
    business_info: str = Field(..., min_length=10, description="Description des services du client")
    admin_phone: str = Field(..., pattern=r"^\d{10,15}$", description="Numéro WhatsApp sans le +")
    wa_instance: str = Field(..., description="ID Instance GreenAPI")
    wa_token: str = Field(..., description="Token GreenAPI")
    plan: str = Field("starter", pattern=r"^(trial|starter|business|pro)$")
    port: int = Field(8081, ge=8081, le=9999, description="Port HTTP unique pour ce bot")
    gemini_key: Optional[str] = Field(None, description="Clé Gemini dédiée (optionnel)")

class UpdateTenantRequest(BaseModel):
    status: Optional[str] = Field(None, pattern=r"^(trial|active|suspended|cancelled)$")
    plan: Optional[str] = Field(None, pattern=r"^(trial|starter|business|pro)$")

class UpdateTenantDataRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    business_info: str = Field(..., min_length=10)
    admin_phone: str = Field(..., pattern=r"^\d{10,15}$")
    wa_instance: str = Field(...)
    wa_token: str = Field(...)
    port: int = Field(..., ge=8081, le=9999)


# ════════════════════════════════════════════════════════════════
#  ROUTES ADMIN (Gestion des Tenants)
# ════════════════════════════════════════════════════════════════

@app.get("/api/v1/tenants", tags=["Admin"])
async def list_tenants(auth=Depends(verify_admin)):
    """Liste tous les clients avec leur statut PM2 en temps réel."""
    tenants = tenant_repo.get_all()
    try:
        pm2_statuses = {s["tenant_id"]: s for s in await pm2_service.status_all()}
    except Exception:
        pm2_statuses = {}

    for t in tenants:
        pm2_info = pm2_statuses.get(t["id"], {})
        t["bot_status"] = pm2_info.get("status", "offline")
        t["cpu"] = pm2_info.get("cpu", 0)
        t["memory_mb"] = pm2_info.get("memory", 0)
        t["restarts"] = pm2_info.get("restarts", 0)

    return {"tenants": tenants, "count": len(tenants)}


@app.post("/api/v1/tenants", status_code=201, tags=["Admin"])
async def create_tenant(payload: CreateTenantRequest, auth=Depends(verify_admin)):
    """
    Crée un nouveau client et déploie son bot automatiquement.
    Workflow: Validation → Création DB → Génération fichiers → Démarrage PM2
    """
    tenant_id = payload.name.lower().replace(" ", "_").replace("-", "_")[:20] + "_" + uuid.uuid4().hex[:6]

    # Vérification doublon de port
    all_tenants = tenant_repo.get_all()
    if any(t.get("port") == payload.port for t in all_tenants):
        raise HTTPException(
            status_code=400,
            detail=f"Le port {payload.port} est déjà utilisé par un autre bot. Choisissez un port différent."
        )

    # Validation Green API
    is_valid = await verify_green_api(payload.wa_instance, payload.wa_token)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Identifiants Green API invalides (Instance ou Token incorrect)."
        )

    try:
        # Création en base (credentials chiffrés automatiquement)
        tenant = tenant_repo.create(
            tenant_id=tenant_id,
            name=payload.name,
            business_info=payload.business_info,
            admin_phone=payload.admin_phone,
            wa_instance=payload.wa_instance,
            wa_token=payload.wa_token,
            plan=payload.plan,
            port=payload.port,
        )

        # Tentative de démarrage du bot via PM2 (best-effort)
        pm2_status = {"status": "pending"}
        try:
            pm2_status = await pm2_service.start(tenant)
        except Exception as pm2_err:
            logger.warning(f"PM2 non disponible, fichiers generes: {pm2_err}")
            pm2_status = {"status": "files_generated_pm2_unavailable"}

        logger.info(f"Nouveau tenant deploye: {tenant_id} sur port {payload.port}")
        return {
            "message": "Bot deploye avec succes !",
            "tenant_id": tenant_id,
            "port": payload.port,
            "webhook_url": f"Configure dans GreenAPI: http://YOUR_SERVER_IP:{payload.port}/notify",
            "bot_status": pm2_status,
        }
    except Exception as e:
        # Rollback: supprimer le tenant si la création DB a échoué
        try:
            tenant_repo.delete(tenant_id)
        except Exception:
            pass
        logger.error(f"Erreur deploiement tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du deploiement: {str(e)}")


@app.get("/api/v1/tenants/{tenant_id}", tags=["Admin"])
async def get_tenant(tenant_id: str, auth=Depends(verify_admin)):
    """Détails complets d'un client (sans les secrets)."""
    tenant = tenant_repo.get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Client introuvable.")
    tenant["bot_status"] = await pm2_service.status(tenant_id)
    tenant["analytics"] = conversation_repo.get_dashboard_data(tenant_id)
    return tenant


@app.delete("/api/v1/tenants/{tenant_id}", tags=["Admin"])
async def delete_tenant(tenant_id: str, auth=Depends(verify_admin)):
    """Supprime un client, arrête son bot et efface toutes ses données."""
    await pm2_service.delete(tenant_id)
    tenant_repo.delete(tenant_id)
    return {"message": f"Client {tenant_id} supprimé et bot arrêté."}


@app.post("/api/v1/tenants/{tenant_id}/restart", tags=["Admin"])
async def restart_bot(tenant_id: str, auth=Depends(verify_admin)):
    """Redémarre le bot d'un client (zero-downtime reload)."""
    ok = await pm2_service.restart(tenant_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Impossible de redémarrer le bot.")
    return {"message": f"Bot {tenant_id} redémarré avec succès."}

@app.post("/api/v1/tenants/{tenant_id}/stop", tags=["Admin"])
async def stop_bot(tenant_id: str, auth=Depends(verify_admin)):
    """Arrête le bot d'un client (suspension)."""
    await pm2_service.stop(tenant_id)
    # Même si le stop PM2 échoue (car process n'existe plus), on met à jour la base
    tenant_repo.update_status(tenant_id, "suspended")
    return {"message": f"Bot {tenant_id} arrêté et suspendu."}

@app.put("/api/v1/tenants/{tenant_id}", tags=["Admin"])
async def update_tenant_data(tenant_id: str, payload: UpdateTenantDataRequest, auth=Depends(verify_admin)):
    """Met à jour les infos du client et relance le bot pour appliquer les modifs."""
    # Vérifier le port
    all_tenants = tenant_repo.get_all()
    if any(t.get("port") == payload.port and t.get("id") != tenant_id for t in all_tenants):
        raise HTTPException(
            status_code=400,
            detail=f"Le port {payload.port} est déjà utilisé."
        )

    # Validation Green API
    is_valid = await verify_green_api(payload.wa_instance, payload.wa_token)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Identifiants Green API invalides."
        )

    tenant_repo.update(
        tenant_id=tenant_id,
        name=payload.name,
        business_info=payload.business_info,
        admin_phone=payload.admin_phone,
        wa_instance=payload.wa_instance,
        wa_token=payload.wa_token,
        port=payload.port
    )
    
    tenant = tenant_repo.get(tenant_id)
    # Re-générer les fichiers .env et .json
    pm2_service._write_env_file(tenant_id, tenant)
    pm2_service._write_knowledge_file(tenant_id, tenant.get("business_info", ""))
    
    # Redémarrer
    await pm2_service.restart(tenant_id)
    
    return {"message": "Client mis à jour et bot redémarré !"}


@app.get("/api/v1/tenants/{tenant_id}/logs", tags=["Admin"])
async def get_bot_logs(tenant_id: str, lines: int = 50, auth=Depends(verify_admin)):
    """Récupère les logs récents d'un bot client."""
    logs = await pm2_service.get_logs(tenant_id, lines)
    return {"tenant_id": tenant_id, "logs": logs}


# ════════════════════════════════════════════════════════════════
#  DASHBOARD HTML ADMIN (Interface Web intégrée)
# ════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse, tags=["UI"])
async def admin_dashboard():
    """Sert le Dashboard Admin (HTML/JS/CSS intégré)."""
    try:
        dashboard_path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "admin.html")
        with open(dashboard_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="""
            <h1>Dashboard Admin BotSaaS</h1>
            <p>Créez le fichier dashboard/admin.html pour activer l'interface graphique.</p>
            <p>API disponible sur <a href='/api/docs'>/api/docs</a></p>
        """)


# ════════════════════════════════════════════════════════════════
#  ENDPOINT SANTÉ (Health Check)
# ════════════════════════════════════════════════════════════════

@app.get("/health", tags=["System"])
async def health_check():
    """Endpoint de monitoring (Uptime Robot peut le pinguer)."""
    conn = get_connection()
    tenants_count = conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "tenants": tenants_count,
        "version": "1.0.0",
    }


# ════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv("ORCHESTRATOR_PORT", 5001))
    host = os.getenv("ORCHESTRATOR_HOST", "0.0.0.0")
    logger.info(f"🚀 Orchestrateur BotSaaS démarré → http://{host}:{port}")
    logger.info(f"📚 Documentation API → http://{host}:{port}/api/docs")
    uvicorn.run("orchestrator.app:app", host=host, port=port, reload=False, workers=1)
