
import os

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

API_KEY = os.getenv("TAVILY_API_KEY")

client = TavilyClient(api_key=API_KEY) if API_KEY else None


def tavily_search(query: str, topic: str = "general"):
    """
    Search the web for travel information.

    topic="general": destinations, attractions, activities and transport.
    topic="hotels": budget hotels, prices and booking links.
    """

    if not client:
        return "Web research is unavailable. Please check TAVILY_API_KEY in your .env file."

    query = str(query or "").strip()

    if not query:
        return "No search query was provided."

    # Improve the search query for hotels
    if topic == "hotels":
        search_query = (
            f"{query}. Find real budget hotels and affordable accommodation. "
            "Prioritize hotels with official websites or genuine booking pages. "
            "Include hotel name, city, approximate nightly price, location, "
            "amenities and the original source URL. "
            "Do not invent prices, ratings or booking links. "
            "If prices are unavailable, clearly say so. "
            "Do not include YouTube videos or unrelated websites."
        )

    else:
        search_query = query

    try:
        response = client.search(
            query=search_query,
            max_results=5,
            search_depth="basic",
            topic="general"
        )

        results = response.get("results", [])

        if not results:
            return "No useful web search results were found."

        contents = []

        for result in results:

            title = result.get("title", "Untitled")
            url = result.get("url", "URL unavailable")
            content = result.get("content", "No description available.")

            # Keep each result short to avoid large LLM requests
            content = str(content)[:700]

            contents.append(
                f"Title: {title}\n"
                f"URL: {url}\n"
                f"Information: {content}"
            )

        # Combine search results
        final_results = "\n\n".join(contents)

        return final_results[:4000]

    except Exception as error:
        print("Tavily search error:", repr(error))
        return "Web search is currently unavailable."
