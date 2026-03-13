# PharmaBF 

## Suivez les instructions pas à pas . Merci et bonne journée a tous!!!!!!!!!!!!!!!
## Prérequis
- Python 3.9+
- MongoDB (installé et actif sur localhost:27017)
- pip

## Installation

```bash
# 1. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate       # Linux/macOS
venv\Scripts\activate          # Windows

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Placer les fichiers JSON dans le même dossier
#    pharmaciesOuaga.json
#    pharmaciesBobo.json

# 4. Importer les données dans MongoDB
python import_data.py

# 5. Lancer l'application
python app.py
```

Ouvrir http://localhost:5000 dans le navigateur.

