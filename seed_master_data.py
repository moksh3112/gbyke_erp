from app.database import SessionLocal
from app.models import ScooterModel, MasterColor, MasterBattery, Location
from sqlalchemy import or_
import uuid

def gen_uuid():
    return str(uuid.uuid4())

db = SessionLocal()

print("🌱 Starting Master Data Auto-Import...")

# ── 1. MODELS ──
models_data = [
    {"name": "Super 10/10",       "code": "SUPER1010"},
    {"name": "Super 12/10",       "code": "SUPER1210"},
    {"name": "DLX 10/10",         "code": "DLX1010"},
    {"name": "DLX 12/10",         "code": "DLX1210"},
    {"name": "BirdyGo NEO",       "code": "BIRDYNEO"},
    {"name": "ReadyGo 2.0 10/10", "code": "READY21010"},
    {"name": "ReadyGo 2.0 12/10", "code": "READY21210"},
    {"name": "BirdyGo 2.0 10/10", "code": "BIRDY21010"},
    {"name": "BirdyGo 2.0 12/10", "code": "BIRDY21210"},
    {"name": "X1",                "code": "GBX1"},
    {"name": "X1 Plus",           "code": "GBX1PLUS"},
    {"name": "X1 Pro",            "code": "GBX1PRO"},
    {"name": "X7",                "code": "GBX7"},
    {"name": "X5",                "code": "GBX5"},
    {"name": "X3",                "code": "GBX3"},
    {"name": "VesGo Gen-N",       "code": "VESGENN"},
    {"name": "X5 Pro",            "code": "GBX5PRO"},
    {"name": "X7 Pro",            "code": "GBX7PRO"},
    {"name": "GB-Rogue",          "code": "GBROGUE"}
]

print("\n📦 Importing Models...")
for m in models_data:
    existing = db.query(ScooterModel).filter(
        or_(ScooterModel.model_code == m["code"], ScooterModel.model_name == m["name"])
    ).first()
    
    if not existing:
        db.add(ScooterModel(id=gen_uuid(), model_name=m["name"], model_code=m["code"]))
        db.commit()
        print(f"  ✓ Added: {m['name']}")
    else:
        print(f"  ⏭️ Skipped: {m['name']} (Already exists)")

# ── 2. COLORS ──
colors_data = [
    "Matte Black", "Gloss Red", "Pearl White", "Nardo Grey", "Midnight Blue"
]
print("\n🎨 Importing Colors...")
for c in colors_data:
    if not db.query(MasterColor).filter(MasterColor.name == c).first():
        db.add(MasterColor(id=gen_uuid(), name=c))
        db.commit()
        print(f"  ✓ Added: {c}")
    else:
        print(f"  ⏭️ Skipped: {c} (Already exists)")

# ── 3. BATTERIES ──
batteries_data = [
    {"type": "Lead Acid", "power": "48V"},
    {"type": "Lead Acid", "power": "60V"},
    {"type": "Lead Acid", "power": "72V"},
    {"type": "Lithium Ion", "power": "60V 30Ah"},
    {"type": "Lithium Ion", "power": "72V 30Ah"},
]
print("\n🔋 Importing Battery Configurations...")
for b in batteries_data:
    if not db.query(MasterBattery).filter(
        MasterBattery.battery_type == b["type"], MasterBattery.power_spec == b["power"]
    ).first():
        db.add(MasterBattery(id=gen_uuid(), battery_type=b["type"], power_spec=b["power"]))
        db.commit()
        print(f"  ✓ Added: {b['type']} - {b['power']}")
    else:
        print(f"  ⏭️ Skipped: {b['type']} - {b['power']} (Already exists)")

# ── 4. LOCATIONS ──
locations_data = [
    {"name": "Dehradun Factory", "type": "factory",   "city": "Dehradun",  "state": "Uttarakhand"},
    {"name": "Delhi Hub",        "type": "warehouse", "city": "New Delhi", "state": "Delhi"},
    {"name": "Jaipur Godown",    "type": "godown",    "city": "Jaipur",    "state": "Rajasthan"}
]
print("\n🏢 Importing Locations...")
for l in locations_data:
    if not db.query(Location).filter(Location.name == l["name"]).first():
        db.add(Location(
            id=gen_uuid(), name=l["name"], location_type=l["type"], city=l["city"], state=l["state"]
        ))
        db.commit()
        print(f"  ✓ Added: {l['name']}")
    else:
        print(f"  ⏭️ Skipped: {l['name']} (Already exists)")

print("\n✅ Master Data import complete! Refresh your PyQt6 app to see the changes.")
db.close()