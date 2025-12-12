# test_api.py
from backend.services import trefle_service
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("TREFLE_API_TOKEN")
print(f"Nutze Token: {token[:5]}... (Länge: {len(token) if token else 0})")

# Test 1: Suche (Das ist das wichtigste für den User)
print("\n--- TEST 1: Suche nach 'Rose' ---")
plants = trefle_service.search_plants("Rose")

if plants:
    print(f"Erfolg! {len(plants)} Pflanzen gefunden.")
    first = plants[0]
    print(f"Erster Treffer: {first['common_name']} (ID: {first['id']})")
    
    # Test 2: Details holen
    print(f"\n--- TEST 2: Details für ID {first['id']} ---")
    details = trefle_service.get_plant_details(first['id'])
    print("Geholte Details:", details)
else:
    print("Keine Pflanzen gefunden. Prüfe Token und Internet.")