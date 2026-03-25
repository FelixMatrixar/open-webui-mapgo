from app.config import BACKEND_MAPS_KEY
from googlemaps.exceptions import ApiError, Timeout, TransportError, HTTPError
import googlemaps
import logging

logger = logging.getLogger(__name__)
client = googlemaps.Client(key=BACKEND_MAPS_KEY)

def search_places(query: str) -> dict:
    try:
        return client.places(query=query)
        
    except ApiError as e:
        # Catches Google-specific rejections: REQUEST_DENIED, OVER_QUERY_LIMIT, INVALID_REQUEST
        logger.error(f"Google Maps API Error (Status/Quota/Key): {e.status} - {e.message}")
        return {"status": "ERROR", "results": []}
        
    except Timeout as e:
        # Catches when Google's servers take too long to respond
        logger.error(f"Google Maps Request Timed Out: {e}")
        return {"status": "ERROR", "results": []}
        
    except TransportError as e:
        # Catches underlying network failures (e.g., your server lost internet connection)
        logger.error(f"Network Transport Error connecting to Google: {e}")
        return {"status": "ERROR", "results": []}
        
    except HTTPError as e:
        # Catches standard HTTP failures (e.g., 500 Internal Server Error, 404 Not Found)
        logger.error(f"HTTP Error {e.status_code} from Google Maps: {e}")
        return {"status": "ERROR", "results": []}
        
    except Exception as e:
        # The ultimate fallback for weird Python bugs (like memory errors or bad variable types)
        logger.critical(f"Critical Unexpected Error in search_places: {e}", exc_info=True)
        return {"status": "ERROR", "results": []}

def get_batch_etas(user_location: str, top_places: list) -> tuple[list, list]:
    destinations = [f"place_id:{p.get('place_id')}" for p in top_places]
    driving_times = [""] * len(top_places)
    walking_times = [""] * len(top_places)
    
    if not user_location or not destinations:
        return driving_times, walking_times

    try:
        d_matrix = client.distance_matrix(origins=[user_location], destinations=destinations, mode="driving")
        w_matrix = client.distance_matrix(origins=[user_location], destinations=destinations, mode="walking")
        
        for i in range(len(top_places)):
            if d_matrix.get('status') == 'OK' and d_matrix['rows'][0]['elements'][i].get('status') == 'OK':
                driving_times[i] = d_matrix['rows'][0]['elements'][i].get('duration', {}).get('text', '')
            if w_matrix.get('status') == 'OK' and w_matrix['rows'][0]['elements'][i].get('status') == 'OK':
                walking_times[i] = w_matrix['rows'][0]['elements'][i].get('duration', {}).get('text', '')
                
    except ApiError as e:
        logger.error(f"Distance Matrix API Error (Status/Quota/Key): {e.status} - {e.message}")
    except Timeout as e:
        logger.error(f"Distance Matrix Request Timed Out: {e}")
    except TransportError as e:
        logger.error(f"Distance Matrix Network Transport Error: {e}")
    except HTTPError as e:
        logger.error(f"Distance Matrix HTTP Error {e.status_code}: {e}")
    except Exception as e:
        logger.critical(f"Critical Unexpected Error in get_batch_etas: {e}", exc_info=True)
        
    return driving_times, walking_times