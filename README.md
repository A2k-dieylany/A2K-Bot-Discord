# 🤖 Claude AI Discord Bot — Agent Polyvalent

Un bot Discord ultra-puissant propulsé par **Claude (Anthropic)**, capable de coder, déboguer, traduire, planifier, analyser des images et bien plus encore.

---

## ✨ Fonctionnalités

| Commande | Description |
|---|---|
| `/ask` | Poser n'importe quelle question |
| `/code` | Générer du code dans n'importe quel langage |
| `/debug` | Déboguer un code avec son erreur |
| `/expliquer` | Expliquer un bloc de code ligne par ligne |
| `/traduire` | Traduire dans n'importe quelle langue |
| `/resume` | Résumer un texte long en points clés |
| `/tache` | Décomposer une tâche complexe en étapes |
| `/plan` | Créer un plan de projet professionnel |
| `/math` | Résoudre des problèmes mathématiques |
| `/corriger` | Corriger et améliorer un texte |
| `/info` | Afficher l'aide du bot |
| `/clear` | Effacer l'historique de conversation |
| `@mention` | Parler directement + analyser des images |

---

## 🚀 Installation

### Étape 1 — Prérequis
- Python 3.10+ installé
- Un compte Discord (gratuit)
- Une clé API Anthropic (https://console.anthropic.com)

### Étape 2 — Créer le bot Discord

1. Va sur https://discord.com/developers/applications
2. Clique **"New Application"** → donne un nom
3. Va dans **"Bot"** → clique **"Add Bot"**
4. Copie le **Token** du bot
5. Active les **Intents** : `MESSAGE CONTENT`, `SERVER MEMBERS`
6. Va dans **"OAuth2 > URL Generator"** :
   - Coche `bot` et `applications.commands`
   - Permissions : `Send Messages`, `Read Message History`, `Embed Links`, `Attach Files`
7. Copie l'URL générée → ouvre-la dans ton navigateur → invite le bot sur ton serveur

### Étape 3 — Configurer le projet

```bash
# Cloner / télécharger le projet
cd discord-bot

# Installer les dépendances
pip install -r requirements.txt

# Créer le fichier de config
cp .env.example .env
```

Ouvre `.env` et remplis :
```env
DISCORD_TOKEN=ton_token_discord
ANTHROPIC_API_KEY=sk-ant-ta_clé_anthropic
```

### Étape 4 — Lancer le bot

```bash
python main.py
```

Tu verras :
```
╔══════════════════════════════════════════╗
║  ✅ ClaudeBot est en ligne !
║  🤖 Modèle : claude-sonnet-4-20250514
║  📋 Serveurs : 1
╚══════════════════════════════════════════╝
```

---

## 🧠 Système de mémoire

Le bot garde en mémoire les **20 derniers échanges** par utilisateur. Cela lui permet de maintenir le contexte d'une conversation. Utilise `/clear` pour repartir de zéro.

---

## 🖼️ Analyse d'images

Pour analyser une image :
1. Mentionne le bot : `@ClaudeBot`
2. Joins une image en pièce jointe
3. Pose ta question sur l'image (optionnel)

---

## 🌐 Hébergement en ligne (24h/24)

Pour que le bot tourne en permanence :

### Option gratuite — Railway
```bash
# 1. Crée un compte sur railway.app
# 2. Nouveau projet → "Deploy from GitHub"
# 3. Pousse ton code sur GitHub
# 4. Ajoute les variables d'environnement dans Railway
# 5. Déploie !
```

### Option gratuite — Render
```bash
# 1. Crée un compte sur render.com
# 2. Nouveau "Web Service" → connecte GitHub
# 3. Start Command : python main.py
# 4. Ajoute les variables d'environnement
```

### Option locale permanente (Windows)
```bash
# Créer une tâche planifiée ou utiliser pm2 avec Node.js
npm install -g pm2
pm2 start main.py --interpreter python3
pm2 save
pm2 startup
```

---

## 🔧 Personnalisation

Dans `main.py`, tu peux modifier :
- `SYSTEM_PROMPT` : changer la personnalité du bot
- `MAX_HISTORY` : ajuster la taille de la mémoire
- `MAX_TOKENS` : ajuster la longueur des réponses
- Ajouter tes propres commandes en suivant le même pattern

---

## 📄 Licence

Projet personnel — libre d'utilisation et de modification.
