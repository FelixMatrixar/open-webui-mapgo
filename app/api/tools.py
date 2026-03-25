import urllib.parse
import logging
import re
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address

from jinja2.exceptions import TemplateNotFound, TemplateError 

from app.services.gmaps import search_places, get_batch_etas
from app.config import FRONTEND_MAPS_KEY

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory="app/templates")

@router.get("/locator", response_class=HTMLResponse)
@limiter.limit("5/minute")
async def find_location(request: Request, query: str, user_location: str = ""):
    # --- SANITIZATION LAYER ---
    try:
        coord_pattern = r'[-+]?\d{1,2}\.\d+,\s*[-+]?\d{1,3}\.\d+'
        match = re.search(coord_pattern, query)
        if match:
            extracted_coords = match.group(0)
            if not user_location:
                user_location = extracted_coords
            query = re.sub(coord_pattern, '', query)
            query = query.replace('(lat, long)', '').replace('(lat,', '').replace('long)', '')
            query = query.strip(" ,+") 
            if not query:
                query = "restaurants and places" 
    except Exception as e:
        logger.warning(f"Sanitization layer failed, proceeding with raw query: {e}")
    # --------------------------

    try:
        places_data = search_places(query)
        
        if places_data.get('status') != 'OK' or not places_data.get('results'):
            return HTMLResponse(content="<p>Location not found.</p>", headers={"Content-Disposition": "inline"})
            
        top_places = places_data['results'][:3]
        driving_times, walking_times = get_batch_etas(user_location, top_places)
        
        for i, place in enumerate(top_places):
            place['safe_name'] = place.get("name", "Unknown")
            place['safe_address'] = place.get("formatted_address", place.get("vicinity", ""))
            
            encoded_q = urllib.parse.quote(f"{place['safe_name']} {place['safe_address']}")
            place['encoded_q'] = encoded_q
            place_id = place.get("place_id", "")
            
            if user_location:
                encoded_origin = urllib.parse.quote(user_location)
                place['directions_url'] = f"https://www.google.com/maps/dir/?api=1&origin={encoded_origin}&destination={encoded_q}&destination_place_id={place_id}"
            else:
                place['directions_url'] = f"https://www.google.com/maps/dir/?api=1&destination={encoded_q}&destination_place_id={place_id}"
                
            place['details_url'] = f"https://www.google.com/maps/search/?api=1&query={encoded_q}&query_place_id={place_id}"
            place['driving_time'] = driving_times[i]
            place['walking_time'] = walking_times[i]

        # Extract the names into a clean comma-separated string
        place_names = ", ".join([p['safe_name'] for p in top_places])
        safe_header_names = urllib.parse.quote(place_names)
        
        return templates.TemplateResponse(
            "map_card.html", 
            {
                "request": request, 
                "places": top_places, 
                "user_location": urllib.parse.quote(user_location) if user_location else "",
                "frontend_api_key": FRONTEND_MAPS_KEY
            },
            headers={"Content-Disposition": "inline", "X-MapGO-Places": safe_header_names}
        )
        
    except TemplateNotFound as e:
        logger.error(f"Missing HTML Template: Make sure '{e.name}' is in the app/templates folder.")
        return HTMLResponse(content="<p class='text-red-500'>System Error: UI file missing.</p>", headers={"Content-Disposition": "inline"})
        
    except TemplateError as e:
        logger.error(f"Jinja2 Syntax Error in map_card.html: {e}")
        return HTMLResponse(content="<p class='text-red-500'>System Error: UI failed to render.</p>", headers={"Content-Disposition": "inline"})
        
    except (TypeError, ValueError, KeyError) as e:
        logger.error(f"Data Formatting Error (Bad Google Maps payload): {e}", exc_info=True)
        return HTMLResponse(content="<p class='text-red-500'>Error processing map data.</p>", headers={"Content-Disposition": "inline"})
        
    except Exception as e:
        logger.critical(f"Critical Unexpected Error in /locator: {e}", exc_info=True)
        return HTMLResponse(content="<p class='text-red-500'>Unable to load location data at this time.</p>", headers={"Content-Disposition": "inline"})


@router.get("/itinerary", response_class=HTMLResponse)
@limiter.limit("5/minute")
async def plan_itinerary(request: Request, stops: str, user_location: str = ""):
    try:
        stop_list = [s.strip() for s in re.split(r'\||,|\band\b', stops, flags=re.IGNORECASE) if s.strip()]
        
        if not stop_list:
            return HTMLResponse(content="<p>No stops provided for the itinerary.</p>", headers={"Content-Disposition": "inline"})

        if user_location:
            origin = user_location
            waypoints = stop_list[:-1]
            destination = stop_list[-1]
        else:
            if len(stop_list) < 2:
                return HTMLResponse(content="<p>Need at least 2 stops for an itinerary.</p>", headers={"Content-Disposition": "inline"})
            origin = stop_list[0]
            waypoints = stop_list[1:-1]
            destination = stop_list[-1]

        origin_enc = urllib.parse.quote(origin)
        dest_enc = urllib.parse.quote(destination)
        waypoints_str = "|".join([urllib.parse.quote(w) for w in waypoints])

        embed_url = f"https://www.google.com/maps/embed/v1/directions?key={FRONTEND_MAPS_KEY}&origin={origin_enc}&destination={dest_enc}&mode=driving"
        if waypoints_str:
            embed_url += f"&waypoints={waypoints_str}"

        dir_url = f"https://www.google.com/maps/dir/?api=1&origin={origin_enc}&destination={dest_enc}"
        if waypoints_str:
            dir_url += f"&waypoints={waypoints_str}"

        return templates.TemplateResponse(
            "itinerary_card.html",
            {
                "request": request,
                "all_stops": [origin] + waypoints + [destination],
                "embed_url": embed_url,
                "dir_url": dir_url
            },
            headers={"Content-Disposition": "inline"}
        )
        
    except TemplateNotFound as e:
        logger.error(f"Missing HTML Template: Make sure '{e.name}' is in the app/templates folder.")
        return HTMLResponse(content="<p class='text-red-500'>System Error: UI file missing.</p>", headers={"Content-Disposition": "inline"})
        
    except TemplateError as e:
        logger.error(f"Jinja2 Syntax Error in itinerary_card.html: {e}")
        return HTMLResponse(content="<p class='text-red-500'>System Error: UI failed to render.</p>", headers={"Content-Disposition": "inline"})
        
    except (TypeError, ValueError, AttributeError) as e:
        logger.error(f"Data Formatting Error (Bad itinerary payload): {e}", exc_info=True)
        return HTMLResponse(content="<p class='text-red-500'>Error processing your itinerary route.</p>", headers={"Content-Disposition": "inline"})
        
    except Exception as e:
        logger.critical(f"Critical Unexpected Error in /itinerary: {e}", exc_info=True)
        return HTMLResponse(content="<p class='text-red-500'>Error building itinerary.</p>", headers={"Content-Disposition": "inline"})