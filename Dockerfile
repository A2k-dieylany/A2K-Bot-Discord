# Utilise une version officielle et légère de Python
FROM python:3.10-slim

# Définit le dossier de travail dans la "boîte"
WORKDIR /app

# Copie le fichier des dépendances
COPY requirements.txt .

# Installe les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Copie tout ton code source (main.py, etc.)
COPY . .

# Expose le port 8080 (celui que ton code Python écoute)
EXPOSE 8080

# La commande qui lance ton bot
CMD ["python", "main.py"]
