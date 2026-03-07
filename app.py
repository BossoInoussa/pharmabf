from flask import Flask, render_template, request
import random as rand
import math
import datetime

app = Flask(__name__)


# first route

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/locate-items/<lon>/<lat>') 
def locateItems(lon, lat):
    locations = getLocations(float(lon), float(lat), datetime.datetime.now())
    return render_template('map-show.html', longitude = lon, latitude = lat, locations = locations)

def getLocations(ex_lon, ex_lat, t):
    """
        A completer, retourner une valeur de ce type 
            {"nom" : "Pharmacie de Ouaga 2", "source"; "Google", "ouverture" : "lun: 7h-18h...", "details" : "A tampouy à côté du maquis Lilas", "distance": 500, "lon": 2.5724032, "lat": 48.7849984, "ouvert": True, "deGarde": True }
    """
    locations = []
    for i in range(0, 10):
        n_lon = ex_lon + (rand.random() - 0.5) / 100
        n_lat = ex_lat + (rand.random() - 0.5) / 100
        iSource = rand.choice(["Google", "OSM", "Facebook"])
        iOpened = rand.choice([True, False])
        dist =  math.sqrt((ex_lon - n_lon) * (ex_lon - n_lon) + (ex_lat - n_lat) * (ex_lat - n_lat)) * 111000
        locations.append({"nom" : "Pharmacie n°" + str(i), "source": iSource, "ouverture" : "lun: 7h-18h...", "details" : "A tampouy à côté du maquis Lilas", "distance": round(dist, 2), "lon": n_lon, "lat": n_lat, "ouvert": iOpened, "deGarde": rand.choice([True, False]) })

    return locations
    

# keep this as is
if __name__ == '__main__':
    app.run(debug=True)