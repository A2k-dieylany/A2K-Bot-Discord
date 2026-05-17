"""
╔══════════════════════════════════════════════════════════════╗
║   orchestrator/pm2_service.py — Gestionnaire PM2           ║
║   Cycle de vie complet des processus bots clients          ║
║   Génération ecosystem.config.js + commandes shell async   ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Répertoire racine où sont stockés les bots clients
CLIENTS_DIR = Path(os.getenv("CLIENTS_DIR", "clients"))
BOT_ENTRY_POINT = Path(__file__).parent.parent / "bot" / "worker.py"


class PM2Service:
    """
    Service d'orchestration des processus PM2.
    Chaque bot client est un processus Python isolé, piloté par PM2.
    
    PM2 garantit :
    - Redémarrage automatique en cas de crash (restart: always)
    - Logs centralisés (~/.pm2/logs/)
    - Monitoring CPU/RAM par processus
    - Déploiement zero-downtime (reload)
    """

    async def _run(self, *args: str) -> tuple[int, str, str]:
        """Exécute une commande shell async et retourne (returncode, stdout, stderr)."""
        import sys
        
        # Sur Windows, pm2 est un .cmd, subprocess.exec a besoin du nom exact sans shell=True
        cmd_args = list(args)
        if cmd_args[0] == "pm2" and sys.platform == "win32":
            cmd_args[0] = "pm2.cmd"
            
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode, stdout.decode(), stderr.decode()
        except FileNotFoundError:
            logger.warning(f"Commande introuvable: {cmd_args[0]}. PM2 est-il installe ?")
            return 1, "", f"Command not found: {cmd_args[0]}"

    def _get_client_dir(self, tenant_id: str) -> Path:
        """Retourne le répertoire dédié à ce client, le crée si nécessaire."""
        client_dir = CLIENTS_DIR / tenant_id
        client_dir.mkdir(parents=True, exist_ok=True)
        return client_dir

    def _write_env_file(self, tenant_id: str, config: dict) -> Path:
        """
        Génère le fichier .env isolé du bot client.
        Seules les valeurs en clair sont écrites (déchiffrement déjà fait par le caller).
        """
        client_dir = self._get_client_dir(tenant_id)
        env_path = client_dir / ".env"
        lines = [
            f"TENANT_ID={tenant_id}",
            f"WA_ID_INSTANCE={config.get('wa_instance', '')}",
            f"WA_API_TOKEN={config.get('wa_token', '')}",
            f"ADMIN_PHONE={config.get('admin_phone', '')}",
            f"BOT_NAME={config.get('name', 'MaxBot')}",
            f"BUSINESS_NAME={config.get('name', '')}",
            f"BUSINESS_INFO={config.get('business_info', '')}",
            f"GEMINI_API_KEY={config.get('gemini_key', os.getenv('GEMINI_API_KEY', ''))}",
            f"PORT={config.get('port', 8081)}",
            f"DATABASE_PATH={client_dir / 'memory.db'}",
            f"MAX_HISTORY=20",
        ]
        env_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"📄 .env généré pour tenant {tenant_id}")
        return env_path

    def _write_knowledge_file(self, tenant_id: str, knowledge: str) -> Path:
        """Génère le fichier de connaissances métier du bot client."""
        client_dir = self._get_client_dir(tenant_id)
        knowledge_path = client_dir / "connaissances.txt"
        knowledge_path.write_text(knowledge, encoding="utf-8")
        return knowledge_path

    def _write_ecosystem_config(self, tenant_id: str, port: int) -> Path:
        """
        Génère le fichier ecosystem.config.js pour PM2.
        Ce format est celui que PM2 utilise pour gérer les processus de façon robuste.
        """
        import sys
        client_dir = self._get_client_dir(tenant_id)
        ecosystem = {
            "apps": [{
                "name": f"bot_{tenant_id}",
                "script": str(BOT_ENTRY_POINT.resolve()),
                "interpreter": sys.executable,
                "cwd": str(client_dir),
                "env_file": str(client_dir / ".env"),
                "watch": False,
                "restart_delay": 3000,
                "max_restarts": 10,
                "out_file": str(client_dir / "logs" / "out.log"),
                "error_file": str(client_dir / "logs" / "error.log"),
                "merge_logs": True,
                "time": True,
            }]
        }
        (client_dir / "logs").mkdir(exist_ok=True)
        eco_path = client_dir / "ecosystem.config.json"
        eco_path.write_text(json.dumps(ecosystem, indent=2), encoding="utf-8")
        return eco_path

    async def start(self, tenant: dict) -> dict:
        """
        Lance le bot d'un client via PM2.
        Retourne le statut du processus.
        """
        tenant_id = tenant["id"]
        client_dir = self._get_client_dir(tenant_id)

        # 1. Générer les fichiers de configuration
        self._write_env_file(tenant_id, tenant)
        self._write_knowledge_file(
            tenant_id,
            tenant.get("business_info", "Aucune information.")
        )
        eco_path = self._write_ecosystem_config(tenant_id, tenant.get("port", 8081))

        # 2. Lancer via PM2
        returncode, stdout, stderr = await self._run(
            "pm2", "start", str(eco_path)
        )
        if returncode != 0:
            logger.error(f"❌ Échec démarrage PM2 pour {tenant_id}: {stderr}")
            raise RuntimeError(f"Impossible de démarrer le bot: {stderr}")

        logger.info(f"🚀 Bot {tenant_id} démarré sur port {tenant.get('port')}")
        return await self.status(tenant_id)

    async def stop(self, tenant_id: str) -> bool:
        """Arrête le processus PM2 du bot client."""
        returncode, _, stderr = await self._run("pm2", "stop", f"bot_{tenant_id}")
        if returncode != 0:
            logger.error(f"❌ Erreur arrêt {tenant_id}: {stderr}")
            return False
        logger.info(f"⏹️ Bot {tenant_id} arrêté.")
        return True

    async def restart(self, tenant_id: str) -> bool:
        """Redémarre le processus PM2 (zero-downtime)."""
        returncode, _, stderr = await self._run("pm2", "reload", f"bot_{tenant_id}")
        if returncode != 0:
            # Fallback: restart classique
            returncode, _, _ = await self._run("pm2", "restart", f"bot_{tenant_id}")
        return returncode == 0

    async def delete(self, tenant_id: str) -> bool:
        """Supprime complètement le processus PM2 du registre."""
        returncode, _, _ = await self._run("pm2", "delete", f"bot_{tenant_id}")
        return returncode == 0

    async def status(self, tenant_id: str) -> dict:
        """Retourne le statut détaillé d'un processus PM2 en JSON."""
        returncode, stdout, _ = await self._run(
            "pm2", "jlist"
        )
        if returncode != 0 or not stdout.strip():
            return {"name": f"bot_{tenant_id}", "status": "unknown", "cpu": 0, "memory": 0}

        try:
            processes = json.loads(stdout)
            for proc in processes:
                if proc.get("name") == f"bot_{tenant_id}":
                    monit = proc.get("monit", {})
                    return {
                        "name": proc["name"],
                        "status": proc.get("pm2_env", {}).get("status", "unknown"),
                        "cpu": monit.get("cpu", 0),
                        "memory": round(monit.get("memory", 0) / 1024 / 1024, 2),  # Mo
                        "uptime": proc.get("pm2_env", {}).get("pm_uptime"),
                        "restarts": proc.get("pm2_env", {}).get("restart_time", 0),
                    }
        except json.JSONDecodeError:
            pass

        return {"name": f"bot_{tenant_id}", "status": "offline", "cpu": 0, "memory": 0}

    async def status_all(self) -> list[dict]:
        """Retourne le statut de TOUS les bots actifs."""
        returncode, stdout, _ = await self._run("pm2", "jlist")
        if returncode != 0 or not stdout.strip():
            return []
        try:
            processes = json.loads(stdout)
            result = []
            for proc in processes:
                if proc.get("name", "").startswith("bot_"):
                    monit = proc.get("monit", {})
                    result.append({
                        "tenant_id": proc["name"].replace("bot_", ""),
                        "status": proc.get("pm2_env", {}).get("status", "unknown"),
                        "cpu": monit.get("cpu", 0),
                        "memory": round(monit.get("memory", 0) / 1024 / 1024, 2),
                        "restarts": proc.get("pm2_env", {}).get("restart_time", 0),
                    })
            return result
        except json.JSONDecodeError:
            return []

    async def get_logs(self, tenant_id: str, lines: int = 50) -> str:
        """Récupère les N dernières lignes de logs d'un bot client."""
        client_dir = CLIENTS_DIR / tenant_id / "logs" / "out.log"
        if not client_dir.exists():
            return "Aucun log disponible."
        returncode, stdout, _ = await self._run(
            "powershell", "-Command", f"Get-Content '{client_dir}' -Tail {lines}"
        )
        return stdout or "Logs vides."


# ── Instance singleton ───────────────────────────────────────────────────────
pm2_service = PM2Service()
