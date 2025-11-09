import re
import urllib.parse as up
import geopy.geocoders as geocoders

#alternative:
#https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html
#https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?address=104+Oak+St,+Maywood,+IL+60153&benchmark=4&format=json

def is_url(input_string):
    try:
        parsed_url = up.urlparse(input_string)
        return bool(parsed_url.scheme and parsed_url.netloc)
    except Exception:
        return False

def get_geocode(location):

    # Regex to match common latitude and longitude formats
    # Examples: "40.7128, -74.0060", "40 42'46\"N, 74 0'22\"W", "40.7128N, 74.0060W"
    lat_lon_pattern = r"^(-?\d{1,3}(?:\.\d+)?(?:[NS])?)\s*,\s*(-?\d{1,3}(?:\.\d+)?(?:[EW])?)$"
    dms_pattern = r"^(-?\d{1,3})\s*(\d{1,2})['’]?\s*(\d{1,2}(?:\.\d+)?)[\"”]?([NS])?,\s*(-?\d{1,3})\s*(\d{1,2})['’]?\s*(\d{1,2}(?:\.\d+)?)[\"”]?([EW])?$"

    if re.match(lat_lon_pattern, location) or re.match(dms_pattern, location):
        # Additional validation for coordinate ranges
        try:
            # Simple check for decimal coordinates
            parts = location.replace('N', '').replace('S', '').replace('E', '').replace('W', '').split(',')
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                #return "coordinates"
                return (lat, lon)
        except ValueError:
            # Handle potential errors if it's not a simple decimal format
            pass
    
    # If not identified as coordinates, assume it's an address
    #return "address"
    geolocator = geocoders.Nominatim(user_agent="Events Calendar")
    result = geolocator.geocode(location)
    if result:
        return (result.latitude, result.longitude)

def parse_location(location):
    if is_url(location):
        url = up.urlparse(location)
        if url.netloc == "maps.google.com":
            query_parts = up.parse_qs(url.query)
            if "q" in query_parts:
                if isinstance(query_parts['q'], list):
                    loc = ",".join(query_parts['q'])
                else:
                    loc = query_parts['q']
                coords = get_geocode(loc)
        else:
            raise Exception
    else:
        coords = get_geocode(location)
    
    return coords

if __name__ == "__main__":
    print(parse_location("https://maps.google.com/?q=41.886236488388,-87.834408828447"))
    print(parse_location("104 Oak St, Maywood, IL 60153"))
    print(parse_location("Way Back Inn 104 Oak St, Maywood, IL 60153")) #fails due to the Way Back Inn part i think
    print(parse_location("41.886236488388, -87.834408828447"))
    print(parse_location("http://maps.google.com/maps?q=104+Oak+St,+Maywood,+IL+60153"))