from src.utils.web_search import search_web
def flight_search(params):
    if not params:
        return "No parameters provided for flight search."
    origin = params.get('origin')
    destination = params.get('destination')
    date = params.get('date')
    if not origin or not destination or not date:
        return "Missing required parameters: 'origin', 'destination', or 'date'."
    # Aquí se realizaría la búsqueda de vuelos (simulada)
    flights = [
        {"flight_number": "AA123", "origin": origin, "destination": destination, "date": date},
        {"flight_number": "BA456", "origin": origin, "destination": destination, "date": date}
    ]
    return flights
def run(params):
    return flight_search(params)