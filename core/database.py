"""
╔══════════════════════════════════════════════════════════════╗
║   core/database.py — Couche Données (SQLite Multi-Tenant)  ║
║   Architecture: Repository Pattern + Migration Automatique  ║
║   Conçu pour migration future vers PostgreSQL               ║
╚══════════════════════════════════════════════════════════════╝
"""

import sqlite3
import os
import logging
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

from .security import security

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DATABASE_PATH", "saas.db")


# ── Pool de connexions thread-safe ──────────────────────────────────────────
_connection: Optional[sqlite3.Connection] = None

def get_connection() -> sqlite3.Connection:
    """Retourne la connexion SQLite singleton (thread-safe en mode WAL)."""
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        _connection.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging pour concurrence
        _connection.execute("PRAGMA foreign_keys=ON")
        _connection.row_factory = sqlite3.Row
        _init_schema(_connection)
    return _connection


@contextmanager
def db_transaction():
    """Context manager garantissant atomicité des transactions."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Transaction DB annulée (rollback): {e}")
        raise


# ── Migrations de Schéma ────────────────────────────────────────────────────
def _init_schema(conn: sqlite3.Connection):
    """
    Initialise/migre le schéma de la base de données.
    Chaque table est versionnée. La colonne tenant_id garantit l'isolation multi-tenant.
    """
    c = conn.cursor()

    # Table Tenants (les clients SaaS)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id          TEXT PRIMARY KEY,              -- UUID unique du client
            name        TEXT NOT NULL,                 -- Nom de l'entreprise
            business_info TEXT NOT NULL DEFAULT '',    -- Description des services
            plan        TEXT NOT NULL DEFAULT 'starter', -- essai/starter/business/pro
            status      TEXT NOT NULL DEFAULT 'trial', -- trial/active/suspended/cancelled
            port        INTEGER UNIQUE,                -- Port HTTP du bot (pour webhook)
            admin_phone TEXT NOT NULL,                 -- Numéro WhatsApp de l'admin client
            wa_instance_enc TEXT,                      -- ID Instance GreenAPI (CHIFFRÉ)
            wa_token_enc    TEXT,                      -- Token GreenAPI (CHIFFRÉ)
            gemini_key_enc  TEXT,                      -- Clé Gemini (CHIFFRÉ, optionnel)
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at  DATETIME,                      -- Date fin d'essai ou prochain paiement
            last_active DATETIME
        )
    """)

    # Table Conversations (multi-tenant, remplace wa_memory)
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id   TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            phone       TEXT NOT NULL,                 -- Numéro du client final (hash pour logs)
            role        TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content     TEXT NOT NULL,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Index de performance sur les requêtes fréquentes
    c.execute("CREATE INDEX IF NOT EXISTS idx_conv_tenant_phone ON conversations(tenant_id, phone)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_conv_timestamp ON conversations(timestamp)")

    # Table Settings (remplacement wa_settings)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tenant_settings (
            tenant_id   TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            phone       TEXT NOT NULL,
            ai_paused   INTEGER DEFAULT 0,
            PRIMARY KEY (tenant_id, phone)
        )
    """)

    # Table Follow-ups (relances automatiques)
    c.execute("""
        CREATE TABLE IF NOT EXISTS followups (
            tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            phone           TEXT NOT NULL,
            last_bot_msg    DATETIME,
            status          TEXT DEFAULT 'pending',
            PRIMARY KEY (tenant_id, phone)
        )
    """)

    # Table Audit Log (toutes les actions importantes)
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id   TEXT,
            action      TEXT NOT NULL,
            details     TEXT,
            ip_address  TEXT,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    logger.info("✅ Schéma de base de données initialisé/vérifié.")


# ════════════════════════════════════════════════════════════════
#  REPOSITORY PATTERN
#  Abstraction des requêtes SQL — permet de migrer vers PostgreSQL
#  sans changer la logique métier.
# ════════════════════════════════════════════════════════════════

class TenantRepository:
    """Gestion CRUD des clients SaaS avec chiffrement automatique des secrets."""

    def create(self, tenant_id: str, name: str, business_info: str,
               admin_phone: str, wa_instance: str, wa_token: str,
               plan: str = "starter", port: int = 8081) -> dict:
        """
        Crée un nouveau client.
        Les credentials WhatsApp sont AUTOMATIQUEMENT chiffrés avant insertion.
        """
        with db_transaction() as conn:
            conn.execute("""
                INSERT INTO tenants (id, name, business_info, admin_phone, plan,
                                     wa_instance_enc, wa_token_enc, port, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'trial')
            """, (
                tenant_id, name, business_info, admin_phone, plan,
                security.encrypt(wa_instance),
                security.encrypt(wa_token),
                port
            ))
        self._audit("CREATE_TENANT", tenant_id, f"Nouveau client: {name}")
        logger.info(f"✅ Tenant créé: {name} (ID: {tenant_id})")
        return self.get(tenant_id)

    def get(self, tenant_id: str) -> Optional[dict]:
        """Retourne un client avec ses credentials DÉCHIFFRÉS."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM tenants WHERE id = ?", (tenant_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        # Déchiffrement à la volée des secrets
        if result.get("wa_instance_enc"):
            result["wa_instance"] = security.decrypt(result["wa_instance_enc"])
        if result.get("wa_token_enc"):
            result["wa_token"] = security.decrypt(result["wa_token_enc"])
        # On ne retourne JAMAIS les colonnes chiffrées brutes
        del result["wa_instance_enc"]
        del result["wa_token_enc"]
        if result.get("gemini_key_enc"):
            result["gemini_key"] = security.decrypt(result["gemini_key_enc"])
            del result["gemini_key_enc"]
        return result

    def update(self, tenant_id: str, name: str, business_info: str,
               admin_phone: str, wa_instance: str, wa_token: str, port: int) -> dict:
        """Met à jour un client existant."""
        with db_transaction() as conn:
            conn.execute("""
                UPDATE tenants SET 
                    name = ?, business_info = ?, admin_phone = ?, port = ?,
                    wa_instance_enc = ?, wa_token_enc = ?
                WHERE id = ?
            """, (
                name, business_info, admin_phone, port,
                security.encrypt(wa_instance),
                security.encrypt(wa_token),
                tenant_id
            ))
        self._audit("UPDATE_TENANT", tenant_id, f"Mise à jour client: {name}")
        return self.get(tenant_id)

    def get_all(self) -> list[dict]:
        """Retourne tous les tenants (sans déchiffrer les secrets pour la liste)."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, name, plan, status, port, admin_phone, created_at, last_active FROM tenants"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_status(self, tenant_id: str, status: str):
        """Met à jour le statut d'abonnement d'un client."""
        with db_transaction() as conn:
            conn.execute(
                "UPDATE tenants SET status = ? WHERE id = ?", (status, tenant_id)
            )
        self._audit("UPDATE_STATUS", tenant_id, f"Statut -> {status}")

    def update_last_active(self, tenant_id: str):
        """Met à jour le timestamp de dernière activité."""
        conn = get_connection()
        conn.execute(
            "UPDATE tenants SET last_active = CURRENT_TIMESTAMP WHERE id = ?",
            (tenant_id,)
        )
        conn.commit()

    def delete(self, tenant_id: str):
        """Supprime un client et TOUTES ses données (CASCADE)."""
        with db_transaction() as conn:
            conn.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))
        self._audit("DELETE_TENANT", tenant_id, "Suppression complète du tenant")
        logger.warning(f"⚠️ Tenant supprimé: {tenant_id}")

    def _audit(self, action: str, tenant_id: str, details: str = ""):
        """Enregistre une action dans le journal d'audit."""
        conn = get_connection()
        conn.execute(
            "INSERT INTO audit_log (tenant_id, action, details) VALUES (?, ?, ?)",
            (tenant_id, action, details)
        )
        conn.commit()


class ConversationRepository:
    """Gestion des messages de conversation par tenant et par numéro client."""

    def add_message(self, tenant_id: str, phone: str, role: str, content: str):
        """Ajoute un message à l'historique du client final."""
        with db_transaction() as conn:
            conn.execute("""
                INSERT INTO conversations (tenant_id, phone, role, content)
                VALUES (?, ?, ?, ?)
            """, (tenant_id, phone, role, content))

    def get_history(self, tenant_id: str, phone: str, limit: int = 20) -> list[dict]:
        """Récupère l'historique de conversation pour l'API Gemini."""
        conn = get_connection()
        rows = conn.execute("""
            SELECT role, content, timestamp FROM conversations
            WHERE tenant_id = ? AND phone = ?
            ORDER BY timestamp DESC LIMIT ?
        """, (tenant_id, phone, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]  # Chronologique

    def get_ai_paused(self, tenant_id: str, phone: str) -> bool:
        """Vérifie si l'IA est en pause pour ce client final."""
        conn = get_connection()
        row = conn.execute(
            "SELECT ai_paused FROM tenant_settings WHERE tenant_id = ? AND phone = ?",
            (tenant_id, phone)
        ).fetchone()
        return bool(row["ai_paused"]) if row else False

    def set_ai_paused(self, tenant_id: str, phone: str, paused: bool):
        """Active/désactive l'IA pour ce client final (prise de relais humain)."""
        with db_transaction() as conn:
            conn.execute("""
                INSERT INTO tenant_settings (tenant_id, phone, ai_paused)
                VALUES (?, ?, ?)
                ON CONFLICT(tenant_id, phone) DO UPDATE SET ai_paused = excluded.ai_paused
            """, (tenant_id, phone, 1 if paused else 0))

    def get_dashboard_data(self, tenant_id: str) -> dict:
        """Agrège les données analytics pour le dashboard client."""
        conn = get_connection()
        total_msgs = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE tenant_id = ?", (tenant_id,)
        ).fetchone()[0]
        unique_clients = conn.execute(
            "SELECT COUNT(DISTINCT phone) FROM conversations WHERE tenant_id = ?", (tenant_id,)
        ).fetchone()[0]
        return {
            "total_messages": total_msgs,
            "unique_clients": unique_clients,
        }


# ── Instances singletons (Injection de dépendances) ────────────────────────
tenant_repo = TenantRepository()
conversation_repo = ConversationRepository()

# Initialisation au démarrage
get_connection()
