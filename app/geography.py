from __future__ import annotations


US_STATE_BOUNDS = {
    "Alabama": (30.1, 35.1, -88.6, -84.9),
    "Alaska": (51.2, 71.5, -179.2, -129.9),
    "Arizona": (31.2, 37.1, -114.9, -109.0),
    "Arkansas": (33.0, 36.6, -94.7, -89.6),
    "California": (32.5, 42.1, -124.5, -114.1),
    "Colorado": (37.0, 41.1, -109.1, -102.0),
    "Connecticut": (40.9, 42.1, -73.8, -71.8),
    "Delaware": (38.4, 39.9, -75.8, -75.0),
    "Florida": (24.3, 31.1, -87.7, -80.0),
    "Georgia": (30.3, 35.1, -85.7, -80.8),
    "Hawaii": (18.8, 22.3, -160.3, -154.7),
    "Idaho": (42.0, 49.1, -117.3, -111.0),
    "Illinois": (36.9, 42.6, -91.6, -87.0),
    "Indiana": (37.7, 41.8, -88.2, -84.7),
    "Iowa": (40.3, 43.6, -96.7, -90.1),
    "Kansas": (36.9, 40.1, -102.1, -94.5),
    "Kentucky": (36.4, 39.2, -89.6, -81.9),
    "Louisiana": (28.9, 33.1, -94.1, -88.8),
    "Maine": (42.9, 47.5, -71.1, -66.8),
    "Maryland": (37.8, 39.8, -79.6, -75.0),
    "Massachusetts": (41.2, 42.9, -73.6, -69.9),
    "Michigan": (41.7, 48.4, -90.5, -82.1),
    "Minnesota": (43.4, 49.4, -97.3, -89.5),
    "Mississippi": (30.1, 35.1, -91.7, -88.1),
    "Missouri": (35.9, 40.7, -95.8, -89.1),
    "Montana": (44.3, 49.1, -116.1, -104.0),
    "Nebraska": (39.9, 43.1, -104.1, -95.3),
    "Nevada": (35.0, 42.1, -120.1, -114.0),
    "New Hampshire": (42.7, 45.4, -72.6, -70.6),
    "New Jersey": (38.9, 41.4, -75.6, -73.9),
    "New Mexico": (31.2, 37.1, -109.1, -103.0),
    "New York": (40.4, 45.1, -79.8, -71.8),
    "North Carolina": (33.8, 36.7, -84.4, -75.4),
    "North Dakota": (45.9, 49.1, -104.1, -96.5),
    "Ohio": (38.3, 42.1, -84.9, -80.5),
    "Oklahoma": (33.6, 37.1, -103.1, -94.4),
    "Oregon": (42.0, 46.4, -124.7, -116.4),
    "Pennsylvania": (39.7, 42.6, -80.6, -74.6),
    "Rhode Island": (41.1, 42.1, -71.9, -71.0),
    "South Carolina": (32.0, 35.3, -83.4, -78.5),
    "South Dakota": (42.4, 45.9, -104.1, -96.4),
    "Tennessee": (34.9, 36.7, -90.4, -81.6),
    "Texas": (25.8, 36.6, -106.7, -93.5),
    "Utah": (36.9, 42.1, -114.1, -109.0),
    "Vermont": (42.7, 45.1, -73.5, -71.4),
    "Virginia": (36.5, 39.5, -83.8, -75.2),
    "Washington": (45.5, 49.1, -124.9, -116.9),
    "West Virginia": (37.1, 40.7, -82.7, -77.7),
    "Wisconsin": (42.4, 47.1, -92.9, -86.8),
    "Wyoming": (40.9, 45.1, -111.1, -104.0),
}


COUNTRY_BOUNDS = {
    "Canada": (41.6, 83.2, -141.1, -52.6),
    "Mexico": (14.5, 32.8, -118.5, -86.5),
    "Brazil": (-34.0, 5.3, -74.0, -34.0),
    "Argentina": (-55.2, -21.8, -73.6, -53.6),
    "Chile": (-56.0, -17.5, -76.0, -66.0),
    "Colombia": (-4.3, 13.6, -79.1, -66.8),
    "United Kingdom": (49.8, 60.9, -8.7, 1.9),
    "Ireland": (51.3, 55.5, -10.7, -5.4),
    "France": (41.2, 51.2, -5.3, 9.7),
    "Spain": (35.8, 43.9, -9.5, 4.4),
    "Portugal": (36.8, 42.2, -9.6, -6.1),
    "Germany": (47.2, 55.1, 5.8, 15.1),
    "Netherlands": (50.7, 53.7, 3.3, 7.3),
    "Belgium": (49.4, 51.6, 2.5, 6.5),
    "Italy": (35.4, 47.1, 6.6, 18.6),
    "Switzerland": (45.8, 47.9, 5.9, 10.6),
    "Austria": (46.3, 49.1, 9.5, 17.2),
    "Poland": (49.0, 54.9, 14.1, 24.2),
    "Norway": (57.8, 71.4, 4.5, 31.2),
    "Sweden": (55.0, 69.1, 10.9, 24.2),
    "Finland": (59.7, 70.1, 20.5, 31.6),
    "Denmark": (54.5, 57.9, 8.0, 15.2),
    "Australia": (-44.0, -10.0, 112.0, 154.0),
    "New Zealand": (-47.5, -34.0, 166.0, 179.9),
    "Japan": (24.0, 46.0, 122.0, 146.0),
    "South Korea": (33.0, 39.0, 124.0, 132.0),
    "China": (18.0, 54.0, 73.0, 135.0),
    "India": (6.0, 36.0, 68.0, 98.0),
    "South Africa": (-35.0, -22.0, 16.0, 33.0),
}


def location_bucket(lat: float | None, lon: float | None) -> tuple[str, str]:
    if lat is None or lon is None:
        return "Unknown", "Unknown"
    state = us_state(lat, lon)
    if state:
        return "US State", state
    return "Country", country(lat, lon)


def us_state(lat: float, lon: float) -> str | None:
    for state, (min_lat, max_lat, min_lon, max_lon) in US_STATE_BOUNDS.items():
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return state
    return None


def continent(lat: float, lon: float) -> str:
    if -60 <= lat <= 85 and -170 <= lon <= -30:
        return "North America" if lat >= 7 else "South America"
    if -56 <= lat <= 13 and -82 <= lon <= -34:
        return "South America"
    if -35 <= lat <= 38 and -18 <= lon <= 52:
        return "Africa"
    if 35 <= lat <= 72 and -25 <= lon <= 45:
        return "Europe"
    if -11 <= lat <= 80 and 45 <= lon <= 180:
        return "Asia"
    if -48 <= lat <= -5 and 110 <= lon <= 180:
        return "Oceania"
    if lat < -60:
        return "Antarctica"
    return "Unknown"


def country(lat: float, lon: float) -> str:
    if us_state(lat, lon):
        return "United States"
    for name, (min_lat, max_lat, min_lon, max_lon) in COUNTRY_BOUNDS.items():
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return name
    fallback = continent(lat, lon)
    return f"Unknown ({fallback})" if fallback != "Unknown" else "Unknown"
