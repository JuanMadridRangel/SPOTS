import re
import requests  # Librería para hacer peticiones a la API de Google Maps
import streamlit as st

API_KEY = "AIzaSyDWnxUDq9qjCXTQt38OLi6a2l1svGt-owM"  # Clave de API

st.title("Fabus calculator")

# Inputs para el cálculo
DAT_miles = st.number_input("Enter DAT miles:", min_value=1) 
Mark_up = st.slider("Mark-up (%)", 0.0, 1.0, 0.1)
DAT_average = st.number_input("Enter DAT average:", min_value=0.0)

# Validación de Mark-up
if Mark_up < 0 or Mark_up > 1:
    raise ValueError("Mark up percentage must be between 0 and 1.")

# Función para redondear a múltiplos de 5
def round_to_nearest_5(value):
    return round(value / 5) * 5

# Función para obtener información de la ruta con Google Maps API
def get_route_info(locations):
    if len(locations) < 2:
        return {"error": "At least two valid locations are required"}
    
    base_url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "routes.distanceMeters"
    }
    
    request_body = {
        "origin": {"address": locations[0]},
        "destination": {"address": locations[-1]},
        "intermediates": [{"address": loc} for loc in locations[1:-1]],
        "travelMode": "DRIVE",
    }
    
    try:
        response = requests.post(base_url, json=request_body, headers=headers)
        data = response.json()

        total_distance_miles = round(sum(route["distanceMeters"] for route in data["routes"]) / 1609.34)

        ALL_IN = DAT_average + (DAT_average * Mark_up)
        RPM = ALL_IN / DAT_miles

        Days_miles = DAT_miles / 600  
        Google_days = total_distance_miles / 600  

        layover_count = max(0, int(Google_days) - int(Days_miles))  
        layover = layover_count * 200  

        stops = len(locations) - 2  
        increase_per_stop = round((stops / 4) * 150, 2) if stops > 4 else 0

        total_additions = stops * 150

        Add_ins = (RPM * total_distance_miles) + total_additions

        Final_Rate = round_to_nearest_5(Add_ins + increase_per_stop + layover)

        st.subheader("----- Calculation -----")
        st.write(f"Google API miles: {total_distance_miles}")
        st.write(f"Layover count: {layover_count} (x $200 per day)")
        st.write(f"Layover total: ${layover}")
        st.write(f"Stops: {stops}")
        st.write(f"Increase per stop: ${increase_per_stop}")
        st.write(f"Total additions: ${total_additions}")
        st.write(f"Final Rate: ${Final_Rate}")

    except Exception as e:
        return st.error(f"Error en la API: {str(e)}")

# Fuction for process the input into the code
def parse_locations():
    st.subheader("Input Locations")

    # Input en un solo `st.text_area()`
    input_text = st.text_area("\nPUT THE LANE (Copy and paste directly from Vooma):")

    # Verificar que el usuario ingresó texto
    if input_text:
        pattern = re.compile(r"(?:Add time)?([A-Z][a-zA-Z\s]+),\s*([A-Z]{2})\s*(\d{5})")
        matches = pattern.findall(input_text)

        # Lista de ubicaciones formateadas
        locations_list = [f"{zip_code}, {city.strip()}, {state}" for city, state, zip_code in matches]
        return locations_list
    return []


locations_input = parse_locations()


if st.button("Calcular"):
    if len(locations_input) < 2:
        st.error("Ingresa al menos dos ubicaciones.")
    else:
        get_route_info(locations_input)


