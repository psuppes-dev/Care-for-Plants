# backend/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import date, timedelta
from pydantic import BaseModel
from auth import router as auth_router, require_login
from passlib.context import CryptContext
from database import SessionLocal  
from models import User
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Eigene Module
import models, database
from services import trefle_service

# Datenbank Tabellen erstellen
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Care For Plants API")
app.include_router(auth_router, prefix="/auth")

BASE_DIR = Path(__file__).resolve().parent.parent  # Repo-Root 
FRONTEND_DIR = BASE_DIR / "frontend"

# serve /img/... -> frontend/img/...
app.mount("/img", StaticFiles(directory=FRONTEND_DIR / "img"), name="img")

# Testuser seeden
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def seed_test_users():
    db = SessionLocal()
    try:
        def ensure(username: str, pw: str):
            u = db.query(User).filter(User.username == username).first()
            if not u:
                db.add(User(username=username, password_hash=pwd_ctx.hash(pw)))
                db.commit()

        ensure("student", "student123")
        ensure("tutor", "tutor123")
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    seed_test_users()

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
def create_location(payload: LocationCreate,user_id: int = Depends(require_login),db: Session = Depends(get_db)):
    """Erstellt einen Standort mit detaillierten Umweltbedingungen (pro User)"""

    db_loc = models.Location(
        user_id=user_id,                     
        name=payload.name,
        light_level=payload.light_level,
        humidity_level=payload.humidity_level,
        temperature_avg=payload.temperature_avg,
        available_space_cm=payload.available_space_cm,
        has_pets_or_children=payload.has_pets_or_children
        )
    db.add(db_loc)
    db.commit()
    db.refresh(db_loc)
    return db_loc

@app.get("/locations/")
def get_locations(user_id: int = Depends(require_login),db: Session = Depends(get_db)):
    return db.query(models.Location).filter(models.Location.user_id == user_id).all()

@app.post("/my-plants/")
def create_my_plant(payload: MyPlantCreate,user_id: int = Depends(require_login),db: Session = Depends(get_db)):
    # 0) Safety: Standort muss dem User gehören
    location = db.query(models.Location).filter(
        models.Location.id == payload.location_id,
        models.Location.user_id == user_id
    ).first()
    if not location:
        raise HTTPException(status_code=404, detail="Standort nicht gefunden oder gehört nicht zum User")

    # 1) PlantInfo (global/shared) prüfen ob lokal vorhanden
    db_info = db.query(models.PlantInfo).filter(
        models.PlantInfo.trefle_id == payload.trefle_id
    ).first()

    if not db_info:
        # 2) Importieren von Trefle
        details = trefle_service.get_plant_details(payload.trefle_id)
        if not details:
            raise HTTPException(status_code=404, detail="Pflanze bei Trefle nicht gefunden")

        db_info = models.PlantInfo(
            trefle_id=payload.trefle_id,
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

    # 3) User-Pflanze anlegen (user_id setzen!)
    new_plant = models.MyPlant(
        user_id=user_id,                   # ⭐ WICHTIG
        nickname=payload.nickname,
        location_id=payload.location_id,
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
    db.refresh(new_plant)

    return {"status": "created", "plant": new_plant.nickname, "id": new_plant.id}


@app.post("/wishlist/")
def add_to_wishlist(
    payload: WishlistCreate,
    user_id: int = Depends(require_login),
    db: Session = Depends(get_db)
):
    # 1) schon vorhanden?
    exists = (
        db.query(models.Wishlist)
        .filter(
            models.Wishlist.user_id == user_id,
            models.Wishlist.trefle_id == payload.trefle_id
        )
        .first()
    )
    if exists:
        return {"status": "exists", "id": exists.id}

    # 2) plant_info holen/erstellen (dein bisheriger Code bleibt)
    db_info = db.query(models.PlantInfo).filter(models.PlantInfo.trefle_id == payload.trefle_id).first()
    if not db_info:
        details = trefle_service.get_plant_details(payload.trefle_id)
        if not details:
            raise HTTPException(status_code=404, detail="Pflanze nicht gefunden")
        db_info = models.PlantInfo(
            trefle_id=payload.trefle_id,
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
            is_toxic=details["is_toxic"],
        )
        db.add(db_info)
        db.commit()
        db.refresh(db_info)

    # 3) wishlist item anlegen
    item = models.Wishlist(
        user_id=user_id,
        trefle_id=payload.trefle_id,
        plant_info_id=db_info.id
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return {"status": "added", "id": item.id}

@app.get("/wishlist/")
def get_wishlist(user_id: int = Depends(require_login),db: Session = Depends(get_db)):
    """Gibt die Wunschliste mit ERWEITERTER Standort-Kompatibilität zurück"""
    wishlist = db.query(models.Wishlist).filter(models.Wishlist.user_id == user_id).all()
    locations = db.query(models.Location).filter(models.Location.user_id == user_id).all()
    
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

@app.delete("/wishlist/{wishlist_id}")
def delete_wishlist_item(
    wishlist_id: int,
    user_id: int = Depends(require_login),
    db: Session = Depends(get_db)
):
    item = db.query(models.Wishlist).filter(
        models.Wishlist.id == wishlist_id,
        models.Wishlist.user_id == user_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")

    db.delete(item)
    db.commit()
    return {"ok": True}


@app.put("/wishlist/{item_id}/plant-info")
def update_plant_info(item_id: int,updates: PlantInfoUpdate,user_id: int = Depends(require_login),db: Session = Depends(get_db)):
    """Eigenschaften einer Pflanze in der Wunschliste manuell bearbeiten (pro User)"""

    wishlist_item = db.query(models.Wishlist).filter(
        models.Wishlist.id == item_id,
        models.Wishlist.user_id == user_id
    ).first()

    if not wishlist_item:
        raise HTTPException(status_code=404, detail="Nicht gefunden")

    plant_info = wishlist_item.plant_info

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
def get_location_details(
    location_id: int,
    user_id: int = Depends(require_login),
    db: Session = Depends(get_db)
):
    """Zeigt alle Pflanzen an einem Standort + passende Wunschlistenpflanzen (pro User)"""

    # Standort nur laden, wenn er dem User gehört
    location = db.query(models.Location).filter(
        models.Location.id == location_id,
        models.Location.user_id == user_id
    ).first()

    if not location:
        raise HTTPException(status_code=404, detail="Standort nicht gefunden")

    # Tatsächliche Pflanzen am Standort (nur dieses Users, extra-safe)
    actual_plants = []
    for plant in location.my_plants:
        # Falls Relationship nicht gefiltert ist, sichern wir per user_id ab
        if getattr(plant, "user_id", user_id) != user_id:
            continue

        actual_plants.append({
            "id": plant.id,
            "nickname": plant.nickname,
            "species": plant.plant_info.common_name or plant.plant_info.scientific_name,
            "image": plant.plant_info.image_url
        })

    # Wunschlisten-Pflanzen nur vom User
    wishlist = db.query(models.Wishlist).filter(models.Wishlist.user_id == user_id).all()
    compatible_wishlist = []

    for item in wishlist:
        plant = item.plant_info
        is_compatible = True

        # Licht-Check
        if abs(plant.sunlight_requirement - location.light_level) > 2:
            is_compatible = False

        # Luftfeuchtigkeit-Check
        if abs(plant.humidity_requirement - location.humidity_level) > 2:
            is_compatible = False

        # Temperatur-Check
        if location.temperature_avg < plant.temperature_min or location.temperature_avg > plant.temperature_max:
            is_compatible = False

        # Platz-Check
        if plant.max_height_cm > location.available_space_cm:
            is_compatible = False

        # Giftigkeit-Check
        if plant.is_toxic and location.has_pets_or_children:
            is_compatible = False

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
def dashboard_tasks(user_id: int = Depends(require_login),db: Session = Depends(get_db)):
    tasks = []
    my_plants = db.query(models.MyPlant).filter(models.MyPlant.user_id == user_id).all()
    
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

#Helper
def get_user_plant(db: Session, plant_id: int, user_id: int):
    plant = db.query(models.MyPlant).filter(
        models.MyPlant.id == plant_id,
        models.MyPlant.user_id == user_id
    ).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Pflanze nicht gefunden")
    return plant

@app.post("/my-plants/{plant_id}/water")
def water_plant(
    plant_id: int,
    user_id: int = Depends(require_login),
    db: Session = Depends(get_db)
):
    """Markiert eine Pflanze als gegossen (pro User)"""
    plant = get_user_plant(db, plant_id, user_id)
    plant.last_watered = date.today()
    db.commit()
    return {"status": "success", "plant": plant.nickname, "watered_on": str(date.today())}


@app.post("/my-plants/{plant_id}/fertilize")
def fertilize_plant(
    plant_id: int,
    user_id: int = Depends(require_login),
    db: Session = Depends(get_db)
):
    """Markiert eine Pflanze als gedüngt (pro User)"""
    plant = get_user_plant(db, plant_id, user_id)
    plant.last_fertilized = date.today()
    db.commit()
    return {"status": "success", "plant": plant.nickname, "fertilized_on": str(date.today())}


@app.post("/my-plants/{plant_id}/repot")
def repot_plant(
    plant_id: int,
    user_id: int = Depends(require_login),
    db: Session = Depends(get_db)
):
    """Markiert eine Pflanze als umgetopft (pro User)"""
    plant = get_user_plant(db, plant_id, user_id)
    plant.last_repotted = date.today()
    db.commit()
    return {"status": "success", "plant": plant.nickname, "repotted_on": str(date.today())}


@app.post("/my-plants/{plant_id}/prune")
def prune_plant(
    plant_id: int,
    user_id: int = Depends(require_login),
    db: Session = Depends(get_db)
):
    """Markiert eine Pflanze als geschnitten (pro User)"""
    plant = get_user_plant(db, plant_id, user_id)
    plant.last_pruned = date.today()
    db.commit()
    return {"status": "success", "plant": plant.nickname, "pruned_on": str(date.today())}


@app.post("/my-plants/{plant_id}/propagate")
def propagate_plant(
    plant_id: int,
    user_id: int = Depends(require_login),
    db: Session = Depends(get_db)
):
    """Markiert eine Pflanze als vermehrt (pro User)"""
    plant = get_user_plant(db, plant_id, user_id)
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
def delete_my_plant(plant_id: int,user_id: int = Depends(require_login),db: Session = Depends(get_db)):
    plant = db.query(models.MyPlant).filter(
        models.MyPlant.id == plant_id,
        models.MyPlant.user_id == user_id
    ).first()

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