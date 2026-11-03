import os
import requests
import certifi
import re
import airportsdata
import pycountry
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

API_KEY = os.getenv("AVIATIONSTACK_API_KEY")

# Default origin: Kathmandu, Nepal
DEFAULT_ORIGIN_IATA = os.getenv("DEFAULT_ORIGIN_IATA", "KTM")

BASE_URL = "https://api.aviationstack.com/v1/flights"

AIRPORTS_DATA = airportsdata.load("IATA")


# --------------------------------------------------
# COUNTRY ALIASES
# --------------------------------------------------

COUNTRY_ALIAS = {
    "USA": "US",
    "UNITED STATES": "US",
    "UK": "GB",
    "UNITED KINGDOM": "GB",
    "UAE": "AE",
    "UNITED ARAB EMIRATES": "AE",
    "NEPAL": "NP",
    "INDIA": "IN",
    "CANADA": "CA",
    "AUSTRALIA": "AU",
    "NEW ZEALAND": "NZ",
    "GERMANY": "DE",
    "FRANCE": "FR",
    "ITALY": "IT",
    "SPAIN": "ES",
    "PORTUGAL": "PT",
    "JAPAN": "JP",
    "CHINA": "CN",
    "SOUTH KOREA": "KR",
    "NORTH KOREA": "KP",
    "SINGAPORE": "SG",
    "MALAYSIA": "MY",
    "THAILAND": "TH",
    "INDONESIA": "ID",
    "PHILIPPINES": "PH",
    "VIETNAM": "VN",
    "BANGLADESH": "BD",
    "PAKISTAN": "PK",
    "SRI LANKA": "LK",
    "BHUTAN": "BT",
    "MALDIVES": "MV",
    "SAUDI ARABIA": "SA",
    "QATAR": "QA",
    "KUWAIT": "KW",
    "OMAN": "OM",
    "BAHRAIN": "BH",
    "TURKEY": "TR",
    "RUSSIA": "RU",
    "UKRAINE": "UA",
    "BRAZIL": "BR",
    "ARGENTINA": "AR",
    "MEXICO": "MX",
    "SOUTH AFRICA": "ZA",
    "EGYPT": "EG",
    "NIGERIA": "NG",
    "KENYA": "KE",
    "SWITZERLAND": "CH",
    "NETHERLANDS": "NL",
    "BELGIUM": "BE",
    "SWEDEN": "SE",
    "NORWAY": "NO",
    "DENMARK": "DK",
    "FINLAND": "FI",
    "IRELAND": "IE",
    "POLAND": "PL",
    "GREECE": "GR",
    "ISRAEL": "IL",
    "IRAN": "IR",
    "IRAQ": "IQ"
}


# --------------------------------------------------
# CITY TO AIRPORT MAPPING
# --------------------------------------------------

CITY_MAIN_AIRPORTS = {

    # Nepal
    "KATHMANDU": "KTM",
    "POKHARA": "PKR",
    "BHAIRAHAWA": "BWA",
    "BIRATNAGAR": "BIR",
    "NEPALGUNJ": "KEP",
    "BHARATPUR": "BHR",
    "JANAKPUR": "JKR",

    # India
    "DELHI": "DEL",
    "MUMBAI": "BOM",
    "BANGALORE": "BLR",
    "BENGALURU": "BLR",
    "CHENNAI": "MAA",
    "KOLKATA": "CCU",
    "HYDERABAD": "HYD",
    "PUNE": "PNQ",
    "JAIPUR": "JAI",
    "AHMEDABAD": "AMD",
    "GOA": "GOI",

    # USA
    "NEW YORK": "JFK",
    "LOS ANGELES": "LAX",
    "CHICAGO": "ORD",
    "SAN FRANCISCO": "SFO",
    "MIAMI": "MIA",
    "BOSTON": "BOS",
    "WASHINGTON DC": "IAD",
    "LAS VEGAS": "LAS",
    "SEATTLE": "SEA",
    "DALLAS": "DFW",
    "HOUSTON": "IAH",
    "ORLANDO": "MCO",

    # UK
    "LONDON": "LHR",
    "MANCHESTER": "MAN",
    "BIRMINGHAM": "BHX",
    "EDINBURGH": "EDI",
    "GLASGOW": "GLA",

    # UAE
    "DUBAI": "DXB",
    "ABU DHABI": "AUH",
    "SHARJAH": "SHJ",

    # Europe
    "PARIS": "CDG",
    "FRANKFURT": "FRA",
    "BERLIN": "BER",
    "MUNICH": "MUC",
    "ROME": "FCO",
    "MILAN": "MXP",
    "MADRID": "MAD",
    "BARCELONA": "BCN",
    "AMSTERDAM": "AMS",
    "ZURICH": "ZRH",
    "GENEVA": "GVA",
    "VIENNA": "VIE",
    "ATHENS": "ATH",
    "ISTANBUL": "IST",
    "LISBON": "LIS",

    # Asia
    "TOKYO": "HND",
    "OSAKA": "KIX",
    "BEIJING": "PEK",
    "SHANGHAI": "PVG",
    "HONG KONG": "HKG",
    "SINGAPORE": "SIN",
    "KUALA LUMPUR": "KUL",
    "BANGKOK": "BKK",
    "PHUKET": "HKT",
    "JAKARTA": "CGK",
    "BALI": "DPS",
    "SEOUL": "ICN",
    "MANILA": "MNL",
    "HO CHI MINH CITY": "SGN",
    "HANOI": "HAN",

    # Australia
    "SYDNEY": "SYD",
    "MELBOURNE": "MEL",
    "BRISBANE": "BNE",
    "PERTH": "PER",
    "AUCKLAND": "AKL",

    # Middle East
    "DOHA": "DOH",
    "RIYADH": "RUH",
    "JEDDAH": "JED",
    "MUSCAT": "MCT",
    "KUWAIT CITY": "KWI",

    # Africa
    "CAIRO": "CAI",
    "CAPE TOWN": "CPT",
    "JOHANNESBURG": "JNB",
    "NAIROBI": "NBO",
    "LAGOS": "LOS",

    # South America
    "SAO PAULO": "GRU",
    "RIO DE JANEIRO": "GIG",
    "BUENOS AIRES": "EZE",
    "LIMA": "LIM",
    "SANTIAGO": "SCL",
}


# --------------------------------------------------
# 1. CLEAN TEXT
# --------------------------------------------------

def clean_text(text: str) -> str:

    text = text.upper().strip()

    text = re.sub(r"[^A-Z0-9\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    stop_words = {
        "FLIGHT", "FLIGHTS", "TRIP", "TRIPS",
        "TRAVEL", "PLAN", "COMPLETE", "DAYS",
        "DAY", "HOTEL", "HOTELS", "INFO",
        "BUDGET", "INFORMATION", "UNDER"
    }

    words = [
        word for word in text.split()
        if word not in stop_words
    ]

    return " ".join(words).strip()


# --------------------------------------------------
# 2. COUNTRY NAME TO COUNTRY CODE
# --------------------------------------------------

def country_name_to_code(country_name: str) -> str:

    country_name = country_name.upper().strip()

    if country_name in COUNTRY_ALIAS:
        return COUNTRY_ALIAS[country_name]

    try:
        country = pycountry.countries.lookup(country_name)
        return country.alpha_2

    except LookupError:
        return None


# --------------------------------------------------
# 3. CHECK AIRPORT COUNTRY
# --------------------------------------------------

def airport_country_matches(airport: str, country_code: str) -> bool:

    country_code = country_code.upper().strip()

    if not pycountry.countries.get(alpha_2=country_code):
        return False

    airport_info = AIRPORTS_DATA.get(airport.upper().strip())

    if not airport_info:
        return False

    return airport_info.get("country") == country_code


# --------------------------------------------------
# 4. GET AIRPORT FOR COUNTRY
# --------------------------------------------------

def get_best_airport_for_country(country_code: str) -> str:

    country_code = country_code.upper().strip()

    if not pycountry.countries.get(alpha_2=country_code):
        return None

    for city, iata in CITY_MAIN_AIRPORTS.items():

        airport_info = AIRPORTS_DATA.get(iata)

        if airport_info and airport_info["country"] == country_code:
            return iata

    return None


# --------------------------------------------------
# 5. RESOLVE LOCATION TO IATA
# --------------------------------------------------

def resolve_location_to_iata(location: str) -> str:

    location = clean_text(location).upper()

    # Check city
    if location in CITY_MAIN_AIRPORTS:
        return CITY_MAIN_AIRPORTS[location]

    # Check country
    country_code = country_name_to_code(location)

    if country_code:
        return get_best_airport_for_country(country_code)

    return None


# --------------------------------------------------
# 6. FIND CITY AND COUNTRY MENTIONS
# --------------------------------------------------

def find_location_mentions(query: str) -> list:

    query = clean_text(query)

    known_locations = set(CITY_MAIN_AIRPORTS) | set(COUNTRY_ALIAS)

    location_pattern = "|".join(
        re.escape(name)
        for name in sorted(known_locations, key=len, reverse=True)
    )

    matches = re.finditer(
        rf"(?<![A-Z])({location_pattern})(?![A-Z])",
        query
    )

    locations = []

    for match in matches:

        location = match.group(1)

        if location not in locations:
            locations.append(location)

    return locations


# --------------------------------------------------
# 7. PARSE ORIGIN AND DESTINATION
# --------------------------------------------------

def parse_route_from_query(query: str) -> tuple:

    locations = find_location_mentions(query)

    origin_iata = DEFAULT_ORIGIN_IATA
    destination_iata = None

    if len(locations) == 1:

        destination_iata = resolve_location_to_iata(locations[0])

    elif len(locations) >= 2:

        cleaned_query = clean_text(query)

        # Check whether the user specified "from"
        from_match = re.search(
            r"\bFROM\s+([A-Z ]+)",
            cleaned_query
        )

        if from_match:

            text_after_from = from_match.group(1).strip()

            possible_origins = [
                location for location in locations
                if re.search(
                    rf"\b{re.escape(location)}\b",
                    text_after_from
                )
            ]

            if possible_origins:

                origin_location = possible_origins[0]

                destination_location = next(
                    (loc for loc in locations if loc != origin_location),
                    None
                )

            else:

                origin_location = locations[0]
                destination_location = locations[1]

        else:

            origin_location = locations[0]
            destination_location = locations[1]

        origin_iata = (
            resolve_location_to_iata(origin_location)
            or DEFAULT_ORIGIN_IATA
        )

        destination_iata = (
            resolve_location_to_iata(destination_location)
            if destination_location else None
        )

    return origin_iata, destination_iata


# --------------------------------------------------
# 8. FORMAT FLIGHT INFORMATION
# --------------------------------------------------

def format_flight(flight: dict) -> str:

    airline = flight.get("airline", {}).get(
        "name", "Unknown Airline"
    )

    flight_number = flight.get("flight", {}).get(
        "number", "Unknown"
    )

    # Departure information
    departure = flight.get("departure", {})

    departure_airport = departure.get("airport", "Unknown")
    departure_terminal = departure.get("terminal", "Unknown")
    departure_gate = departure.get("gate", "Unknown")
    departure_time = departure.get("estimated", "Unknown")
    departure_delay = departure.get("delay", 0)

    # Arrival information
    arrival = flight.get("arrival", {})

    arrival_airport = arrival.get("airport", "Unknown")
    arrival_terminal = arrival.get("terminal", "Unknown")
    arrival_gate = arrival.get("gate", "Unknown")
    arrival_time = arrival.get("estimated", "Unknown")
    arrival_delay = arrival.get("delay", 0)

    # Flight status
    status = flight.get("flight_status", "Unknown")

    return (
        f"Airline: {airline}\n"
        f"Flight Number: {flight_number}\n"
        f"Flight Status: {status}\n\n"

        f"--- DEPARTURE ---\n"
        f"Airport: {departure_airport}\n"
        f"Terminal: {departure_terminal}\n"
        f"Gate: {departure_gate}\n"
        f"Departure Time: {departure_time}\n"
        f"Departure Delay: {departure_delay} minutes\n\n"

        f"--- ARRIVAL ---\n"
        f"Airport: {arrival_airport}\n"
        f"Terminal: {arrival_terminal}\n"
        f"Gate: {arrival_gate}\n"
        f"Arrival Time: {arrival_time}\n"
        f"Arrival Delay: {arrival_delay} minutes\n"
    )


# --------------------------------------------------
# 9. SEARCH FLIGHTS USING API
# --------------------------------------------------

def search_flights(query: str, limit: int = 10) -> list:

    origin_iata, destination_iata = parse_route_from_query(query)

    print(f"Detected route: {origin_iata} -> {destination_iata}")

    if not destination_iata:

        print("Could not identify a supported destination city or country.")

        return []

    if not API_KEY:

        print("AVIATIONSTACK_API_KEY is missing. Check your .env file.")

        return []

    params = {
        "access_key": API_KEY,
        "dep_iata": origin_iata,
        "arr_iata": destination_iata,
        "limit": limit
    }

    try:

        response = requests.get(
            BASE_URL,
            params=params,
            timeout=30,
            verify=certifi.where()
        )

        print("HTTP status:", response.status_code)

        data = response.json()

        if response.status_code != 200 or "error" in data:

            print(
                "Aviationstack API error:",
                data.get("error", response.text)
            )

            return []

        return data.get("data", [])

    except requests.RequestException as error:

        print("Network/request error:", error)

        return []

    except ValueError:

        print("The API response was not valid JSON.")

        return []


# --------------------------------------------------
# 10. TEST THE CODE
# --------------------------------------------------

if __name__ == "__main__":

    test_query = "plan a 7 days Japan trip from India"

    print("Locations found:", find_location_mentions(test_query))

    print("Parsed route:", parse_route_from_query(test_query))

    print("\nSearching flights...")

    flights = search_flights(test_query)

    if flights:

        for flight in flights:

            print(format_flight(flight))

            print("=" * 50)

    else:

        print("No flight records returned. Check the messages above.")