from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights

# results = tavily_search("Best travel destinations in Europe")
# print(results)

search_results = search_flights("plan a 7 days nepal trip from india")
print(search_results)