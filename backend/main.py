# backend/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import date, timedelta
from pydantic import BaseModel


# Eigene Module
import models, database
from services import trefle_service

# Datenbank Tabellen erstellen
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Care For Plants API")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In Produktion spezifischer machen!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Pydantic Schemas ---
# WICHTIG: Wir nutzen hier keine komplexen typing-Imports mehr
class LocationCreate(BaseModel):
    name: str
    light_level: int = 5

class WishlistCreate(BaseModel):
    trefle_id: int
    
class MyPlantCreate(BaseModel):
    nickname: str
    location_id: int
    trefle_id: int
    
class LocationCreate(BaseModel):
    name: str
    light_level: int = 5
    humidity_level: int = 5
    temperature_avg: int = 20
    available_space_cm: int = 200
    has_pets_or_children: bool = False

class WishlistCreate(BaseModel):
    trefle_id: int

class PlantInfoUpdate(BaseModel):
    water_frequency_days: int = None
    fertilize_frequency_days: int = None
    sunlight_requirement: int = None
    humidity_requirement: int = None
    temperature_min: int = None
    temperature_max: int = None
    max_height_cm: int = None
    soil_type: str = None
    is_toxic: bool = None

# --- API ENDPOINTS ---

@app.get("/plants/search/{query}")
def search_plants(query: str):
    return trefle_service.search_plants(query)

@app.post("/locations/")
def create_location(loc: LocationCreate, db: Session = Depends(get_db)):
    """Erstellt einen Standort mit detaillierten Umweltbedingungen"""
    db_loc = models.Location(
        name=loc.name,
        light_level=loc.light_level,
        humidity_level=loc.humidity_level,
        temperature_avg=loc.temperature_avg,
        available_space_cm=loc.available_space_cm,
        has_pets_or_children=loc.has_pets_or_children
    )
    db.add(db_loc)
    db.commit()
    db.refresh(db_loc)
    return db_loc

@app.get("/locations/")
def list_locations(db: Session = Depends(get_db)):
    return db.query(models.Location).all()

@app.post("/my-plants/")
def add_plant_to_location(plant_in: MyPlantCreate, db: Session = Depends(get_db)):
    # 1. Prüfen ob lokal vorhanden
    db_info = db.query(models.PlantInfo).filter(models.PlantInfo.trefle_id == plant_in.trefle_id).first()
    
    if not db_info:
        # 2. Importieren von Trefle
        details = trefle_service.get_plant_details(plant_in.trefle_id)
        if not details:
            raise HTTPException(status_code=404, detail="Pflanze bei Trefle nicht gefunden")
            
        db_info = models.PlantInfo(
            trefle_id=plant_in.trefle_id,
            scientific_name=details["scientific_name"],
            common_name=details["common_name"],
            image_url=details["image_url"],
            water_frequency_days=details["water_frequency_days"],
            fertilize_frequency_days=details["fertilize_frequency_days"],
            repot_frequency_days=details["repot_frequency_days"],
            prune_frequency_days=details["prune_frequency_days"],
            sunlight_requirement=details["sunlight_requirement"],
            humidity_requirement=details["humidity_requirement"],
            temperature_min=details["temperature_min"],
            temperature_max=details["temperature_max"],
            max_height_cm=details["max_height_cm"],
            soil_type=details["soil_type"],
            is_toxic=details["is_toxic"]
        )
        db.add(db_info)
        db.commit()
        db.refresh(db_info)

    # 3. User-Pflanze anlegen
    new_plant = models.MyPlant(
        nickname=plant_in.nickname,
        location_id=plant_in.location_id,
        plant_info_id=db_info.id,
        last_watered=date.today(),
        last_fertilized=date.today(),
        last_repotted=date.today(),
        last_pruned=date.today(),
        last_propagated=date.today(),
        date_acquired=date.today()
    )
    db.add(new_plant)
    db.commit()
    return {"status": "created", "plant": new_plant.nickname}


@app.post("/wishlist/")
def add_to_wishlist(item: WishlistCreate, db: Session = Depends(get_db)):
    """Fügt eine Pflanze zur Wunschliste hinzu"""
    # Prüfen ob schon in Wunschliste
    exists = db.query(models.Wishlist).filter(models.Wishlist.trefle_id == item.trefle_id).first()
    if exists:
        raise HTTPException(status_code=400, detail="Pflanze bereits in Wunschliste")
    
    # PlantInfo holen oder erstellen
    db_info = db.query(models.PlantInfo).filter(models.PlantInfo.trefle_id == item.trefle_id).first()
    
    if not db_info:
        details = trefle_service.get_plant_details(item.trefle_id)
        if not details:
            raise HTTPException(status_code=404, detail="Pflanze nicht gefunden")
            
        db_info = models.PlantInfo(
            trefle_id=item.trefle_id,
    scientific_name=details["scientific_name"],
    common_name=details["common_name"],
    image_url=details["image_url"],
    water_frequency_days=details["water_frequency_days"],
    fertilize_frequency_days=details["fertilize_frequency_days"],
    repot_frequency_days=details["repot_frequency_days"],
    prune_frequency_days=details["prune_frequency_days"],
    sunlight_requirement=details["sunlight_requirement"],
    humidity_requirement=details["humidity_requirement"],
    temperature_min=details["temperature_min"],
    temperature_max=details["temperature_max"],
    max_height_cm=details["max_height_cm"],
    soil_type=details["soil_type"],
    is_toxic=details["is_toxic"]
)
        db.add(db_info)
        db.commit()
        db.refresh(db_info)
    
    # Zur Wunschliste hinzufügen
    wishlist_item = models.Wishlist(
        trefle_id=item.trefle_id,
        plant_info_id=db_info.id,
        added_date=date.today()
    )
    db.add(wishlist_item)
    db.commit()
    
    return {"status": "added", "plant": db_info.common_name}

@app.get("/wishlist/")
def get_wishlist(db: Session = Depends(get_db)):
    """Gibt die Wunschliste mit ERWEITERTER Standort-Kompatibilität zurück"""
    wishlist = db.query(models.Wishlist).all()
    locations = db.query(models.Location).all()
    
    result = []
    for item in wishlist:
        plant = item.plant_info
        
        # Kompatible Standorte finden (erweiterte Prüfung)
        suitable = []
        for loc in locations:
            is_suitable = True
            
            # Licht-Check (Toleranz ±2)
            if abs(plant.sunlight_requirement - loc.light_level) > 2:
                is_suitable = False
            
            # Luftfeuchtigkeit-Check
            if abs(plant.humidity_requirement - loc.humidity_level) > 2:
                is_suitable = False
            
            # Temperatur-Check
            if loc.temperature_avg < plant.temperature_min or loc.temperature_avg > plant.temperature_max:
                is_suitable = False
            
            # Platz-Check
            if plant.max_height_cm > loc.available_space_cm:
                is_suitable = False
            
            # Giftigkeit-Check
            if plant.is_toxic and loc.has_pets_or_children:
                is_suitable = False
            
            if is_suitable:
                suitable.append(loc.name)
        
        result.append({
            "id": item.id,
            "trefle_id": item.trefle_id,
            "scientific_name": plant.scientific_name,
            "common_name": plant.common_name,
            "image_url": plant.image_url,
            "water_frequency_days": plant.water_frequency_days,
            "sunlight_requirement": plant.sunlight_requirement,
            "humidity_requirement": plant.humidity_requirement,
            "temperature_min": plant.temperature_min,
            "temperature_max": plant.temperature_max,
            "max_height_cm": plant.max_height_cm,
            "soil_type": plant.soil_type,
            "is_toxic": plant.is_toxic,
            "suitable_locations": suitable
        })
    
    return result

@app.delete("/wishlist/{item_id}")
def remove_from_wishlist(item_id: int, db: Session = Depends(get_db)):
    """Entfernt eine Pflanze aus der Wunschliste"""
    item = db.query(models.Wishlist).filter(models.Wishlist.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    
    db.delete(item)
    db.commit()
    return {"status": "deleted"}

@app.put("/wishlist/{item_id}/plant-info")
def update_plant_info(item_id: int, updates: PlantInfoUpdate, db: Session = Depends(get_db)):
    """Eigenschaften einer Pflanze in der Wunschliste manuell bearbeiten"""
    wishlist_item = db.query(models.Wishlist).filter(models.Wishlist.id == item_id).first()
    if not wishlist_item:
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    
    plant_info = wishlist_item.plant_info
    
    # Nur gesetzte Werte aktualisieren
    if updates.water_frequency_days is not None:
        plant_info.water_frequency_days = updates.water_frequency_days
    if updates.fertilize_frequency_days is not None:
        plant_info.fertilize_frequency_days = updates.fertilize_frequency_days
    if updates.sunlight_requirement is not None:
        plant_info.sunlight_requirement = updates.sunlight_requirement
    if updates.humidity_requirement is not None:
        plant_info.humidity_requirement = updates.humidity_requirement
    if updates.temperature_min is not None:
        plant_info.temperature_min = updates.temperature_min
    if updates.temperature_max is not None:
        plant_info.temperature_max = updates.temperature_max
    if updates.max_height_cm is not None:
        plant_info.max_height_cm = updates.max_height_cm
    if updates.soil_type is not None:
        plant_info.soil_type = updates.soil_type
    if updates.is_toxic is not None:
        plant_info.is_toxic = updates.is_toxic
    
    db.commit()
    return {"status": "updated", "plant": plant_info.common_name}

@app.get("/locations/{location_id}/details")
def get_location_details(location_id: int, db: Session = Depends(get_db)):
    """Zeigt alle Pflanzen an einem Standort + passende Wunschlistenpflanzen"""
    location = db.query(models.Location).filter(models.Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Standort nicht gefunden")
    
    # Tatsächliche Pflanzen am Standort
    actual_plants = []
    for plant in location.my_plants:
        actual_plants.append({
            "id": plant.id,
            "nickname": plant.nickname,
            "species": plant.plant_info.common_name or plant.plant_info.scientific_name,
            "image": plant.plant_info.image_url
        })
    
    # Wunschlisten-Pflanzen die passen würden
    wishlist = db.query(models.Wishlist).all()
    compatible_wishlist = []
    
    for item in wishlist:
        plant = item.plant_info
        is_compatible = True
        reasons = []
        
        # Licht-Check
        if abs(plant.sunlight_requirement - location.light_level) > 2:
            is_compatible = False
            reasons.append(f"Licht: braucht {plant.sunlight_requirement}, Standort hat {location.light_level}")
        
        # Luftfeuchtigkeit-Check
        if abs(plant.humidity_requirement - location.humidity_level) > 2:
            is_compatible = False
            reasons.append(f"Feuchtigkeit: braucht {plant.humidity_requirement}, Standort hat {location.humidity_level}")
        
        # Temperatur-Check
        if location.temperature_avg < plant.temperature_min or location.temperature_avg > plant.temperature_max:
            is_compatible = False
            reasons.append(f"Temperatur: braucht {plant.temperature_min}-{plant.temperature_max}°C, Standort hat {location.temperature_avg}°C")
        
        # Platz-Check
        if plant.max_height_cm > location.available_space_cm:
            is_compatible = False
            reasons.append(f"Platz: wird {plant.max_height_cm}cm hoch, nur {location.available_space_cm}cm verfügbar")
        
        # Giftigkeit-Check
        if plant.is_toxic and location.has_pets_or_children:
            is_compatible = False
            reasons.append("⚠️ GIFTIG für Haustiere/Kinder!")
        
        if is_compatible:
            compatible_wishlist.append({
                "wishlist_id": item.id,
                "common_name": plant.common_name,
                "scientific_name": plant.scientific_name,
                "image": plant.image_url
            })
    
    return {
        "location": {
            "id": location.id,
            "name": location.name,
            "light_level": location.light_level,
            "humidity_level": location.humidity_level,
            "temperature_avg": location.temperature_avg,
            "available_space_cm": location.available_space_cm,
            "has_pets_or_children": location.has_pets_or_children
        },
        "actual_plants": actual_plants,
        "compatible_wishlist_plants": compatible_wishlist
    }

@app.get("/dashboard/tasks")
def get_tasks(db: Session = Depends(get_db)):
    tasks = []
    my_plants = db.query(models.MyPlant).all()
    
    for plant in my_plants:
        # Gießen
        water_interval = plant.plant_info.water_frequency_days
        next_water = plant.last_watered + timedelta(days=water_interval)
        water_days_until = (next_water - date.today()).days
        
        # Düngen
        fertilize_interval = plant.plant_info.fertilize_frequency_days
        last_fert = plant.last_fertilized or plant.date_acquired
        next_fertilize = last_fert + timedelta(days=fertilize_interval)
        fert_days_until = (next_fertilize - date.today()).days
        
        # Umtopfen
        repot_interval = plant.plant_info.repot_frequency_days
        last_rep = plant.last_repotted or plant.date_acquired
        next_repot = last_rep + timedelta(days=repot_interval)
        repot_days_until = (next_repot - date.today()).days
        
        # Schneiden
        prune_interval = plant.plant_info.prune_frequency_days
        last_pru = plant.last_pruned or plant.date_acquired
        next_prune = last_pru + timedelta(days=prune_interval)
        prune_days_until = (next_prune - date.today()).days
        
        # Vermehren
        propagate_interval = plant.plant_info.propagate_frequency_days
        last_prop = plant.last_propagated or plant.date_acquired
        next_propagate = last_prop + timedelta(days=propagate_interval)
        prop_days_until = (next_propagate - date.today()).days

        
        # Nächste fällige Aufgabe bestimmen
        all_tasks = [
         ("water", water_days_until),
        ("fertilize", fert_days_until),
        ("repot", repot_days_until),
        ("prune", prune_days_until),
        ("propagate", prop_days_until)
        ]

        all_tasks.sort(key=lambda x: x[1])
        next_task = all_tasks[0]
        
        status = "OK"
        if next_task[1] < 0: status = "ÜBERFÄLLIG"
        elif next_task[1] == 0: status = "HEUTE"
        
        tasks.append({
            "id": plant.id,
            "plant": plant.nickname,
            "species": plant.plant_info.common_name or plant.plant_info.scientific_name,
            "location": plant.location.name,
            "image": plant.plant_info.image_url,
            "days_until_watering": water_days_until,
            "days_until_fertilizing": fert_days_until,
            "days_until_repotting": repot_days_until,
            "days_until_pruning": prune_days_until,
            "days_until_propagating": prop_days_until,
            "next_task": next_task[0],
            "next_task_days": next_task[1],
            "status": status
        })
    
    return sorted(tasks, key=lambda x: x["next_task_days"])



@app.post("/my-plants/{plant_id}/water")
def water_plant(plant_id: int, db: Session = Depends(get_db)):
    """Markiert eine Pflanze als gegossen"""
    plant = db.query(models.MyPlant).filter(models.MyPlant.id == plant_id).first()
    
    if not plant:
        raise HTTPException(status_code=404, detail="Pflanze nicht gefunden")
    
    plant.last_watered = date.today()
    db.commit()
    
    return {"status": "success", "plant": plant.nickname, "watered_on": str(date.today())}

@app.post("/my-plants/{plant_id}/fertilize")
def fertilize_plant(plant_id: int, db: Session = Depends(get_db)):
    """Markiert eine Pflanze als gedüngt"""
    plant = db.query(models.MyPlant).filter(models.MyPlant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Pflanze nicht gefunden")
    
    plant.last_fertilized = date.today()
    db.commit()
    return {"status": "success", "plant": plant.nickname, "fertilized_on": str(date.today())}

@app.post("/my-plants/{plant_id}/repot")
def repot_plant(plant_id: int, db: Session = Depends(get_db)):
    """Markiert eine Pflanze als umgetopft"""
    plant = db.query(models.MyPlant).filter(models.MyPlant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Pflanze nicht gefunden")
    
    plant.last_repotted = date.today()
    db.commit()
    return {"status": "success", "plant": plant.nickname, "repotted_on": str(date.today())}

@app.post("/my-plants/{plant_id}/prune")
def prune_plant(plant_id: int, db: Session = Depends(get_db)):
    """Markiert eine Pflanze als geschnitten"""
    plant = db.query(models.MyPlant).filter(models.MyPlant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Pflanze nicht gefunden")
    
    plant.last_pruned = date.today()
    db.commit()
    return {"status": "success", "plant": plant.nickname, "pruned_on": str(date.today())}

@app.post("/my-plants/{plant_id}/propagate")
def propagate_plant(plant_id: int, db: Session = Depends(get_db)):
    """Markiert eine Pflanze als vermehrt"""
    plant = db.query(models.MyPlant).filter(models.MyPlant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Pflanze nicht gefunden")

    plant.last_propagated = date.today()
    db.commit()

    return {"status": "success", "plant": plant.nickname, "propagated_on": str(date.today())}

from datetime import timedelta

@app.post("/admin/my-plants/{plant_id}/simulate/{days}")
def simulate_single_plant(plant_id: int, days: int, db: Session = Depends(get_db)):
    """
    Demo-Helfer: setzt die Pflege-Daten EINER Pflanze um X Tage zurück
    """
    plant = db.query(models.MyPlant).filter(models.MyPlant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Pflanze nicht gefunden")

    if plant.last_watered:
        plant.last_watered -= timedelta(days=days)
    if plant.last_fertilized:
        plant.last_fertilized -= timedelta(days=days)
    if plant.last_repotted:
        plant.last_repotted -= timedelta(days=days)
    if plant.last_pruned:
        plant.last_pruned -= timedelta(days=days)
    if hasattr(plant, "last_propagated") and plant.last_propagated:
        plant.last_propagated -= timedelta(days=days)

    db.commit()

    return {
        "status": "ok",
        "plant_id": plant.id,
        "nickname": plant.nickname,
        "days_shifted": days
    }
    
@app.delete("/my-plants/{plant_id}")
def delete_my_plant(plant_id: int, db: Session = Depends(get_db)):
    plant = db.query(models.MyPlant).filter(models.MyPlant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Pflanze nicht gefunden")

    db.delete(plant)
    db.commit()
    return {"status": "ok", "deleted_id": plant_id}



class MovePlantRequest(BaseModel):
    location_id: int

@app.put("/my-plants/{plant_id}/move")
def move_my_plant(plant_id: int, body: MovePlantRequest, db: Session = Depends(get_db)):
    plant = db.query(models.MyPlant).filter(models.MyPlant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Pflanze nicht gefunden")

    loc = db.query(models.Location).filter(models.Location.id == body.location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Standort nicht gefunden")

    plant.location_id = body.location_id
    db.commit()
    return {"status": "ok", "plant_id": plant_id, "new_location_id": body.location_id}

@app.get("/my-plants/{plant_id}/recommended-locations")
def get_recommended_locations_for_myplant(plant_id: int, db: Session = Depends(get_db)):
    plant = db.query(models.MyPlant).filter(models.MyPlant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Pflanze nicht gefunden")

    pi = plant.plant_info
    locations = db.query(models.Location).all()

    result = []
    for loc in locations:
        reasons = []
        ok = True

        if abs(pi.sunlight_requirement - loc.light_level) > 2:
            ok = False
            reasons.append("Licht passt nicht")

        if abs(pi.humidity_requirement - loc.humidity_level) > 2:
            ok = False
            reasons.append("Feuchtigkeit passt nicht")

        if loc.temperature_avg < pi.temperature_min or loc.temperature_avg > pi.temperature_max:
            ok = False
            reasons.append("Temperatur passt nicht")

        if pi.max_height_cm > loc.available_space_cm:
            ok = False
            reasons.append("Zu wenig Platz")

        if pi.is_toxic and loc.has_pets_or_children:
            ok = False
            reasons.append("Giftig bei Haustieren/Kinder")

        result.append({
            "id": loc.id,
            "name": loc.name,
            "recommended": ok,
            "reasons": reasons
        })

    # Empfohlen oben
    result.sort(key=lambda x: (not x["recommended"], x["name"].lower()))
    return result


from fastapi.responses import FileResponse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # Projekt-Root
FRONTEND_DIR = ROOT / "frontend"

@app.get("/")
def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")

from fastapi.staticfiles import StaticFiles

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static"
)