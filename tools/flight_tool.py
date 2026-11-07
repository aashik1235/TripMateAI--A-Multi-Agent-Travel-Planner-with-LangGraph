import os
import re
import requests
import certifi
import airportsdata
import pycountry

from datetime import date
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
BASE_URL = "https://api.aviationstack.com/v1/flightsFuture"
DEFAULT_ORIGIN = "KTM"
AIRPORTS_DATA = airportsdata.load("IATA")

COUNTRY_ALIAS = {
    "NEPAL": "NP", "INDONESIA": "ID", "INDIA": "IN",
    "USA": "US", "UNITED STATES": "US", "UK": "GB",
    "UNITED KINGDOM": "GB", "UAE": "AE",
    "UNITED ARAB EMIRATES": "AE", "AUSTRALIA": "AU",
    "CANADA": "CA", "JAPAN": "JP", "CHINA": "CN",
    "SINGAPORE": "SG", "MALAYSIA": "MY", "THAILAND": "TH",
    "GERMANY": "DE", "FRANCE": "FR", "ITALY": "IT",
    "SPAIN": "ES", "SOUTH KOREA": "KR", "SOUTH AFRICA": "ZA",
    "BANGLADESH": "BD", "PAKISTAN": "PK", "SRI LANKA": "LK",
    "BHUTAN": "BT", "QATAR": "QA", "SAUDI ARABIA": "SA",
    "TURKEY": "TR", "TÜRKIYE": "TR", "NEW ZEALAND": "NZ",
    "PHILIPPINES": "PH", "VIETNAM": "VN", "NETHERLANDS": "NL",
    "SWITZERLAND": "CH", "PORTUGAL": "PT", "BRAZIL": "BR",
    "MEXICO": "MX",
}

CITY_MAIN_AIRPORTS = {
    "KATHMANDU": "KTM", "POKHARA": "PKR", "BIRATNAGAR": "BIR",
    "JAKARTA": "CGK", "BALI": "DPS", "DENPASAR": "DPS",
    "SURABAYA": "SUB", "DELHI": "DEL", "NEW DELHI": "DEL",
    "MUMBAI": "BOM", "BANGALORE": "BLR", "BENGALURU": "BLR",
    "CHENNAI": "MAA", "KOLKATA": "CCU", "DHAKA": "DAC",
    "NEW YORK": "JFK", "LOS ANGELES": "LAX",
    "SAN FRANCISCO": "SFO", "CHICAGO": "ORD",
    "LONDON": "LHR", "DUBAI": "DXB", "ABU DHABI": "AUH",
    "SINGAPORE": "SIN", "KUALA LUMPUR": "KUL", "BANGKOK": "BKK",
    "TOKYO": "HND", "OSAKA": "KIX", "SYDNEY": "SYD",
    "MELBOURNE": "MEL", "TORONTO": "YYZ", "VANCOUVER": "YVR",
    "PARIS": "CDG", "BERLIN": "BER", "FRANKFURT": "FRA",
    "ROME": "FCO", "MADRID": "MAD", "AMSTERDAM": "AMS",
    "ZURICH": "ZRH",
}

COUNTRY_MAIN_AIRPORTS = {
    "NP": "KTM", "ID": "CGK", "IN": "DEL", "US": "JFK",
    "GB": "LHR", "AE": "DXB", "SG": "SIN", "MY": "KUL",
    "TH": "BKK", "JP": "HND", "AU": "SYD", "CA": "YYZ",
    "DE": "FRA", "FR": "CDG", "IT": "FCO", "ES": "MAD",
    "CN": "PEK", "KR": "ICN", "BD": "DAC", "PK": "ISB",
    "LK": "CMB", "BT": "PBH", "QA": "DOH", "SA": "JED",
    "TR": "IST", "NZ": "AKL", "PH": "MNL", "VN": "SGN",
    "NL": "AMS", "CH": "ZRH", "PT": "LIS", "BR": "GRU",
    "MX": "MEX", "ZA": "JNB",
}


def country_name_to_code(country_name):
    country_name = country_name.strip().upper()
    if country_name in COUNTRY_ALIAS:
        return COUNTRY_ALIAS[country_name]
    try:
        return pycountry.countries.lookup(country_name).alpha_2
    except LookupError:
        return None


def airport_country_matches(airport_code, country_code):
    airport = AIRPORTS_DATA.get(airport_code.upper())
    return bool(airport and airport.get("country") == country_code)


def get_best_airport_for_country(country_code):
    preferred = COUNTRY_MAIN_AIRPORTS.get(country_code)
    if preferred and airport_country_matches(preferred, country_code):
        return preferred
    for code, airport in AIRPORTS_DATA.items():
        if airport.get("country") == country_code:
            return code
    return None


def resolve_location_to_iata(location):
    location = location.strip().upper()
    if location in CITY_MAIN_AIRPORTS:
        code = CITY_MAIN_AIRPORTS[location]
        if code in AIRPORTS_DATA:
            return code
    country_code = country_name_to_code(location)
    return get_best_airport_for_country(country_code) if country_code else None


def find_location_mentions(query):
    query = query.upper()
    known = list(CITY_MAIN_AIRPORTS) + list(COUNTRY_ALIAS)
    found = []
    for location in set(known):
        match = re.search(r"\b" + re.escape(location) + r"\b", query)
        if match:
            found.append((match.start(), location))
    found.sort(key=lambda item: item[0])
    result = []
    for _, location in found:
        if location not in result:
            result.append(location)
    return result


def parse_route_from_query(query):
    query = query.upper()
    match = re.search(
        r"\bFROM\s+(.+?)\s+TO\s+(.+?)(?:\s+(?:INCLUDING|WITH|FOR|UNDER|BUDGET|AND)\b|$)",
        query,
    )
    if match:
        origins = find_location_mentions(match.group(1))
        destinations = find_location_mentions(match.group(2))
        if origins and destinations:
            return (
                resolve_location_to_iata(origins[0]),
                resolve_location_to_iata(destinations[0]),
            )

    locations = find_location_mentions(query)
    if len(locations) >= 2:
        return (
            resolve_location_to_iata(locations[0]),
            resolve_location_to_iata(locations[1]),
        )
    if len(locations) == 1:
        return DEFAULT_ORIGIN, resolve_location_to_iata(locations[0])
    return None, None


def format_flight(flight):
    airline = flight.get("airline") or {}
    departure = flight.get("departure") or {}
    arrival = flight.get("arrival") or {}
    flight_info = flight.get("flight") or {}
    aircraft = flight.get("aircraft") or {}

    return f"""
Airline: {airline.get('name') or 'Unknown airline'}
Flight Number: {(flight_info.get('iataNumber') or 'Unknown')}

Departure:
Airport: {departure.get('iataCode') or 'Unknown'}
Time: {departure.get('scheduledTime') or 'Not available'}
Terminal: {departure.get('terminal') or 'Not available'}

Arrival:
Airport: {arrival.get('iataCode') or 'Unknown'}
Time: {arrival.get('scheduledTime') or 'Not available'}
Terminal: {arrival.get('terminal') or 'Not available'}

Aircraft: {aircraft.get('modelText') or 'Not available'}
""".strip()


def search_flights(query="", travel_date="", limit=10, origin=None, destination=None):
    """
    Search future flight schedule information.

    origin and destination can be supplied directly as city/country names
    or IATA codes. If omitted, route parsing uses query and defaults to KTM
    only when one destination is detected.
    """
    if not API_KEY:
        print("AVIATIONSTACK_API_KEY is missing from .env")
        return []

    if not origin or not destination:
        parsed_origin, parsed_destination = parse_route_from_query(query)
        origin = origin or parsed_origin
        destination = destination or parsed_destination

    origin = str(origin or "").strip().upper()
    destination = str(destination or "").strip().upper()

    if len(origin) != 3 or len(destination) != 3:
        print("Could not identify valid origin and destination airport codes.")
        return []
    if origin == destination:
        print("Origin and destination cannot be the same.")
        return []

    travel_date = str(travel_date or "").strip().strip("'\"")
    try:
        selected_date = date.fromisoformat(travel_date)
    except ValueError:
        print("Please provide a valid future date in YYYY-MM-DD format.")
        return []

    if selected_date <= date.today():
        print("Please enter a future departure date.")
        return []

    params = {
        "access_key": API_KEY,
        "iataCode": destination,
        "type": "arrival",
        "date": travel_date,
    }

    try:
        response = requests.get(
            BASE_URL,
            params=params,
            timeout=30,
            verify=certifi.where(),
        )
        response.raise_for_status()
        result = response.json()

        if not isinstance(result, dict) or result.get("error"):
            print("AviationStack returned an invalid response:", result)
            return []

        flights = result.get("data") or []
        matches = []
        seen = set()

        for flight in flights:
            departure = flight.get("departure") or {}
            arrival = flight.get("arrival") or {}
            info = flight.get("flight") or {}

            dep_code = (departure.get("iataCode") or "").upper()
            arr_code = (arrival.get("iataCode") or "").upper()

            if dep_code != origin or arr_code != destination:
                continue

            key = (
                dep_code,
                arr_code,
                departure.get("scheduledTime"),
                arrival.get("scheduledTime"),
                info.get("iataNumber"),
            )
            if key not in seen:
                seen.add(key)
                matches.append(flight)

        return matches[:max(1, int(limit))]

    except requests.exceptions.Timeout:
        print("Flight API request timed out.")
    except requests.exceptions.HTTPError as error:
        print("Flight API HTTP error:", error)
        print("API response:", response.text[:1000])
    except requests.exceptions.RequestException as error:
        print("Flight API request error:", error)
    except (ValueError, TypeError) as error:
        print("Invalid flight API response:", error)
    except Exception as error:
        print("Unexpected flight search error:", repr(error))

    return []


if __name__ == "__main__":
    query = input("Enter travel request (e.g. from Kathmandu to Dhaka): ")
    travel_date = input("Enter departure date (YYYY-MM-DD): ")
    origin, destination = parse_route_from_query(query)
    print("Parsed route:", origin, "->", destination)
    flights = search_flights(query, travel_date, origin=origin, destination=destination)
    for item in flights:
        print(format_flight(item))
    if not flights:
        print("No flight schedule information available.")
