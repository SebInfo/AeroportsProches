from flask import Flask, render_template, request
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium

# Initialisation de l'application Flask
app = Flask(__name__)

# Charger le fichier CSV contenant les aéroports
df = pd.read_csv("csv/airports.csv")

# Filtrer et renommer les colonnes pour plus de clarté
filtered_df = df[["ident", "name", "type", "latitude_deg", "longitude_deg", "iso_country"]].copy()
filtered_df.rename(columns={"ident": "code_oaci", "latitude_deg": "lat", "longitude_deg": "lon"}, inplace=True)

# Ajouter une colonne géométrique pour représenter les coordonnées
filtered_df["geometry"] = [Point(xy) for xy in zip(filtered_df["lon"], filtered_df["lat"])]

# Conversion en GeoDataFrame pour faciliter les calculs géographiques
airports = gpd.GeoDataFrame(filtered_df, geometry="geometry")

def get_airport_info(code_oaci):
    """
    Récupère les informations d'un aéroport à partir de son code OACI.

    :param code_oaci: Code OACI de l'aéroport recherché
    :return: Dictionnaire contenant les informations de l'aéroport (nom, type, coordonnées) ou None si non trouvé.
    """
    airport = airports[airports["code_oaci"] == code_oaci]
    if airport.empty:
        return None
    return {
        "name": airport.iloc[0]["name"],
        "type": airport.iloc[0]["type"],
        "geometry": airport.iloc[0]["geometry"]
    }

def find_nearby_airports(geometry, selected_type, exclude_oaci, max_results=4):
    """
    Trouve les aéroports les plus proches d'un aéroport donné.

    :param geometry: Coordonnées de l'aéroport de référence
    :param selected_type: Type d'aéroports à inclure (large_airport, medium_airport ou all)
    :param exclude_oaci: Code OACI de l'aéroport de référence (à exclure)
    :param max_results: Nombre maximum d'aéroports proches à retourner
    :return: GeoDataFrame des aéroports les plus proches
    """
    airports["distance"] = airports["geometry"].distance(geometry)
    filtered_airports = airports[airports["code_oaci"] != exclude_oaci]

    # Filtrer selon le type sélectionné
    if selected_type != "all":
        filtered_airports = filtered_airports[filtered_airports["type"] == selected_type]

    return filtered_airports.nsmallest(max_results, "distance")

def create_map(lat, lon, airport_name, nearby_airports):
    """
    Crée une carte Folium centrée sur un aéroport et affiche les aéroports proches.

    :param lat: Latitude de l'aéroport principal
    :param lon: Longitude de l'aéroport principal
    :param airport_name: Nom de l'aéroport principal
    :param nearby_airports: Liste des aéroports proches à afficher
    :return: Objet Folium Map
    """
    folium_map = folium.Map(location=[lat, lon], zoom_start=12, tiles="CartoDB Positron")
    bounds = [[lat, lon]]  # Ajouter l'aéroport principal aux limites

    # Ajouter l'aéroport principal sur la carte
    folium.Marker(
        [lat, lon], tooltip=airport_name, popup=airport_name,
        icon=folium.Icon(color="blue", icon="plane", prefix="fa")
    ).add_to(folium_map)

    # Ajouter les aéroports proches sur la carte
    for _, nearby_airport in nearby_airports.iterrows():
        nearby_lat, nearby_lon = nearby_airport["geometry"].y, nearby_airport["geometry"].x
        nearby_name = nearby_airport["name"]
        folium.Marker(
            [nearby_lat, nearby_lon], tooltip=nearby_name,
            popup=f"{nearby_name} ({nearby_airport['distance']:.2f} km)",
            icon=folium.Icon(color="green", icon="plane", prefix="fa")
        ).add_to(folium_map)
        bounds.append([nearby_lat, nearby_lon])

    # Ajuster la carte pour inclure tous les points
    folium_map.fit_bounds(bounds)
    return folium_map

@app.route("/presentation")
def presentation():
    """
    Affiche la page de présentation du projet.
    """
    return render_template("presentation.html")

@app.route("/", methods=["GET", "POST"])
def index():
    """
    Vue principale qui affiche la page d'accueil et permet de rechercher un aéroport.

    :return: Rendu HTML avec les informations de l'aéroport et la carte générée
    """
    airport_name = None
    airport_type = None
    code_oaci = "LFMK"
    map_path = None

    if request.method == "POST":
        code_oaci = request.form.get("code_oaci").upper()
        selected_type = request.form.get("airport_type", "all")
        show_nearby = "show_nearby" in request.form

        airport_info = get_airport_info(code_oaci)

        if airport_info:
            airport_name = airport_info["name"]
            airport_type = airport_info["type"]
            geometry = airport_info["geometry"]
            lat, lon = geometry.y, geometry.x

            # Rechercher les aéroports proches si l'option est cochée
            nearby_airports = find_nearby_airports(geometry, selected_type, code_oaci) if show_nearby else pd.DataFrame()

            # Générer la carte
            folium_map = create_map(lat, lon, airport_name, nearby_airports)

            # Sauvegarde de la carte dans un fichier HTML
            map_path = "static/map.html"
            folium_map.save(map_path)
        else:
            airport_name = "Aéroport non trouvé"

    return render_template("index.html", airport_name=airport_name, airport_type=airport_type, code_oaci=code_oaci, map_path=map_path)

if __name__ == "__main__":
    app.run(debug=True)
