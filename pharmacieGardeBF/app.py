from flask import Flask, render_template, request, jsonify
import math
import datetime
from pymongo import MongoClient

app = Flask(__name__)

# === CONFIGURATION MONGODB ===
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME   = "pharmacies_bf"

_client = None

def get_db():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client[DB_NAME]


# ─────────────────────────────────────────────────────────────────
#  LOGIQUE DE GARDE
# ─────────────────────────────────────────────────────────────────

def get_current_garde_group(t: datetime.datetime) -> int:
    """
    Retourne le numéro du groupe actuellement de garde (1-4).
    La semaine de garde démarre le samedi à 12h00.
    On utilise la config stockée dans MongoDB comme point de référence.
    """
    db = get_db()
    config = db["garde_config"].find_one()

    if config:
        ref_date  = config["reference_date"]
        ref_group = config["reference_group"]
        nb        = config["nb_groupes"]
    else:
        # Valeurs par défaut si import_data.py n'a pas été exécuté
        ref_date  = datetime.datetime(2025, 3, 8, 12, 0, 0)
        ref_group = 1
        nb        = 4

    # Nombre de semaines écoulées depuis la date de référence
    delta_seconds = (t - ref_date).total_seconds()
    weeks_elapsed = int(delta_seconds // (7 * 24 * 3600))

    current_group = ((ref_group - 1 + weeks_elapsed) % nb) + 1
    return current_group


def is_pharmacy_open(pharmacy: dict, t: datetime.datetime, garde_group: int) -> tuple:
    """
    Détermine si une pharmacie est ouverte à l'instant t.
    Retourne (est_ouvert: bool, de_garde: bool, label_horaire: str)

    Horaires normaux (approximatifs) :
      Lun–Sam : 07h30–12h30 et 15h00–18h30
      Dimanche : fermé (sauf garde)

    Garde : toute la semaine 24h/24 pour le groupe de garde actuel.
    """
    # Pharmacies déclarées ouvertes 24h (hors Ouaga/Bobo)
    if pharmacy.get("ouvert_24h"):
        return True, False, "Ouvert 24h/24"

    groupe = pharmacy.get("groupe_garde")
    de_garde = (groupe == garde_group)

    if de_garde:
        return True, True, "De garde (ouvert 24h/24)"

    # Horaires normaux
    weekday = t.weekday()   # 0=Lun … 6=Dim
    hour    = t.hour
    minute  = t.minute
    h_min   = hour * 60 + minute   # minutes depuis minuit

    if weekday == 6:   # Dimanche
        ouvert = False
    else:
        matin = (7 * 60 + 30 <= h_min <= 12 * 60 + 30)
        aprem = (15 * 60      <= h_min <= 18 * 60 + 30)
        ouvert = matin or aprem

    horaire_label = "Lun–Sam : 7h30–12h30 / 15h–18h30"
    return ouvert, False, horaire_label


def haversine_meters(lon1, lat1, lon2, lat2) -> float:
    """Distance en mètres entre deux points géographiques."""
    R = 6_371_000  # rayon Terre en mètres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─────────────────────────────────────────────────────────────────
#  FONCTION PRINCIPALE
# ─────────────────────────────────────────────────────────────────

def getLocations(ex_lon: float, ex_lat: float, t: datetime.datetime) -> list:
    """
    Retourne la liste des pharmacies triées par :
      1. Ouvertes en premier (et de garde en tête des ouvertes)
      2. Distance croissante
    
    Chaque élément :
      {
        "nom"      : str,
        "source"   : str,
        "ouverture": str,
        "details"  : str,
        "telephone": str,
        "distance" : float (mètres),
        "lon"      : float,
        "lat"      : float,
        "ouvert"   : bool,
        "deGarde"  : bool,
        "groupe"   : int | None,
        "ville"    : str,
      }
    """
    db = get_db()
    col = db["pharmacies"]

    garde_group = get_current_garde_group(t)
    results = []

    for p in col.find():
        coords = p["location"]["coordinates"]
        lon, lat = coords[0], coords[1]

        dist = haversine_meters(ex_lon, ex_lat, lon, lat)
        ouvert, de_garde, horaire_label = is_pharmacy_open(p, t, garde_group)

        results.append({
            "nom":       p["nom"],
            "source":    p.get("source", "Google Maps / OSM"),
            "ouverture": horaire_label,
            "details":   p.get("adresse", ""),
            "telephone": p.get("telephone", ""),
            "distance":  round(dist),
            "lon":       lon,
            "lat":       lat,
            "ouvert":    ouvert,
            "deGarde":   de_garde,
            "groupe":    p.get("groupe_garde"),
            "ville":     p.get("ville", ""),
        })

    # Tri : ouvert+deGarde → ouvert → fermé, puis distance
    def sort_key(loc):
        if loc["ouvert"] and loc["deGarde"]:
            priority = 0
        elif loc["ouvert"]:
            priority = 1
        else:
            priority = 2
        return (priority, loc["distance"])

    results.sort(key=sort_key)
    return results


# ─────────────────────────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/locate-items/<lon>/<lat>')
def locateItems(lon, lat):
    locations = getLocations(float(lon), float(lat), datetime.datetime.now())
    return render_template(
        'map-show.html',
        longitude=lon,
        latitude=lat,
        locations=locations,
    )


@app.route('/api/locations/<lon>/<lat>')
def api_locations(lon, lat):
    """Endpoint JSON pour usage mobile/externe."""
    locations = getLocations(float(lon), float(lat), datetime.datetime.now())
    return jsonify(locations)


if __name__ == '__main__':
    app.run(debug=True)
