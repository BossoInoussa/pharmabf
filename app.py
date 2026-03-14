from flask import Flask, render_template, request, jsonify
import math
import datetime
import os
from pymongo import MongoClient

app = Flask(__name__)

# MONGO_URI = "mongodb://localhost:27017/"
MONGO_URI = os.environ.get("MONGO_URL", "mongodb://localhost:27017/")
DB_NAME   = "pharmacies_bf"
_client   = None

def get_db():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client[DB_NAME]


# ─── Logique de garde ────────────────────────────────────────────

def get_current_garde_group(t: datetime.datetime) -> int:
    db     = get_db()
    config = db["garde_config"].find_one()
    if config:
        ref_date  = config["reference_date"]
        ref_group = config["reference_group"]
        nb        = config["nb_groupes"]
    else:
        ref_date  = datetime.datetime(2025, 3, 8, 12, 0, 0)
        ref_group = 1
        nb        = 4

    delta_seconds = (t - ref_date).total_seconds()
    weeks_elapsed = int(delta_seconds // (7 * 24 * 3600))
    return ((ref_group - 1 + weeks_elapsed) % nb) + 1


def is_pharmacy_open(pharmacy: dict, t: datetime.datetime, garde_group: int) -> tuple:
    if pharmacy.get("ouvert_24h"):
        return True, False, "Ouvert 24h/24"

    groupe   = pharmacy.get("groupe_garde")
    de_garde = (groupe == garde_group)

    if de_garde:
        return True, True, "De garde — ouvert 24h/24"

    weekday = t.weekday()   # 0=Lun, 6=Dim
    h_min   = t.hour * 60 + t.minute

    if weekday == 6:
        ouvert = False
    else:
        matin = (7*60+30 <= h_min <= 12*60+30)
        aprem = (15*60   <= h_min <= 18*60+30)
        ouvert = matin or aprem

    return ouvert, False, "Lun–Sam : 7h30–12h30 / 15h–18h30"


def haversine_meters(lon1, lat1, lon2, lat2) -> float:
    R  = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp  = math.radians(lat2 - lat1)
    dl  = math.radians(lon2 - lon1)
    a   = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# ─── Fonction principale ─────────────────────────────────────────

def getLocations(ex_lon: float, ex_lat: float, t: datetime.datetime) -> list:
    db          = get_db()
    col         = db["pharmacies"]
    garde_group = get_current_garde_group(t)
    results     = []

    for p in col.find():
        coords = p["location"]["coordinates"]
        lon, lat = coords[0], coords[1]
        dist = haversine_meters(ex_lon, ex_lat, lon, lat)
        ouvert, de_garde, horaire = is_pharmacy_open(p, t, garde_group)

        results.append({
            "nom":       p["nom"],
            "source":    p.get("source", "Google Maps / OSM"),
            "ouverture": horaire,
            "adresse":   p.get("adresse", ""),
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

    def sort_key(loc):
        if loc["ouvert"] and loc["deGarde"]: return (0, loc["distance"])
        if loc["ouvert"]:                    return (1, loc["distance"])
        return                                      (2, loc["distance"])

    results.sort(key=sort_key)
    return results


# ─── Routes Flask ────────────────────────────────────────────────

@app.route('/')
def index():
    now         = datetime.datetime.now()
    garde_group = get_current_garde_group(now)

    # Calcul du prochain changement de garde (samedi suivant 12h)
    # weekday: 5=Sam, delta pour atteindre prochain samedi
    days_until_sat = (5 - now.weekday()) % 7
    if days_until_sat == 0 and now.hour >= 12:
        days_until_sat = 7
    next_garde = (now + datetime.timedelta(days=days_until_sat)).replace(hour=12, minute=0, second=0)
    delta      = next_garde - now
    hours_left = int(delta.total_seconds() // 3600)

    return render_template('index.html',
                           garde_group=garde_group,
                           hours_left=hours_left)


@app.route('/locate-items/<lon>/<lat>')
def locateItems(lon, lat):
    autofilter = request.args.get('filter', '')
    locations  = getLocations(float(lon), float(lat), datetime.datetime.now())
    now        = datetime.datetime.now()
    garde_group = get_current_garde_group(now)

    return render_template('map-show.html',
                           longitude=lon,
                           latitude=lat,
                           locations=locations,
                           garde_group=garde_group,
                           autofilter=autofilter)


@app.route('/api/locations/<lon>/<lat>')
def api_locations(lon, lat):
    locations = getLocations(float(lon), float(lat), datetime.datetime.now())
    return jsonify(locations)


@app.route('/api/garde')
def api_garde():
    now         = datetime.datetime.now()
    garde_group = get_current_garde_group(now)
    return jsonify({"groupe": garde_group, "timestamp": now.isoformat()})

@app.route('/init-db')
def init_db():
    from import_data import main
    main()
    return "Base de donnees importee"
    
# if __name__ == '__main__':
#    app.run(debug=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
