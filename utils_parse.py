import streamlit as st
import re

# Función para redondear a múltiplos de 5
def round_to_nearest_5(value):
    return round(value / 5) * 5

def parse_location_string_spots(loc_str):

        parts = [p.strip() for p in loc_str.split(",")]

        if len(parts) >= 3 and re.match(r"^\d{5}$", parts[0]):
            # Tiene ZIP válido + ciudad + estado
            return {
                "postalCode": parts[0],
                "city": parts[1],
                "stateOrProvince": parts[2]
            }
        elif len(parts) >= 2:
            # Solo ciudad + estado
            city = parts[-2]
            state = parts[-1]
            if city and state:
                return {
                    "city": city,
                    "stateOrProvince": state
                }
        raise ValueError(f"Formato de ubicación inválido: {loc_str}")


def parse_location_string_contract(loc_str):

        parts = [p.strip() for p in loc_str.split(",")]

        if len(parts) >= 3 and re.match(r"^\d{5}$", parts[0]):
            # Tiene ZIP válido + ciudad + estado
            return {
                "postalCode": parts[0],
                "city": parts[1],
                "stateProv": parts[2]
            }
        elif len(parts) >= 2:
            # Solo ciudad + estado
            city = parts[-2]
            state = parts[-1]
            if city and state:
                return {
                    "city": city,
                    "stateProv": state
                }
        raise ValueError(f"Formato de ubicación inválido: {loc_str}")


# Fuction to process the input into the code
def parse_locations():
    st.subheader("Input Locations")

    
    # Key used only for the text area field
    text_key = "input_locations_text"

    # Initialize only that specific key if it doesn't exist
    if "clear_text_triggered" in st.session_state and st.session_state["clear_text_triggered"]:
        st.session_state[text_key] = ""
        st.session_state["clear_text_triggered"] = False  


    col1, col2 = st.columns([10, 1])  

    with col1:
         input_text = st.text_area(
            "PUT THE LANE (Copy and paste directly from Vooma):",
            value=st.session_state.get(text_key, ""),
            key=text_key
        )

    with col2:
        st.markdown("###")  # Align vertically
        if st.button("🧼"):
            st.session_state["clear_text_triggered"] = True 
            st.rerun()  


    if input_text:
        pattern = re.compile(r"(?:(?:Add time|AM|PM)\s+)?([A-Z][a-zA-Z\s]+),\s*([A-Z]{2})(?:\s*(\d{5}))?")
        matches = pattern.findall(input_text)

        locations_list = [f"{zip_code if zip_code else ''}, {city.strip()}, {state}" for city, state, zip_code in matches]
        return locations_list
    
    
     
    
  
    return []
