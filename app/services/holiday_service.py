"""Public holiday lookup service using the `holidays` package."""

import logging
from collections import defaultdict
from datetime import date, timedelta

import holidays

logger = logging.getLogger(__name__)

# Curated mapping of IANA timezone city → ISO 3166-1 alpha-2 country code.
# Only maps the most common timezones; less common ones fall back to None.
_TZ_CITY_TO_COUNTRY = {
    # Europe
    'Berlin': 'DE', 'Vienna': 'AT', 'Zurich': 'CH', 'Amsterdam': 'NL',
    'Brussels': 'BE', 'Paris': 'FR', 'London': 'GB', 'Dublin': 'IE',
    'Madrid': 'ES', 'Lisbon': 'PT', 'Rome': 'IT', 'Stockholm': 'SE',
    'Oslo': 'NO', 'Copenhagen': 'DK', 'Helsinki': 'FI', 'Warsaw': 'PL',
    'Prague': 'CZ', 'Bratislava': 'SK', 'Budapest': 'HU', 'Bucharest': 'RO',
    'Sofia': 'BG', 'Athens': 'GR', 'Istanbul': 'TR', 'Tallinn': 'EE',
    'Riga': 'LV', 'Vilnius': 'LT', 'Zagreb': 'HR', 'Belgrade': 'RS',
    'Ljubljana': 'SI', 'Kyiv': 'UA', 'Moscow': 'RU',
    # Americas
    'New_York': 'US', 'Chicago': 'US', 'Denver': 'US', 'Los_Angeles': 'US',
    'Anchorage': 'US', 'Honolulu': 'US', 'Phoenix': 'US', 'Detroit': 'US',
    'Toronto': 'CA', 'Vancouver': 'CA', 'Winnipeg': 'CA', 'Halifax': 'CA',
    'Edmonton': 'CA', 'Montreal': 'CA',
    'Mexico_City': 'MX', 'Cancun': 'MX',
    'Sao_Paulo': 'BR', 'Rio_Branco': 'BR',
    'Buenos_Aires': 'AR', 'Santiago': 'CL', 'Lima': 'PE', 'Bogota': 'CO',
    # Asia-Pacific
    'Tokyo': 'JP', 'Seoul': 'KR', 'Shanghai': 'CN', 'Hong_Kong': 'HK',
    'Taipei': 'TW', 'Singapore': 'SG', 'Bangkok': 'TH', 'Jakarta': 'ID',
    'Kolkata': 'IN', 'Calcutta': 'IN', 'Karachi': 'PK', 'Dhaka': 'BD',
    'Manila': 'PH', 'Kuala_Lumpur': 'MY', 'Ho_Chi_Minh': 'VN',
    'Jerusalem': 'IL', 'Tel_Aviv': 'IL', 'Dubai': 'AE', 'Riyadh': 'SA',
    # Oceania
    'Sydney': 'AU', 'Melbourne': 'AU', 'Brisbane': 'AU', 'Perth': 'AU',
    'Adelaide': 'AU', 'Hobart': 'AU', 'Darwin': 'AU',
    'Auckland': 'NZ', 'Wellington': 'NZ',
    # Africa
    'Johannesburg': 'ZA', 'Cairo': 'EG', 'Lagos': 'NG', 'Nairobi': 'KE',
    'Casablanca': 'MA', 'Tunis': 'TN', 'Algiers': 'DZ',
}

_SUPPORTED_COUNTRIES = None


def detect_country_from_timezone(tz_name):
    """Derive ISO country code from an IANA timezone name.

    Returns 2-letter code or None if unrecognized.
    """
    if not tz_name or '/' not in tz_name:
        return None
    # Try the city part (last segment after /)
    city = tz_name.rsplit('/', 1)[-1]
    code = _TZ_CITY_TO_COUNTRY.get(city)
    if code and code in _get_supported_set():
        return code
    return None


def _get_supported_set():
    """Cached set of country codes supported by the holidays package."""
    global _SUPPORTED_COUNTRIES
    if _SUPPORTED_COUNTRIES is None:
        _SUPPORTED_COUNTRIES = set(holidays.list_supported_countries().keys())
    return _SUPPORTED_COUNTRIES


def get_supported_countries():
    """Return sorted list of (code, name) tuples for the settings dropdown."""
    raw = holidays.list_supported_countries()
    items = sorted(raw.items(), key=lambda x: x[1])
    return [('', 'Auto-detect from timezone')] + [(code, f'{name} ({code})') for code, name in items]


def _resolve_country(calendar):
    """Determine the effective country code for a calendar."""
    if calendar.holiday_country:
        if calendar.holiday_country in _get_supported_set():
            return calendar.holiday_country
        logger.warning("holiday.unsupported_country", extra={
            "calendar_id": str(calendar.id), "country": calendar.holiday_country
        })
        return None
    return detect_country_from_timezone(calendar.timezone)


def get_holidays_for_date_range(calendar, start_date, end_date):
    """Get public holidays within a date range for a calendar.

    Returns:
        dict mapping date strings (YYYY-MM-DD) to list of dicts
        with keys: name, country_code
    """
    country = _resolve_country(calendar)
    if not country:
        return {}

    # Gather all years in the range
    years = set()
    d = start_date
    while d < end_date:
        years.add(d.year)
        d += timedelta(days=1)

    try:
        country_holidays = holidays.country_holidays(country, years=years)
    except Exception as e:
        logger.warning("holiday.fetch_error", extra={
            "calendar_id": str(calendar.id), "country": country, "error": str(e)
        })
        return {}

    result = defaultdict(list)
    for hdate, hname in sorted(country_holidays.items()):
        if start_date <= hdate < end_date:
            result[hdate.strftime('%Y-%m-%d')].append({
                'name': hname,
                'country_code': country,
            })

    return dict(result)


def get_upcoming_holidays(calendar, days_ahead=90):
    """Get upcoming public holidays as a flat sorted list.

    Returns:
        list of dicts with keys: date_str, date_obj, name, country_code
    """
    today = date.today()
    end = today + timedelta(days=days_ahead)

    country = _resolve_country(calendar)
    if not country:
        return []

    years = {today.year}
    if end.year != today.year:
        years.add(end.year)

    try:
        country_holidays = holidays.country_holidays(country, years=years)
    except Exception:
        return []

    result = []
    for hdate, hname in sorted(country_holidays.items()):
        if today <= hdate <= end:
            result.append({
                'date_str': hdate.strftime('%Y-%m-%d'),
                'date_obj': hdate,
                'name': hname,
                'country_code': country,
            })

    return result
