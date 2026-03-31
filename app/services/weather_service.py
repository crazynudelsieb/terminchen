"""Weather forecast overlay using the Open-Meteo API (free, no key required)."""

import json
import logging
import time
import urllib.request
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# Approximate coordinates for common IANA timezone cities.
# Mirrors the city list in holiday_service._TZ_CITY_TO_COUNTRY.
_TZ_CITY_TO_COORDS = {
    # Europe
    'Berlin': (52.52, 13.41), 'Vienna': (48.21, 16.37), 'Zurich': (47.38, 8.54),
    'Amsterdam': (52.37, 4.90), 'Brussels': (50.85, 4.35), 'Paris': (48.86, 2.35),
    'London': (51.51, -0.13), 'Dublin': (53.35, -6.26), 'Madrid': (40.42, -3.70),
    'Lisbon': (38.72, -9.14), 'Rome': (41.90, 12.50), 'Stockholm': (59.33, 18.07),
    'Oslo': (59.91, 10.75), 'Copenhagen': (55.68, 12.57), 'Helsinki': (60.17, 24.94),
    'Warsaw': (52.23, 21.01), 'Prague': (50.08, 14.44), 'Bratislava': (48.15, 17.11),
    'Budapest': (47.50, 19.04), 'Bucharest': (44.43, 26.10), 'Sofia': (42.70, 23.32),
    'Athens': (37.98, 23.73), 'Istanbul': (41.01, 28.98), 'Tallinn': (59.44, 24.75),
    'Riga': (56.95, 24.11), 'Vilnius': (54.69, 25.28), 'Zagreb': (45.81, 15.98),
    'Belgrade': (44.79, 20.47), 'Ljubljana': (46.06, 14.51), 'Kyiv': (50.45, 30.52),
    'Moscow': (55.76, 37.62),
    # Americas
    'New_York': (40.71, -74.01), 'Chicago': (41.88, -87.63), 'Denver': (39.74, -104.99),
    'Los_Angeles': (34.05, -118.24), 'Anchorage': (61.22, -149.90), 'Honolulu': (21.31, -157.86),
    'Phoenix': (33.45, -112.07), 'Detroit': (42.33, -83.05),
    'Toronto': (43.65, -79.38), 'Vancouver': (49.28, -123.12), 'Winnipeg': (49.90, -97.14),
    'Halifax': (44.65, -63.57), 'Edmonton': (53.55, -113.49), 'Montreal': (45.50, -73.57),
    'Mexico_City': (19.43, -99.13), 'Cancun': (21.16, -86.85),
    'Sao_Paulo': (-23.55, -46.63), 'Rio_Branco': (-9.97, -67.81),
    'Buenos_Aires': (-34.60, -58.38), 'Santiago': (-33.45, -70.67),
    'Lima': (-12.05, -77.04), 'Bogota': (4.71, -74.07),
    # Asia-Pacific
    'Tokyo': (35.68, 139.69), 'Seoul': (37.57, 126.98), 'Shanghai': (31.23, 121.47),
    'Hong_Kong': (22.32, 114.17), 'Taipei': (25.03, 121.57), 'Singapore': (1.35, 103.82),
    'Bangkok': (13.76, 100.50), 'Jakarta': (-6.21, 106.85),
    'Kolkata': (22.57, 88.36), 'Calcutta': (22.57, 88.36), 'Karachi': (24.86, 67.01),
    'Dhaka': (23.81, 90.41), 'Manila': (14.60, 120.98), 'Kuala_Lumpur': (3.14, 101.69),
    'Ho_Chi_Minh': (10.82, 106.63), 'Jerusalem': (31.77, 35.23), 'Tel_Aviv': (32.09, 34.78),
    'Dubai': (25.20, 55.27), 'Riyadh': (24.69, 46.72),
    # Oceania
    'Sydney': (-33.87, 151.21), 'Melbourne': (-37.81, 144.96), 'Brisbane': (-27.47, 153.03),
    'Perth': (-31.95, 115.86), 'Adelaide': (-34.93, 138.60), 'Hobart': (-42.88, 147.33),
    'Darwin': (-12.46, 130.84), 'Auckland': (-36.85, 174.76), 'Wellington': (-41.29, 174.78),
    # Africa
    'Johannesburg': (-26.20, 28.05), 'Cairo': (30.04, 31.24), 'Lagos': (6.52, 3.38),
    'Nairobi': (-1.29, 36.82), 'Casablanca': (33.57, -7.59), 'Tunis': (36.81, 10.18),
    'Algiers': (36.74, 3.09),
}

# WMO Weather Interpretation Codes → (emoji, short description)
_WMO_CODE_MAP = {
    0: ('\u2600\ufe0f', 'Clear sky'),
    1: ('\U0001f324', 'Mainly clear'), 2: ('\u26c5', 'Partly cloudy'), 3: ('\u2601\ufe0f', 'Overcast'),
    45: ('\U0001f32b\ufe0f', 'Fog'), 48: ('\U0001f32b\ufe0f', 'Rime fog'),
    51: ('\U0001f327\ufe0f', 'Light drizzle'), 53: ('\U0001f327\ufe0f', 'Drizzle'), 55: ('\U0001f327\ufe0f', 'Dense drizzle'),
    56: ('\U0001f327\ufe0f', 'Freezing drizzle'), 57: ('\U0001f327\ufe0f', 'Heavy freezing drizzle'),
    61: ('\U0001f327\ufe0f', 'Light rain'), 63: ('\U0001f327\ufe0f', 'Rain'), 65: ('\U0001f327\ufe0f', 'Heavy rain'),
    66: ('\U0001f327\ufe0f', 'Freezing rain'), 67: ('\U0001f327\ufe0f', 'Heavy freezing rain'),
    71: ('\u2744\ufe0f', 'Light snow'), 73: ('\u2744\ufe0f', 'Snow'), 75: ('\u2744\ufe0f', 'Heavy snow'),
    77: ('\u2744\ufe0f', 'Snow grains'),
    80: ('\U0001f326\ufe0f', 'Light showers'), 81: ('\U0001f326\ufe0f', 'Showers'), 82: ('\U0001f326\ufe0f', 'Heavy showers'),
    85: ('\U0001f328\ufe0f', 'Light snow showers'), 86: ('\U0001f328\ufe0f', 'Snow showers'),
    95: ('\u26c8\ufe0f', 'Thunderstorm'), 96: ('\u26c8\ufe0f', 'Thunderstorm w/ hail'),
    99: ('\u26c8\ufe0f', 'Heavy thunderstorm'),
}

_FALLBACK_WEATHER = ('\U0001f324', 'Unknown')

# Simple in-memory cache: (lat_rounded, lon_rounded) → (timestamp, data_dict)
_cache = {}
_CACHE_TTL = 3 * 60 * 60  # 3 hours


def _resolve_coords(calendar):
    """Determine (lat, lon) for a calendar, or None."""
    if calendar.weather_lat is not None and calendar.weather_lon is not None:
        return (calendar.weather_lat, calendar.weather_lon)
    tz = calendar.timezone
    if not tz or '/' not in tz:
        return None
    city = tz.rsplit('/', 1)[-1]
    return _TZ_CITY_TO_COORDS.get(city)


def _get_cached_or_fetch(lat, lon):
    """Return date-keyed weather dict, using cache when fresh."""
    key = (round(lat, 2), round(lon, 2))
    now = time.time()
    cached = _cache.get(key)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={key[0]}&longitude={key[1]}"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min"
        f"&timezone=auto&forecast_days=14"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("weather.fetch_error", extra={"lat": lat, "lon": lon, "error": str(e)})
        return cached[1] if cached else {}

    daily = data.get('daily', {})
    dates = daily.get('time', [])
    codes = daily.get('weather_code', [])
    highs = daily.get('temperature_2m_max', [])
    lows = daily.get('temperature_2m_min', [])

    result = {}
    for i, d in enumerate(dates):
        code = codes[i] if i < len(codes) else None
        icon, desc = _WMO_CODE_MAP.get(code, _FALLBACK_WEATHER)
        result[d] = {
            'icon': icon,
            'description': desc,
            'temp_high': highs[i] if i < len(highs) else None,
            'temp_low': lows[i] if i < len(lows) else None,
        }

    _cache[key] = (now, result)
    return result


def get_weather_for_date_range(calendar, start_date, end_date):
    """Get weather forecast for dates in [start_date, end_date).

    Returns:
        dict mapping date strings (YYYY-MM-DD) to weather dicts
        with keys: icon, description, temp_high, temp_low
    """
    coords = _resolve_coords(calendar)
    if not coords:
        return {}

    all_weather = _get_cached_or_fetch(*coords)
    if not all_weather:
        return {}

    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    return {d: w for d, w in all_weather.items() if start_str <= d < end_str}


def get_upcoming_weather(calendar, days_ahead=14):
    """Get upcoming weather as a flat sorted list for agenda view.

    Returns:
        list of dicts with keys: date_str, date_obj, icon, description, temp_high, temp_low
    """
    coords = _resolve_coords(calendar)
    if not coords:
        return []

    all_weather = _get_cached_or_fetch(*coords)
    if not all_weather:
        return []

    today = date.today()
    end = today + timedelta(days=days_ahead)
    result = []
    for d_str, w in sorted(all_weather.items()):
        d_obj = date.fromisoformat(d_str)
        if today <= d_obj <= end:
            result.append({
                'date_str': d_str,
                'date_obj': d_obj,
                'icon': w['icon'],
                'description': w['description'],
                'temp_high': w['temp_high'],
                'temp_low': w['temp_low'],
            })
    return result
