import os
import uuid
import json
import re
import operator
from typing import Annotated, TypedDict, Any
from datetime import date

import certifi
from dotenv import load_dotenv

load_dotenv()
load_dotenv()

os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGSMITH_PROJECT"] = "TripMateAI"


os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

print("Tracing:", os.getenv("LANGSMITH_TRACING"))
print("Project:", os.getenv("LANGSMITH_PROJECT"))
print("API Key:", bool(os.getenv("LANGSMITH_API_KEY")))


import psycopg
from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

from langchain_groq import ChatGroq

from tools.tavily_tool import tavily_search

from tools.flight_tool import (
    search_flights,
    format_flight,
    resolve_location_to_iata,
)


# ==================================================
# 1. CONFIGURATION
# ==================================================

def get_database_url():

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL is missing from .env")

    if "sslmode=" not in database_url.lower():

        separator = "&" if "?" in database_url else "?"
        database_url += f"{separator}sslmode=require"

    return database_url


GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing from .env")


llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="openai/gpt-oss-120b",
    temperature=0.4,
    max_tokens=6000,   # CHANGED (was 1600)
)

# NEW: approximate rate for estimates only. Set it to the current rate.
USD_TO_NPR = 140


# ==================================================
# 2. TRAVEL STATE
# ==================================================

class TravelState(TypedDict, total=False):

    messages: Annotated[list[AnyMessage], operator.add]

    user_query: str

    travel_date: str

    trip_context: dict

    flight_results: str

    hotel_results: str

    research_results: str

    final_response: str

    llm_calls: int


# ==================================================
# 3. HELPER FUNCTIONS
# ==================================================

def format_results(data: Any, max_chars=4000):

    if data is None or data == [] or data == {} or data == "":
        return "No results were returned."

    if isinstance(data, (dict, list)):

        result = json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
            default=str
        )

    else:
        result = str(data)

    if len(result) > max_chars:
        result = result[:max_chars] + "\n...[results truncated]"

    return result


def message_history(messages, limit=8, max_chars=2500):

    """
    Keep recent conversation history for context extraction.

    More assistant response text is retained so TripMate can
    understand selections such as 'I like option 2'.
    """

    lines = []

    for message in (messages or [])[-limit:]:

        if isinstance(message, HumanMessage):
            role = "User"

        elif isinstance(message, AIMessage):
            role = "TripMate"

        else:
            continue

        content = message.content

        if not isinstance(content, str):
            continue

        content = content[:max_chars]

        lines.append(f"{role}: {content}")

    return "\n".join(lines)


def extract_json(text):

    text = text.strip()

    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        return {}

    try:
        return json.loads(text[start:end + 1])

    except json.JSONDecodeError:
        return {}


# ==================================================
# 4. TRAVEL CONTEXT EXTRACTION
# ==================================================

def get_trip_context(state):

    old_context = state.get("trip_context") or {}

    history = message_history(
        state.get("messages", []),
        limit=8,
        max_chars=2500
    )

    prompt = f"""
Extract travel information from this conversation.

RECENT CONVERSATION:
{history}

PREVIOUSLY SAVED DETAILS:
{json.dumps(old_context, ensure_ascii=False)}

Return ONLY valid JSON with these keys:

{{
    "origin": null,
    "destination": null,
    "hotel_location": null,
    "travel_date": null,
    "return_date": null,
    "duration_days": null,
    "budget": null,
    "currency": null,
    "travellers": null
}}

IMPORTANT RULES:

GENERAL CONTEXT:

1. Extract only information provided or clearly implied.

2. Keep previous values if the user has not changed them.

3. The latest explicit USER instruction wins.

4. Do not treat TripMate suggestions as user decisions.

5. Do not invent missing information.

6. Do not confuse origin with destination.

7. Do not assume a specific city when the user only provides
   a country. For example, Bangladesh does not automatically
   mean Dhaka.

DESTINATION SELECTION:

8. If the user says "option 1", "option 2", "option 3",
   "I like option 2", or similar, look at the immediately
   preceding TripMate response in the conversation.

9. Identify the destination belonging to that numbered option.

10. Save the selected destination in the destination field.

11. If the option cannot be identified from the conversation,
    leave destination unchanged. Do not guess.

DESTINATION CHANGES:

12. If the user explicitly changes the trip destination,
    update destination only.

13. Preserve origin, duration, budget, currency and travellers.

14. If the destination changes, clear an old hotel_location
    unless the user also specifies a new hotel location.

HOTEL LOCATION:

15. hotel_location is the specific city, area or location
    where the user wants to search for hotels.

16. If the user says "find hotels in Kuala Lumpur",
    set hotel_location to "Kuala Lumpur".

17. Do NOT change destination to Kuala Lumpur just because
    the user wants hotels there. The trip destination may
    still be Malaysia.

18. If the user says "find hotels" without naming a city,
    keep the previously saved hotel_location or use destination
    as the hotel search location.

19. If the user changes the hotel search city, update only
    hotel_location. Do not change destination.

BUDGET:

20. If the user changes the budget, update budget.

21. Update currency only when the currency is stated or
    clearly established by the conversation.

22. Do not invent exchange rates or convert currencies.

Return JSON only.
"""

    try:

        response = llm.invoke([
            SystemMessage(
                content=(
                    "You extract travel information accurately. "
                    "Return valid JSON only."
                )
            ),
            HumanMessage(content=prompt),
        ])

        extracted = extract_json(str(response.content))

    except Exception as error:

        print("Context extraction error:", error)
        extracted = {}

    # Start with previously saved details
    merged = dict(old_context)

    # Update extracted values
    for key, value in extracted.items():

        # Empty hotel_location means clear the previous
        # hotel search location after a destination change.
        if key == "hotel_location" and value == "":
            merged[key] = ""

        elif value not in (None, "", "null"):
            merged[key] = value

    # Explicit departure date takes priority
    if state.get("travel_date"):
        merged["travel_date"] = state["travel_date"]

    return merged


# ==================================================
# 5. REQUEST DETECTION
# ==================================================

def wants_live_flights(query):

    q = query.lower()

    terms = (
        "find flights",
        "search flights",
        "search for flights",
        "show flights",
        "available flights",
        "flight options",
        "book flight",
        "book a flight",
        "air ticket options",
        "flight schedule",
        "flight timings",
    )

    return any(term in q for term in terms)


def wants_live_hotels(query):

    q = query.lower()

    terms = (
        "find hotels",
        "find a hotel",
        "find cheaper hotels",
        "search hotels",
        "search for hotels",
        "show hotels",
        "hotel options",
        "available hotels",
        "book hotel",
        "book a hotel",
        "hotel booking",
        "accommodation options",
        "places to stay",
        "cheaper hotels",
        "cheap hotels",
        "budget hotels",
        "affordable hotels",
        "find cheaper accommodation",
        "cheap accommodation",
    )

    return any(term in q for term in terms)


def wants_research(query):

    q = query.lower()

    terms = (
        "research",
        "look up",
        "search for",
        "what can i do",
        "activities",
        "attractions",
        "things to do",
        "compare destinations",
        "compare",
        "explore",
    )

    return any(term in q for term in terms)


def is_trip_planning_request(query):

    q = re.sub(r"\s+", " ", (query or "").lower()).strip()

    explicit_phrases = (
        "plan a trip",
        "plan my trip",
        "plan trip",
        "trip to",
        "travel to",
        "vacation",
        "holiday",
        "itinerary",
        "travel plan",
        "trip plan",
        "tour plan",
        "travel package",
    )

    if any(term in q for term in explicit_phrases):
        return True

    mentions_trip = bool(
        re.search(r"\b(trip|holiday|vacation|tour)\b", q)
    )

    mentions_duration = bool(
        re.search(r"\b\d+\s*[- ]?\s*days?\b", q)
    )

    planning_verb = bool(
        re.search(r"\b(plan|arrange|organize|suggest|make)\b", q)
    )

    return mentions_trip and (mentions_duration or planning_verb)


# ==================================================
# 6. ROUTE AND HOTEL QUERY BUILDERS
# ==================================================

def build_route_query(context):

    origin = context.get("origin") or ""
    destination = context.get("destination") or ""

    if not origin or not destination:
        return ""

    return f"from {origin} to {destination}"


def build_hotel_query(context):

    # Prefer the specific hotel city/area.
    # If none is provided, use the main destination.
    hotel_location = (
        context.get("hotel_location")
        or context.get("destination")
        or ""
    )

    budget = context.get("budget", "")
    currency = context.get("currency", "")
    travel_date = context.get("travel_date", "")
    duration = context.get("duration_days", "")

    if not hotel_location:
        return ""

    query = (
        f"Find affordable budget hotels and cheap accommodation "
        f"in {hotel_location}."
    )

    if budget:

        query += (
            f" The user's total trip budget is "
            f"{budget} {currency or ''}."
            " Prioritize affordable accommodation."
            " Do not assume the entire budget is available for hotels."
        )

    if duration:
        query += f" Trip duration: {duration} days."

    if travel_date:
        query += f" Departure date: {travel_date}."

    query += (
        " Prioritize actual hotel websites and established "
        "hotel booking platforms. Find real hotel names, "
        "locations, nightly prices when published, and original "
        "booking URLs. Do not invent prices, ratings, availability "
        "or booking links. If price information is unavailable, "
        "say so. Keep prices in their original stated currency."
    )

    return query


# ==================================================
# 7. MAIN TRIPMATE AGENT
# ==================================================

def tripmate_agent(state: TravelState):

    query = state.get("user_query", "")

    # STEP 1: Extract travel details
    context = get_trip_context(state)

    flight_results = (
        "Not searched. The user has not requested live flights."
    )

    hotel_results = (
        "Not searched. The user has not requested live hotels."
    )

    research_results = "No additional research requested."

    # ==================================================
    # STEP 2: FLIGHT SEARCH
    # ==================================================

    if wants_live_flights(query):

        origin = context.get("origin")
        destination = context.get("destination")
        travel_date = str(context.get("travel_date") or "").strip()

        if not destination:

            flight_results = (
                "Please provide your destination before searching flights."
            )

        elif not origin:

            flight_results = (
                "Please provide your departure city or airport "
                "before searching flights."
            )

        elif not travel_date:

            flight_results = (
                "Please provide your departure date to search flights."
            )

        else:

            route_query = build_route_query(context)

            origin_iata = resolve_location_to_iata(origin)
            destination_iata = resolve_location_to_iata(destination)

            if not origin_iata or not destination_iata:

                flight_results = (
                    "I could not identify the departure or destination "
                    "airport. Please provide a city or airport name."
                )

            else:

                try:

                    flight_data = search_flights(
                        route_query,
                        travel_date,
                        origin=origin_iata,
                        destination=destination_iata,
                    )

                    if flight_data:

                        flight_results = "\n\n".join(
                            format_flight(item)
                            for item in flight_data
                        )

                        flight_results = flight_results[:4000]

                    else:

                        flight_results = (
                            "No matching flight schedule was returned. "
                            "This does not prove that no flights operate."
                        )

                except Exception as error:

                    print("Flight search error:", error)

                    flight_results = (
                        "Flight search is temporarily unavailable."
                    )

    # ==================================================
    # STEP 3: HOTEL SEARCH
    # ==================================================

    if wants_live_hotels(query):

        hotel_location = (
            context.get("hotel_location")
            or context.get("destination")
        )

        if not hotel_location:

            hotel_results = (
                "Please tell me the city or destination where "
                "you want to search for hotels."
            )

        else:

            try:

                hotel_query = build_hotel_query(context)

                hotel_data = tavily_search(
                    hotel_query,
                    topic="hotels"
                )

                hotel_results = format_results(
                    hotel_data,
                    max_chars=4000
                )

            except Exception as error:

                print("Hotel search error:", error)

                hotel_results = (
                    "Hotel search is temporarily unavailable."
                )

    # ==================================================
    # STEP 4: GENERAL TRAVEL RESEARCH
    # ==================================================

    needs_destination_choice = (
        not context.get("destination")
        and is_trip_planning_request(query)
        and not wants_live_flights(query)
        and not wants_live_hotels(query)
    )

    if needs_destination_choice:

        origin = context.get("origin") or "not specified"

        budget = context.get("budget")
        currency = context.get("currency")

        duration = (
            context.get("duration_days")
            or "not specified"
        )

        travellers = (
            context.get("travellers")
            or "not specified"
        )

        budget_text = (
            f"{budget} {currency or ''}".strip()
            if budget
            else "not specified"
        )

        research_query = (
            f"Suggest three realistic travel destinations for a "
            f"{duration} trip starting from {origin}, for "
            f"{travellers}, with a total budget of {budget_text}. "
            "Consider transport, accommodation, food, local transport "
            "and activities. Include practical travel considerations. "
            "Use verifiable information where possible. "
            "Do not claim live prices or invent exchange rates."
        )

        try:

            research_data = tavily_search(research_query)

            research_results = format_results(
                research_data,
                max_chars=4000
            )

        except Exception as error:

            print("Destination research error:", error)

            research_results = (
                "Destination research is temporarily unavailable."
            )

    elif wants_research(query) and not wants_live_hotels(query):

        destination = context.get("destination")

        if "compare" in query.lower():

            research_query = (
                f"Compare these travel destinations: {query}. "
                "Cover costs, attractions, transport, safety "
                "and accommodation areas."
            )

        elif destination:

            research_query = (
                f"Travel guide for {destination}: attractions, "
                "activities, transport, food and practical advice."
            )

        else:

            research_query = query

        try:

            research_data = tavily_search(research_query)

            research_results = format_results(
                research_data,
                max_chars=4000
            )

        except Exception as error:

            print("Research error:", error)

            research_results = (
                "Travel research is temporarily unavailable."
            )

    # ==================================================
    # STEP 5: FINAL LLM PROMPT
    # ==================================================

    prompt = f"""
You are TripMate, a helpful travel-planning assistant.

CURRENT USER REQUEST:
{query}

SAVED TRAVEL DETAILS:
{json.dumps(context, ensure_ascii=False)}

FLIGHT SEARCH RESULTS:
{flight_results}

HOTEL SEARCH RESULTS:
{hotel_results}

TRAVEL RESEARCH RESULTS:
{research_results}


YOUR RESPONSIBILITIES:

1. Understand simple, incomplete and informal user messages.

2. Never ask users to repeat information already saved.

3. If the destination is missing, suggest exactly three suitable
   destinations when the user requests a new trip.

4. When the user selects an option, use the selected destination
   from SAVED TRAVEL DETAILS.

5. If the user changes only the destination, preserve budget,
   duration, origin and traveller count.

6. If the user changes only the budget, preserve destination
   and duration.

7. If the user changes only the duration, preserve destination
   and budget.

8. Use hotel_location for hotel searches. Do not replace the
   main trip destination with the hotel search city.

9. Provide realistic budget categories:
   flights, accommodation, food, local transport, activities
   and miscellaneous expenses.

10. Clearly label estimated prices as estimates.
    Never present estimates as live prices.

11. Use flight results only when supplied above.
    Flight schedules are not ticket prices.

12. Use hotel results only when supplied above.

13. For hotel recommendations:
    - Show actual hotel names.
    - Include city or location.
    - Show prices only when search results provide them.
    - Include original booking URLs when available.
    - Never invent ratings, prices or booking links.
    - Explain when information is missing.

14. Search results do not confirm room availability.

15. Suggest activities as ideas, not confirmed reservations.

16. Never book or pay without explicit confirmation.

17. Separate live search findings from estimates.

18. If information is missing, ask only the most important question.

19. EXCHANGE RATE: For your own ESTIMATES, use this approximate rate:
    1 USD = {USD_TO_NPR} NPR. Say once that it is approximate.

20. For estimates, show NPR first with USD in brackets,
    like NPR 70,000 ($500). Round to the nearest NPR 1,000.

21. For prices found in HOTEL or FLIGHT search results, show the
    original currency exactly as the source gives it. Never convert
    those, and never claim a hotel is cheaper based on a conversion.

22. BUDGET AND STYLE: The user's message may include a budget and a
    travel style (Budget, Comfort or Luxury). Respect both.
    If the budget is too low for the style or destination, say so
    first, then give the best plan that fits the budget.
    ALWAYS include international flights in the total.
    Add the totals carefully and check the math before answering.

23. Do not invent a departure city from a country name.

24. FLIGHTS FROM NEPAL: Flights from Kathmandu are rarely direct.
    Plan the first and last day around a connection, and do not
    assume arrival on the morning of Day 1.

25. VISA: Do not state exact visa fees or rules. Say which kind of
    visa Nepali passport holders usually need and tell them to check
    the official embassy or e-visa website.

26. LENGTH: Keep the answer under 900 words. Use one itinerary table
    and one budget table, then 3 to 5 short tips.


27. OTHER CURRENCIES: Never multiply a local-currency price by
    {USD_TO_NPR}, because that is the USD rate. Convert to USD first,
    then to NPR. The UAE dirham is fixed at about 3.67 per USD, so
    1 AED is about {USD_TO_NPR / 3.67:.0f} NPR. For other currencies,
    quote the price in USD instead of guessing a local rate.

28. DATES: Always write dates with the exact year from the travel
    date in SAVED TRAVEL DETAILS, for example 12 Nov 2026.
    Never change the year.

29. MISSING DETAILS: If travellers or trip length are missing, assume
    1 traveller and 5 days, say the assumption in one line, and give
    the plan. Ask at most ONE question, after the plan.

30. DATES: Never write days of the week (Mon, Tue, Sat and so on).
    Write only the date, for example "Day 1 – 12 Nov 2026".

31. RAIL PASSES: Do not state a rail pass price or tell the user to
    buy one. Say that a pass may or may not save money, and that they
    should compare it with individual tickets on the official site
    before buying. In the budget, estimate local transport as a range.
    

IMPORTANT:

Use SAVED TRAVEL DETAILS as the source of previous trip preferences.

Do not change existing values without a new instruction from the user.

Use tables when they make the answer easier to understand.
"""

    # ==================================================
    # STEP 6: GENERATE FINAL RESPONSE
    # ==================================================

    try:

        response = llm.invoke([
            SystemMessage(
                content=(
                    "You are TripMate, an accurate travel assistant for "
                    "travelers from Nepal. Always finish your answer. "
                    "Check all arithmetic."
                )   # CHANGED
            ),
            HumanMessage(content=prompt),
        ])

        final_response = str(response.content)

    except Exception as error:

        print("Final LLM error:", error)

        final_response = (
            "Sorry! TripMate could not generate your response "
            "right now. This may be due to a temporary API "
            "limit or connection problem. Please try again."
        )

    # ==================================================
    # STEP 7: RETURN UPDATED STATE
    # ==================================================

    return {

        "trip_context": context,

        "flight_results": flight_results,

        "hotel_results": hotel_results,

        "research_results": research_results,

        "final_response": final_response,

        "messages": [
            AIMessage(content=final_response)
        ],

        "llm_calls": state.get("llm_calls", 0) + 2,
    }


# ==================================================
# 8. LANGGRAPH
# ==================================================

graph = StateGraph(TravelState)

graph.add_node(
    "tripmate_agent",
    tripmate_agent
)

graph.add_edge(START, "tripmate_agent")

graph.add_edge("tripmate_agent", END)


# ==================================================
# 9. POSTGRESQL CHECKPOINTER
# ==================================================

DATABASE_URL = get_database_url()

_conn = psycopg.connect(
    DATABASE_URL,
    autocommit=True,
    row_factory=dict_row,
)

checkpointer = PostgresSaver(_conn)

checkpointer.setup()

travel_graph = graph.compile(
    checkpointer=checkpointer
)


# ==================================================
# 10. PUBLIC FUNCTION
# ==================================================

def run_travel_agent(
    user_input: str,
    travel_date: str = "",
    thread_id: str | None = None
):

    if not user_input or not user_input.strip():
        raise ValueError("Please enter a travel request.")

    travel_date = str(travel_date or "").strip()

    # Validate departure date
    if travel_date:

        try:

            parsed_date = date.fromisoformat(travel_date)

            if parsed_date.isoformat() != travel_date:
                raise ValueError("Use YYYY-MM-DD format.")

            if parsed_date <= date.today():
                raise ValueError("Departure date must be in the future.")

        except ValueError as error:

            raise ValueError(
                f"Invalid departure date: {error}"
            )

    # Create a new conversation ID if necessary
    if not thread_id:
        thread_id = f"trip_{uuid.uuid4().hex}"

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    # Check whether this conversation already exists
    saved_state = travel_graph.get_state(config)

    if saved_state and saved_state.values:

        input_state = {

            "user_query": user_input,

            "travel_date": travel_date,

            "messages": [
                HumanMessage(content=user_input)
            ],
        }

    else:

        input_state = {

            "user_query": user_input,

            "travel_date": travel_date,

            "trip_context": {},

            "flight_results": "",

            "hotel_results": "",

            "research_results": "",

            "final_response": "",

            "llm_calls": 0,

            "messages": [
                HumanMessage(content=user_input)
            ],
        }

    # Run LangGraph
    result = travel_graph.invoke(
        input_state,
        config=config
    )

    return {

        "thread_id": thread_id,

        "answer": result.get("final_response", ""),

        "trip_context": result.get("trip_context", {}),

        "flight_results": result.get("flight_results", ""),

        "hotel_results": result.get("hotel_results", ""),

        "research_results": result.get("research_results", ""),

        "llm_calls": result.get("llm_calls", 0),
    }