"""
╔══════════════════════════════════════════════════════════════╗
║   run_orchestrator.py — Point d'Entrée Unifié              ║
║   Lance l'API Orchestrateur (FastAPI) + health monitoring  ║
╚══════════════════════════════════════════════════════════════╝
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from orchestrator.app import app
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("ORCHESTRATOR_PORT", 5001))
    print(f"""
============================================================
  BotSaaS Orchestrateur -- Demarrage
------------------------------------------------------------
  Dashboard Admin : http://localhost:{port}
  API Docs        : http://localhost:{port}/api/docs
  Health Check    : http://localhost:{port}/health
============================================================
""")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
