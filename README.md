# 🤖 A2K Bot Discord — Agent Polyvalent (Groq)

Un bot Discord ultra-rapide et performant propulsé par **Groq** et **Llama 3.3 70B**. Il est capable de coder, déboguer, traduire, planifier, lire des fichiers et bien plus encore, avec une interface moderne et 100% asynchrone !

---

## ✨ Fonctionnalités Principales

| Commande | Description |
|---|---|
| `/ask` | Poser n'importe quelle question (fichiers texte/code supportés) |
| `/code` | Générer du code dans n'importe quel langage |
| `/debug` | Déboguer un script avec son message d'erreur |
| `/expliquer` | Expliquer un bloc de code ligne par ligne |
| `/traduire` | Traduire dans n'importe quelle langue |
| `/resume` | Résumer un texte long en points clés |
| `/tache` | Décomposer une tâche complexe en étapes |
| `/plan` | Créer un plan de projet professionnel |
| `/math` | Résoudre des problèmes mathématiques |
| `/corriger` | Corriger et améliorer un texte |
| `/clear` | Effacer l'historique de conversation du salon |
| `@mention` | Discuter directement avec le bot (fichiers supportés) |

### 🌟 Fonctionnalités Premium (Incluses)
- **100% Asynchrone :** Gère des dizaines de requêtes simultanées sans jamais bloquer.
- **Mémoire de Salon :** Le contexte est sauvegardé par salon/thread, idéal pour collaborer à plusieurs !
- **Lecture de Fichiers :** Glissez un fichier `.py`, `.js`, `.txt`, etc. dans le chat et demandez au bot de l'analyser.
- **Interface Embeds :** Réponses magnifiquement formatées et colorées (Pagination automatique).
- **Bouton Interactif :** Corbeille 🗑️ sous chaque message pour nettoyer le salon (réservée à l'auteur de la commande).

---

## 🚀 Installation & Lancement

### Étape 1 — Prérequis
- Python 3.10+ installé
- Un compte Discord Developer
- Une clé API Groq (Gratuite sur [console.groq.com](https://console.groq.com/))

### Étape 2 — Configuration
1. Clonez ce dépôt.
2. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
3. Créez un fichier `.env` à la racine (basé sur `.env.example`) :
   ```env
   DISCORD_TOKEN=votre_token_discord
   GROQ_API_KEY=gsk_votre_cle_groq
   BOT_NAME=MonBot
   MAX_HISTORY=50
   ```

### Étape 3 — Lancer le bot
```bash
python main.py
```

---

## 📄 À propos
Projet développé et optimisé pour la rapidité extrême de Groq (Llama 3). 
Libre d'utilisation et de modification.
