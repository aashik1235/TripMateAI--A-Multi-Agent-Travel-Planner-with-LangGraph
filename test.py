from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights
from backend import run_travel_agent
import uuid
# results = tavily_search("Best travel destinations in Europe")
# print(results)

#search_results = search_flights("plan a 7 days nepal trip from india")
#print(search_results)

if __name__ == "__main__":

    # One thread ID for the entire conversation.
    thread_id = f"tripmate_{uuid.uuid4().hex}"

    print("\nWelcome to TripMate AI!")
    print("Type 'exit' to quit.\n")

    first_request = True

    while True:

        query = input("\nEnter travel request: ").strip()

        if query.lower() in ["exit", "quit"]:
            print("Thank you for using TripMate!")
            break

        if not query:
            print("Please enter a travel request.")
            continue

        # Ask for the departure date only on the first request.
        travel_date = ""

        if first_request:
            travel_date = input(
                "Enter departure date (YYYY-MM-DD) or press Enter to skip: "
            ).strip()
            first_request = False

        try:
            result = run_travel_agent(
                user_input=query,
                travel_date=travel_date,
                thread_id=thread_id
            )

            print("\n" + "=" * 60)
            print("TRIPMATE FINAL RESPONSE")
            print("=" * 60)

            print(result["answer"])

            print("\n" + "=" * 60)

        except Exception as e:
            print(f"\nError: {e}")
