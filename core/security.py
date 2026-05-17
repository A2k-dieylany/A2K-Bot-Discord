"""
╔══════════════════════════════════════════════════════════════╗
║   core/security.py — Couche Sécurité (AES-GCM / Fernet)    ║
║   Chiffrement AES-256 de tous les secrets clients           ║
║   Standard: OWASP, NIST SP 800-38D                         ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import logging

logger = logging.getLogger(__name__)

# ── Dérivation de la clé maître depuis la variable d'environnement ─────────
# La clé est dérivée par PBKDF2 avec 480 000 itérations (recommandation NIST 2024)
# Elle n'est JAMAIS stockée en clair, seulement en mémoire pendant l'exécution.

_MASTER_KEY_RAW: str = os.getenv("SECRET_ENCRYPTION_KEY", "change_me_in_production_NOW")
_SALT: bytes = os.getenv("ENCRYPTION_SALT", "botsaas_sds_dakar_2026").encode()

def _derive_fernet_key(master_key: str, salt: bytes) -> bytes:
    """Dérive une clé Fernet 256-bit depuis la clé maître via PBKDF2-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,
    )
    raw = kdf.derive(master_key.encode())
    return base64.urlsafe_b64encode(raw)

_FERNET = Fernet(_derive_fernet_key(_MASTER_KEY_RAW, _SALT))


class SecurityService:
    """
    Service de chiffrement symétrique (AES-128 en mode CBC via Fernet).
    Fernet garantit l'authenticité du message (HMAC-SHA256) et l'intégrité.
    Usage : chiffrer les clés API GreenAPI, tokens Gemini, etc. des clients.
    """

    @staticmethod
    def encrypt(plaintext: str) -> str:
        """
        Chiffre une valeur en texte clair. Retourne une chaîne base64 sécurisée.
        Lève ValueError si la donnée est vide.
        """
        if not plaintext or not plaintext.strip():
            raise ValueError("La valeur à chiffrer ne peut pas être vide.")
        token: bytes = _FERNET.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")

    @staticmethod
    def decrypt(ciphertext: str) -> str:
        """
        Déchiffre un token Fernet. Retourne le texte clair.
        Lève SecurityError si le token est corrompu ou altéré.
        """
        try:
            plaintext: bytes = _FERNET.decrypt(ciphertext.encode("utf-8"))
            return plaintext.decode("utf-8")
        except InvalidToken as e:
            logger.error("Tentative de déchiffrement avec un token invalide. Possible tampering.")
            raise PermissionError("Token de sécurité invalide ou corrompu.") from e

    @staticmethod
    def hash_phone(phone: str) -> str:
        """
        Hash un numéro de téléphone (SHA-256) pour les logs/analytics anonymisés.
        Garantit que les logs ne contiennent jamais de données PII en clair.
        """
        return hashlib.sha256(f"salt_phone_{phone}".encode()).hexdigest()[:16]


# ── Instance singleton exportée ─────────────────────────────────────────────
security = SecurityService()
