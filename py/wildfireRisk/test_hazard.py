# test file for hazard map queries
# can get rid of this later, keep this to test if needed

from fire_hazard_service import query_fire_hazard_zone

test_points = [
    # --- LRA (local areas, cities + WUI edges) ---
    ("Malibu (LRA - coastal hills)", 34.0259, -118.7798),
    ("Paradise town center (LRA)", 39.7596, -121.6219),
    ("Altadena foothills", 34.1897, -118.1312),

    # --- SRA (state wildland areas) ---
    ("Auburn foothills", 38.8966, -121.0769),
    ("Grass Valley outskirts", 39.2191, -121.0611),
    ("Oakhurst (near Yosemite)", 37.3280, -119.6493),
    ("Arnold (Sierra foothills)", 38.2555, -120.3510),

    # --- FEDERAL (national parks / forests) ---
    ("Yosemite Valley", 37.8651, -119.5383),
    ("Sequoia National Park", 36.4864, -118.5658),
    ("Lake Tahoe Basin (forest area)", 39.0968, -120.0324),

    # --- UNZONED / transitional ---
    ("Remote Sierra Nevada ridge", 37.5, -119.5),
    ("Northern CA forest edge", 41.2, -123.7),

    # --- EXPECTED UNKNOWN (urban cores) ---
    ("Downtown LA", 34.0522, -118.2437),
    ("San Francisco downtown", 37.7749, -122.4194),
    ("Sacramento downtown", 38.5816, -121.4944),
]

for name, lat, lon in test_points:
    result = query_fire_hazard_zone(lat, lon)
    print(f"\n{name} ({lat}, {lon})")
    print(f"Zone: {result.get('hazard_zone')}")
    print(f"Layer: {result.get('source_layer')}")