import requests
import os
from dotenv import load_dotenv

load_dotenv()
# Wir holen das Token, entfernen aber sicherheitshalber Leerzeichen
TREFLE_TOKEN = os.getenv("TREFLE_API_TOKEN", "").strip()

def search_plants(query: str):
    """
    Sucht nach Pflanzen. 
    Entspricht: https://trefle.io/api/v1/plants/search?token=...&q=...
    """
    url = "https://trefle.io/api/v1/plants/search"
    
    params = {
        "token": TREFLE_TOKEN,
        "q": query
    }
    
    print(f"DEBUG: Rufe URL auf: {url} mit Query: {query}") # Damit wir sehen was passiert
    
    try:
        response = requests.get(url, params=params)
        
        # Zeigt uns den exakten Statuscode (200 ist gut, 401 verboten, 404 nicht gefunden)
        print(f"DEBUG: Status Code: {response.status_code}")
        
        if response.status_code == 200:
            return response.json().get("data", [])
        else:
            print(f"API Fehler: {response.text}")
            return []
            
    except Exception as e:
        print(f"Python Request Fehler: {e}")
        return []

def get_plant_details(trefle_id: int):
    """
    Holt Details einer Pflanze per ID.
    Nutzt ALLE verfügbaren Trefle-Daten für bessere Schätzungen.
    """
    url = f"https://trefle.io/api/v1/plants/{trefle_id}"
    params = {"token": TREFLE_TOKEN}
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json().get("data", {})
            
            main_species = data.get("main_species", {})
            growth = main_species.get("growth", {})
            specifications = main_species.get("specifications", {})
            
            # === WASSER & LUFTFEUCHTIGKEIT ===
            soil_humidity = growth.get("soil_humidity")
            water_days = 7
            humidity_req = 5
            
            if soil_humidity:
                soil_val = int(soil_humidity)
                if soil_val >= 9:  # Sumpf/Wasser
                    water_days = 2
                    humidity_req = 9
                elif soil_val >= 7:  # Feucht
                    water_days = 3
                    humidity_req = 7
                elif soil_val >= 5:  # Mittel
                    water_days = 7
                    humidity_req = 5
                elif soil_val >= 3:  # Trocken
                    water_days = 14
                    humidity_req = 3
                else:  # Sehr trocken (Kakteen, Sukkulenten)
                    water_days = 21
                    humidity_req = 2
            
            # === DÜNGEN basierend auf Wachstumsrate ===
            growth_rate = growth.get("growth_rate")
            fertilize_days = 30
            if growth_rate:
                if growth_rate == "fast": fertilize_days = 14
                elif growth_rate == "moderate": fertilize_days = 30
                elif growth_rate == "slow": fertilize_days = 60
            
            # === UMTOPFEN ===
            repot_days = 730  # Standard 2 Jahre
            if growth_rate == "fast": repot_days = 365
            
            # === LICHT ===
            light = growth.get("light")
            light_req = 5
            if light:
                try:
                    light_req = int(light)
                except:
                    # Fallback auf Textbeschreibung
                    if "full sun" in str(light).lower(): light_req = 10
                    elif "part shade" in str(light).lower(): light_req = 6
                    elif "shade" in str(light).lower(): light_req = 3
            
            # === HÖHE ===
            max_height_cm = 100  # Default
            
            # Prüfe verschiedene Quellen für Höhe
            height_sources = [
                specifications.get("maximum_height", {}),
                main_species.get("maximum_height", {}),
                growth.get("maximum_height", {})
            ]
            
            for height_data in height_sources:
                if height_data and isinstance(height_data, dict):
                    if height_data.get("cm"):
                        max_height_cm = int(height_data["cm"])
                        break
                    elif height_data.get("m"):
                        max_height_cm = int(float(height_data["m"]) * 100)
                        break
            
            # Fallback auf average_height
            if max_height_cm == 100:
                avg_height = specifications.get("average_height", {})
                if avg_height and avg_height.get("cm"):
                    max_height_cm = int(float(avg_height["cm"]) * 1.2)  # 20% Puffer
            
            # === TEMPERATUR ===
            temp_min = 15
            temp_max = 25
            
            # Minimum Temperature
            min_temp_data = growth.get("minimum_temperature", {})
            if min_temp_data and min_temp_data.get("deg_c"):
                temp_min = int(min_temp_data["deg_c"])
            
            # Wenn keine min_temp, schätzen wir basierend auf anderen Faktoren
            atmospheric_humidity = growth.get("atmospheric_humidity")
            if atmospheric_humidity:
                # Tropische Pflanzen = höhere Mindesttemperatur
                if int(atmospheric_humidity) >= 8:
                    temp_min = 18
                    temp_max = 28
            
            # === BODENART ===
            soil_type = "universal"
            
            soil_texture = growth.get("soil_texture")
            if soil_texture:
                if "sand" in str(soil_texture).lower(): soil_type = "sandig"
                elif "clay" in str(soil_texture).lower(): soil_type = "lehmig"
                elif "loam" in str(soil_texture).lower(): soil_type = "humusreich"
            
            # === TOXIZITÄT ===
            toxicity = main_species.get("toxicity")
            is_toxic = False
            if toxicity and str(toxicity).lower() not in ["none", "null", "low", "0"]:
                is_toxic = True
            
            # Auch Edible-Status checken
            edible = main_species.get("edible")
            if edible is False:  # Explizit nicht essbar könnte giftig sein
                # Vorsichtshalber als potentiell giftig markieren
                pass
            
            # --- HEURISTIK-LAYER (nur wenn Trefle wenig liefert) -----------------

            name_blob = " ".join([
                str(data.get("scientific_name") or ""),
                str(data.get("common_name") or ""),
                str(main_species.get("family") or ""),
                str(main_species.get("genus") or "")
            ]).lower()

            def has_any(words):
                return any(w in name_blob for w in words)

            # 1) Keywords -> Plantentyp ableiten
            is_cactus = has_any(["cactus", "kaktus", "cactaceae", "opuntia", "echinopsis", "mammillaria"])
            is_succulent = has_any(["succulent", "sukkulent", "crassula", "echeveria", "sedum", "haworthia", "aloe"])
            is_herb = has_any(["basil", "basilikum", "mint", "minze", "thyme", "thymian", "rosemary", "rosmarin", "parsley", "petersilie", "oregano"])
            is_orchid = has_any(["orchid", "orchidee", "orchidaceae", "phalaenopsis"])
            is_tropical = has_any(["monstera", "philodendron", "calathea", "maranta", "anthurium", "alocasia", "pothos", "epipremnum", "dieffenbachia", "ficus"])
            is_fern = has_any(["fern", "farn", "nephrolepis", "asplenium", "pteris"])
            is_palm = has_any(["palm", "palme", "areca", "dypsis", "chamaedorea", "kentia", "howea"])
            is_citrus = has_any(["citrus", "lemon", "zitrone", "orange", "mandarine", "kumquat"])

            # 2) Licht -> grobe Umwelt ableiten (wenn Trefle light vorhanden, nutzt du es eh)
            # light_req ist bei dir 1-10 (10 = volle Sonne)
            # Faustregel:
            # - viel Licht -> tendenziell mehr Wasserbedarf oder zumindest öfter prüfen
            # - wenig Licht -> weniger Wasser (Verdunstung geringer)
            # - sehr hohe Luftfeuchte-Anforderungen eher bei Schattenpflanzen (Farne etc.)
            def light_band(l):
                if l >= 8: return "high"
                if l <= 4: return "low"
                return "mid"

            lb = light_band(light_req)

            # 3) Nur überschreiben, wenn Werte "unsicher" sind (Default oder aus fehlenden Feldern entstanden)
            # Du kannst die Defaults erkennen: humidity_req==5, temp 15-25, soil_type=="universal", max_height_cm==100 (dein Default)
            is_defaultish = (
                humidity_req == 5 and
                temp_min == 15 and temp_max == 25 and
                soil_type == "universal" and
                max_height_cm == 100
            )

            # 4) Heuristik anwenden
            if is_defaultish:
                # Baseline nach Licht
                if lb == "high":
                    water_days = min(water_days, 7)      # eher häufiger checken
                    humidity_req = max(humidity_req, 4)
                    soil_type = "universal"
                elif lb == "low":
                    water_days = max(water_days, 10)     # seltener gießen
                    humidity_req = max(humidity_req, 5)
                else:
                    # mid
                    water_days = max(min(water_days, 9), 7)

                # Typ-spezifische Overrides
                if is_cactus or is_succulent:
                    water_days = 21 if lb != "low" else 28
                    humidity_req = 2
                    soil_type = "sandig"
                    temp_min, temp_max = 12, 30
                    light_req = max(light_req, 8)
                    max_height_cm = min(max_height_cm, 80)

                if is_fern:
                    water_days = 3 if lb != "high" else 2
                    humidity_req = 8
                    soil_type = "humusreich"
                    temp_min, temp_max = 16, 28
                    light_req = min(light_req, 4)
                    max_height_cm = min(max_height_cm, 120)

                if is_orchid:
                    water_days = 7 if lb == "mid" else 10
                    humidity_req = 7
                    soil_type = "humusreich"
                    temp_min, temp_max = 18, 28
                    max_height_cm = 70

                if is_tropical:
                    water_days = 7 if lb != "high" else 5
                    humidity_req = 6
                    soil_type = "humusreich"
                    temp_min, temp_max = 18, 28

                if is_palm:
                    water_days = 7 if lb != "low" else 10
                    humidity_req = 6
                    soil_type = "humusreich"
                    temp_min, temp_max = 16, 28

                if is_herb:
                    # Kräuter mögen oft Sonne und gleichmäßige Feuchte, aber keine Staunässe
                    water_days = 3 if lb == "high" else 5
                    humidity_req = 5
                    soil_type = "universal"
                    temp_min, temp_max = 12, 28
                    max_height_cm = 60
                    if light_band == "high":water_days = 3

                if is_citrus:
                    water_days = 5 if lb == "high" else 7
                    humidity_req = 5
                    soil_type = "universal"
                    temp_min, temp_max = 10, 30

                
            return {
                "scientific_name": data.get("scientific_name"),
                "common_name": data.get("common_name"),
                "image_url": data.get("image_url"),
                "water_frequency_days": water_days,
                "fertilize_frequency_days": fertilize_days,
                "repot_frequency_days": repot_days,
                "prune_frequency_days": 90,
                "sunlight_requirement": light_req,
                "humidity_requirement": humidity_req,
                "temperature_min": temp_min,
                "temperature_max": temp_max,
                "max_height_cm": max_height_cm,
                "soil_type": soil_type,
                "is_toxic": is_toxic
            }
        return None
    except Exception as e:
        print(f"Fehler bei Details: {e}")
        return None
    