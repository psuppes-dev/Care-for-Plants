# backend/models.py
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base

# 1. Katalog: Hier speichern wir die Pflanzen - KOMPLETT ERWEITERT!
class PlantInfo(Base):
    __tablename__ = "plant_infos"
    
    id = Column(Integer, primary_key=True, index=True)
    trefle_id = Column(Integer, unique=True)
    scientific_name = Column(String)
    common_name = Column(String)
    image_url = Column(String)
    
    # Pflegeanforderungen
    water_frequency_days = Column(Integer, default=7)
    fertilize_frequency_days = Column(Integer, default=30)
    repot_frequency_days = Column(Integer, default=730)
    prune_frequency_days = Column(Integer, default=90)
    propagate_frequency_days = Column(Integer, default=180)  

    
    # NEUE Eigenschaften für Kompatibilität
    sunlight_requirement = Column(Integer, default=5)  # 1-10
    humidity_requirement = Column(Integer, default=5)  # 1-10 (1=trocken, 10=feucht)
    temperature_min = Column(Integer, default=15)      # Grad Celsius
    temperature_max = Column(Integer, default=25)      # Grad Celsius
    max_height_cm = Column(Integer, default=100)       # Maximale Höhe
    soil_type = Column(String, default="universal")    # z.B. "universal", "sandig", "lehmig"
    is_toxic = Column(Boolean, default=False)          # Giftig für Haustiere/Kinder?
    
    my_plants = relationship("MyPlant", back_populates="plant_info")

# 2. Standort: Wo stehen die Pflanzen? - ERWEITERT!
class Location(Base):
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    
    # Standorteigenschaften
    light_level = Column(Integer, default=5)           # 1-10
    humidity_level = Column(Integer, default=5)        # 1-10
    temperature_avg = Column(Integer, default=20)      # Durchschnittstemperatur
    available_space_cm = Column(Integer, default=200)  # Verfügbare Höhe
    has_pets_or_children = Column(Boolean, default=False)  # Haustiere/Kinder?
    
    my_plants = relationship("MyPlant", back_populates="location")

# 3. Meine Pflanzen: Die konkrete Instanz
class MyPlant(Base):
    __tablename__ = "my_plants"
    
    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String)
    date_acquired = Column(Date)
    
    # Pflegedaten
    last_watered = Column(Date)
    last_fertilized = Column(Date, nullable=True)
    last_repotted = Column(Date, nullable=True)
    last_pruned = Column(Date, nullable=True)
    last_propagated = Column(Date, nullable=True)

    
    plant_info_id = Column(Integer, ForeignKey("plant_infos.id"))
    location_id = Column(Integer, ForeignKey("locations.id"))
    
    plant_info = relationship("PlantInfo", back_populates="my_plants")
    location = relationship("Location", back_populates="my_plants")

# 4. Wunschliste: Pflanzen die der User haben möchte
class Wishlist(Base):
    __tablename__ = "wishlist"
    
    id = Column(Integer, primary_key=True, index=True)
    trefle_id = Column(Integer, unique=True)
    plant_info_id = Column(Integer, ForeignKey("plant_infos.id"))
    added_date = Column(Date)
    
    plant_info = relationship("PlantInfo")