# -----------------------------
# LIBRARIES
# -----------------------------
import requests  # For making API requests (DAT and Google Maps)
import streamlit as st  # For Streamlit app interface
from datetime import datetime

# -----------------------------
# CONNECTIONS / CONFIG IMPORTS
# -----------------------------
from Access import user_url, org_url, url_spot, base_url,url_forecast, url_MCI, GS_CLIENT_ID, GS_AUTH_URL, GS_PREDICT_URL
from utils_parse import parse_location_string_spots,parse_location_string_contract, parse_locations, round_to_nearest_5

# -----------------------------
# Google Maps API Credentials
# -----------------------------
API_KEY= st.secrets["API_KEY"]


# -----------------------------
# DAT API Credentials
# -----------------------------
ORG_USERNAME = st.secrets["ORG_USERNAME"]
ORG_PASSWORD = st.secrets["ORG_PASSWORD"]
ACCOUNT_USERNAME = st.secrets["ACCOUNT_USERNAME"]


# -----------------------------
# GREENSCREENS API URL
# -----------------------------
GS_CLIENT_SECRET = st.secrets["GS_CLIENT_SECRET"] # client_secret

# -----------------------------
# FUNCTIONS: DAT AUTHENTICATION
# -----------------------------
def get_dat_access_token():
    try:
        # Step 1: Login with organization credentials
        org_payload = {
            "username": ORG_USERNAME,
            "password": ORG_PASSWORD
        }
        org_response = requests.post(org_url, json=org_payload)
        org_response.raise_for_status()
        org_token = org_response.json()["accessToken"]

        # Step 2: Login with user account
        user_payload = {
            "username": ACCOUNT_USERNAME
        }
        user_headers = {
            "Authorization": f"Bearer {org_token}"
        }
        user_response = requests.post(user_url, json=user_payload, headers=user_headers)
        user_response.raise_for_status()
        data = user_response.json()

        access_token = data["accessToken"]
        expiration = data.get("expiresWhen", "Desconocido")

        # Show confirmation in sidebar
        st.sidebar.success(f"DAT token generated\nExpires: {expiration}")

        return access_token

    except Exception as e:
        st.sidebar.error(f"Error authenticating with DAT: {e}")
        return None

# -----------------------------
# STREAMLIT INITIALIZATION
# -----------------------------
if "DAT_BEARER_TOKEN" not in st.session_state:
    st.session_state["DAT_BEARER_TOKEN"] = get_dat_access_token()

st.title("Multis Spot or Contract: Pricing Department")

with st.sidebar:
    st.markdown("### Token Manager")
    if st.button("Refresh DAT Token"):
        st.session_state["DAT_BEARER_TOKEN"] = get_dat_access_token()

# -----------------------------
# SELECT CONTRACT OR SPOT
# -----------------------------

with st.sidebar:
    st.markdown("### Pricing Mode")
    pricing_mode = st.radio("Select pricing mode:", ["Spot", "Contract"])


# -----------------------------
# USER INPUT: CUSTOMER & EQUIPMENT
# -----------------------------
col1, col2 = st.columns(2)

with col1:
    opcion_stops = st.selectbox("Select Customer:", ["Fabuwood Cabinetry", "Other"])
with col2:
    equipment_type = st.selectbox("Select Equipment Type:", ["VAN", "FLATBED", "REEFER"])

# -----------------------------
# LOGIC: VALUE PER STOP BASED ON CUSTOMER
# -----------------------------
if opcion_stops == "Fabuwood Cabinetry":
    variable_stops = 150
elif opcion_stops == "Other":
    variable_stops = 100

# -----------------------------
# USER INPUT: ESCALATION TYPE
# -----------------------------
with st.sidebar:
    st.markdown("### DAT Rate Options")
    escalation_type = st.selectbox(
        "Select Escalation Type:",
        options=["Best_fit", "Specific (7 Days, Zip code)"],
        help="Use 'Best_fit' when ZIPs are missing or for broader data. Use 'Specific' for more accurate Zip codes results."
    )



# -----------------------------
# FUNCTION: Markup
# -----------------------------


markup_mode = st.radio(
    "Do you want to input your own markup?",
    options=["Yes", "No"],
    horizontal=True,
    index=1
    )

Mark_up=None

if markup_mode == "Yes":
    user_markup = st.number_input(
        "Enter your mark-up",
        min_value=0.0,
        max_value=1.0,
        value=0.1,
        step=0.01,
    )
    Mark_up = user_markup
    st.info(f"Manual markup selected: {round(Mark_up * 100, 2)}%")
else:
    st.info("Markup will be calculated automatically based on MCI values once you press Calculate.")


def calculate_auto_markup(locations, equipment_type):
    
    mci_data = get_MCI_scores(locations, equipment_type, url_MCI)

    if not mci_data:
        return 0.07 if equipment_type == "VAN" else 0.12  # fallback por equipo

    origin_mci = mci_data["origin_mci"]
    destination_mci = mci_data["destination_mci"]

   
    if equipment_type == "VAN":
        base_markup = 0.08
    elif equipment_type in ["REEFER", "FLATBED"]:
        base_markup = 0.12
    else:
        base_markup = 0.1

    
    origin_adj = 0
    if origin_mci >= 90:
        origin_adj = 0.02
    elif origin_mci >= 75:
        origin_adj = 0.015
    elif origin_mci >= 50:
        origin_adj = 0.01
    elif origin_mci <= -75:
        origin_adj = 0.01

    dest_adj = 0
    if destination_mci >= 75:
        dest_adj = -0.02
    elif destination_mci >= 50:
        dest_adj = -0.01
    elif destination_mci <= -75:
        dest_adj = 0.015

    return base_markup + origin_adj + dest_adj



# -----------------------------
# FUNCTION: GET DAT RATE DATA
# -----------------------------
def get_DAT_data(locations, equipment_type, pricing_mode):

    headers = {
        "Authorization": f"Bearer {st.session_state['DAT_BEARER_TOKEN']}",
        "Content-Type": "application/json"
    }

   
    if pricing_mode == "Spot":

        origin = parse_location_string_spots(locations[0])
        destination = parse_location_string_spots(locations[-1])

        print("Origin:", origin)
        print("Destination:", destination)

        # Check if ZIP codes exist
        has_zip = "postalCode" in origin and "postalCode" in destination

        
        # Define escalation block
        if escalation_type == "Specific (7 Days, Zip code)" and has_zip:
            target_escalation = {
                "escalationType": "SPECIFIC_AREA_TYPE_AND_SPECIFIC_TIME_FRAME",
                "specificTimeFrame": "7_DAYS",
                "specificAreaType": "3_DIGIT_ZIP"
            }
        else:
            target_escalation = {
                "escalationType": "BEST_FIT"
            }

        body = [
            {
                "origin": origin,
                "destination": destination,
                "rateType": "SPOT",
                "equipment": equipment_type,
                "includeMyRate": True,
                "targetEscalation": target_escalation
            }
        ]

        try:
            response = requests.post(url_spot, headers=headers, json=body)
            print("DAT status:", response.status_code)
            print("DAT response:", response.text)
            response.raise_for_status()

            data = response.json()
            rate_response_full = data["rateResponses"][0]["response"]

            if "rate" not in rate_response_full:
                if escalation_type == "SPECIFIC (30 DAYS, 3-DIGIT ZIP)" and has_zip:
                    st.warning("No rates available for this lane using ZIP codes and a 30-day time frame.")
                else:
                    st.warning("No DAT rates available for this lane at the moment.")
                return None

            rate_response = rate_response_full["rate"]

            return {
                "rate": rate_response["perTrip"]["rateUsd"],
                "high": rate_response["perTrip"]["highUsd"],
                "low": rate_response["perTrip"]["lowUsd"],
                "miles": rate_response["mileage"],
                "fuel_per_trip": rate_response.get("averageFuelSurchargePerTripUsd")

            }

        except Exception as e:
            st.error(f"Error calling DAT API: {e}")
            return None
        
    elif pricing_mode == "Contract":

        origin = parse_location_string_contract(locations[0])
        destination = parse_location_string_contract(locations[-1])

        origin_spot = parse_location_string_spots(locations[0])
        destination_spot = parse_location_string_spots(locations[-1])

        print("Origin:", origin)
        print("Destination:", destination)

        # Check if ZIP codes exist
        has_zip = "postalCode" in origin and "postalCode" in destination

        try:

           # --------- Forecast Request (Contract base rate + miles) ---------
            body_forecast = {
                "origin": origin,
                "destination": destination,
                "equipmentCategory": equipment_type,
                "forecastPeriod": "52WEEKS"
            }

            response_forecast = requests.post(url_forecast, headers=headers, json=body_forecast)
            response_forecast.raise_for_status()
            data_forecast = response_forecast.json()

            per_trip_data = data_forecast.get("forecasts", {}).get("perTrip", [])
            seen_months = set()
            monthly_forecasts = []

            for point in per_trip_data:
                date_str = point.get("forecastDate")
                avg_usd = point.get("forecastUSD", 0)
                mae_data = point.get("mae", {})
                low_usd = mae_data.get("lowUSD", 0)
                high_usd = mae_data.get("highUSD", 0)

                if not date_str or avg_usd == 0:
                    continue

                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                year_month = (date.year, date.month)

                if year_month not in seen_months:
                    seen_months.add(year_month)
                    monthly_forecasts.append({
                        "date": date_str,
                        "forecastUSD": int(avg_usd),
                        "lowUSD": int(low_usd),
                        "highUSD": int(high_usd)
                    })

                if len(monthly_forecasts) == 12:
                    break

            # Print results
            for point in monthly_forecasts:
                print(f"{point['date']} - Avg: ${point['forecastUSD']} | Low: ${point['lowUSD']} | High: ${point['highUSD']}")

            forecast_values = [p["forecastUSD"] for p in monthly_forecasts]

            if not forecast_values:
                st.warning("No forecast data available for this lane.")
                return None

            average_rate = sum(forecast_values) / len(forecast_values)
            mileage = data_forecast.get("mileage", 0)

           
            # --- Spot request for fuel ---
            fuel_body = [
                {
                    "origin": origin_spot,
                    "destination": destination_spot,
                    "rateType": "SPOT",
                    "equipment": equipment_type,
                    "includeMyRate": True,
                    "targetEscalation": {
                        "escalationType": "BEST_FIT"
                    }
                }
            ]

            fuel_response = requests.post(url_spot, headers=headers, json=fuel_body)
            fuel_response.raise_for_status()
            fuel_data = fuel_response.json()
            fuel_response_data = fuel_data["rateResponses"][0]["response"]

            rate_block = fuel_response_data.get("rate", {})
            fuel_per_trip = rate_block.get("averageFuelSurchargePerTripUsd", 0)

            return {
                "rate": average_rate,
                "miles": mileage,
                "fuel_per_trip": fuel_per_trip
            }
        

        except Exception as e:
            st.error(f"Error calling DAT Contract logic: {e}")
            return None

# -----------------------------
# FUNCTION: GOOGLE MAPS ROUTE & PRICING

# -----------------------------

def get_MCI_scores(locations, equipment_type, url_MCI):
    headers = {
        "Authorization": f"Bearer {st.session_state['DAT_BEARER_TOKEN']}",
        "Content-Type": "application/json"
    }

    try:
        # Parse origin and destination using existing logic
        origin = parse_location_string_spots(locations[0])
        destination = parse_location_string_spots(locations[-1])

        print(origin,destination)

        # Prepare both MCI requests
        mci_origin_body = (

            f"page=0"
            f"&pageSize=10"
            f"&city={origin.get('city')}"
            f"&stateOrProvince={origin.get('stateOrProvince')}"
            f"&country=US"
            f"&areaType=MARKET_AREA"
            f"&equipmentCategory={equipment_type}"
            f"&timeframe=EIGHT_DAY_FORECAST"
            f"&direction=OUTBOUND"
            
        )

        mci_destination_body = (

        f"page=0"
        f"&pageSize=10"
        f"&city={destination.get('city')}"
        f"&stateOrProvince={destination.get('stateOrProvince')}"
        f"&country=US"
        f"&areaType=MARKET_AREA"
        f"&equipmentCategory={equipment_type}"
        f"&timeframe=EIGHT_DAY_FORECAST"
        f"&direction=OUTBOUND"
            
        )

        # Make requests
        origin_response = requests.get(url_MCI,headers=headers, params = mci_origin_body)
        destination_response = requests.get(url_MCI, headers=headers,params = mci_destination_body)

        origin_response.raise_for_status()
        destination_response.raise_for_status()

        origin_data = origin_response.json()
        destination_data = destination_response.json()

        # Extract values — validate structure before indexing
        mci_origin = origin_data[0]["marketConditionsForecasts"][0]["mciScore"]
        mci_destination = destination_data[0]["marketConditionsForecasts"][0]["mciScore"]

        print(mci_origin,mci_destination)

        if mci_origin is None or mci_destination is None:
            st.warning("Could not retrieve MCI scores for both locations.")
            return None

        return {
            "origin_mci": mci_origin,
            "destination_mci": mci_destination
        }

    except Exception as e:
        st.error(f"Error retrieving MCI data: {e}")
        return None



# -----------------------------
# FUNCTION: GREENSCREENS
# -----------------------------
def get_greenscreens_rate(locations, equipment_type):
    try:
        from datetime import datetime, timezone

        # Step 1: AUTH - Get token
        auth_payload = {
            "client_id": GS_CLIENT_ID,
            "client_secret": GS_CLIENT_SECRET,
            "grant_type": "client_credentials"
        }

        auth_headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        auth_response = requests.post(GS_AUTH_URL, data=auth_payload, headers=auth_headers)
        auth_response.raise_for_status()
        access_token = auth_response.json().get("access_token")

        if not access_token:
            st.error("Failed to obtain GreenScreens access token.")
            return None
        
        # Step 2: Build body for prediction
        origin = parse_location_string_spots(locations[0])
        destination = parse_location_string_spots(locations[-1])

        body = {
            "pickupDateTime": datetime.now(timezone.utc).isoformat(),
            "transportType": equipment_type,
            "stops": [
                {
                    "order": 0,
                    "city": origin["city"],
                    "state": origin["stateOrProvince"],
                    "country": "US",
                    "zip": origin.get("postalCode", "")
                },
                {
                    "order": 1,
                    "city": destination["city"],
                    "state": destination["stateOrProvince"],
                    "country": "US",
                    "zip": destination.get("postalCode", "")
                }
            ],
            "commodity": "General Freight",
            "currency": "USD"
        }

        # Step 3: Call prediction endpoint
        prediction_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        prediction_response = requests.post(GS_PREDICT_URL, json=body, headers=prediction_headers)
        prediction_response.raise_for_status()
        data = prediction_response.json()
        rpm = data.get("targetBuyRate", 0)
        distance = data.get("distance", 0)
        confidence = data.get("confidenceLevel", 0)
        total_all_in = int((rpm) * distance)

        print(total_all_in,confidence)

        if total_all_in is None or confidence is None:
            st.warning("No valid rate or confidence returned from GreenScreens.")
            return None

        return {
            "rate_per_mile": total_all_in,
            "confidence": confidence
        }

        

    except Exception as e:
        st.error(f"Error getting GreenScreens data: {e}")
        return None



# -----------------------------
# FUNCTION: GOOGLE MAPS ROUTE & PRICING
# -----------------------------
def get_route_info(locations, DAT_miles, DAT_average, effective_avg_rate=None, blend_label=None):
    if len(locations) < 2:
        return {"error": "At least two valid locations are required"}

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
        # 1. Calculate Google miles (real route distance)
        total_distance_miles = round(sum(route["distanceMeters"] for route in data["routes"]) / 1609.34)


        # 2. Layover logic
        Days_miles = DAT_miles / 600
        Google_days = total_distance_miles / 600
        layover_count = max(0, int(Google_days) - int(Days_miles))

        # 3. Stops logic
        stops = len(locations) - 2
        total_additions = stops * variable_stops

        if opcion_stops == "Fabuwood Cabinetry":
            layover = layover_count * 125
            increase_per_stop = round((stops / 4) * 100, 2) if stops > 4 else 0
        else:
            layover = layover_count * 200
            increase_per_stop = round((stops / 4) * 150, 2) if stops > 4 else 0 


        base_rate_for_rpm = effective_avg_rate if effective_avg_rate is not None else DAT_average
        RPM = base_rate_for_rpm / DAT_miles
        mileage_charge = RPM * total_distance_miles

        
        miles_diff = total_distance_miles - DAT_miles

        
        if miles_diff >= 0:
            total_cost = round_to_nearest_5(mileage_charge + total_additions + increase_per_stop + layover)
        else:
            total_cost = round_to_nearest_5(base_rate_for_rpm + total_additions + increase_per_stop + layover)


        Final_Rate = round_to_nearest_5(total_cost * (1 + Mark_up))

        Manual_adj_buy = total_cost - DAT_average

        adj_layover = layover  # Ya está calculado con base en días extras
        adj_extra_stops = increase_per_stop + total_additions  # Ya está calculado
        adj_extra_miles_plus_margin = round((Manual_adj_buy) - (adj_layover + adj_extra_stops), 2)
   
        return {
        "google_miles": total_distance_miles,
        "dat_miles": DAT_miles,
        "dat_avg_rate": DAT_average,
        "total_cost": total_cost,
        "final_rate": Final_Rate,
        "layover": adj_layover,
        "extra_stops": adj_extra_stops,
        "extra_miles": adj_extra_miles_plus_margin,
        "blend_label": blend_label,
        "effective_avg_rate": base_rate_for_rpm
        }
    
    except Exception as e:
        st.error(f"Error in Google Maps API: {str(e)}")

# -----------------------------
# RESULT
# -----------------------------  
def SHOW_RESULT(route_data, mci_data, gs_data):
    total_distance_miles = route_data["google_miles"]
    DAT_miles = route_data["dat_miles"]
    DAT_average = route_data["dat_avg_rate"]
    effective_avg = route_data["effective_avg_rate"]
    total_cost = route_data["total_cost"]
    Final_Rate = route_data["final_rate"]
    markup = int(total_cost * Mark_up)
    adj_layover = route_data["layover"]
    adj_extra_stops = route_data["extra_stops"]
    adj_extra_miles_plus_margin = route_data["extra_miles"]
    
    mci_origin = mci_data["origin_mci"]
    mci_destination = mci_data["destination_mci"]

    total_all_in = gs_data["rate_per_mile"]
    confidence = gs_data["confidence"]

    with st.container():
            st.markdown(
                f"""
                <div style="background-color:#f8f9fa;padding:15px 20px;border-radius:8px;
                            border:1px solid #ccc;margin-top:15px;font-family:sans-serif;
                            font-size:14px;line-height:1.6;">
                    <b style="font-size:16px;color:#333;">📈 RESULT</b><br><br>
                    <b>Google Miles:</b> {total_distance_miles} &nbsp;&nbsp;&nbsp;
                    <b>DAT Miles:</b> {DAT_miles} &nbsp;&nbsp;&nbsp;
                    <b>DAT Avg Rate:</b> ${int(DAT_average)} &nbsp;&nbsp;&nbsp;
                    <b>Base Rate:</b> ${int(effective_avg)}<br>
                    <b>GS:</b> ${total_all_in} | {confidence}% &nbsp;&nbsp;&nbsp;
                    <b>Buy Rate:</b> ${total_cost} &nbsp;&nbsp;&nbsp;
                    <b>Sell Rate:</b> ${Final_Rate} &nbsp;&nbsp;&nbsp;
                    <b>Markup:</b> ${markup}<br>
                    <b>Layover:</b> ${adj_layover} &nbsp;&nbsp;&nbsp;
                    <b>Extra Stops:</b> ${adj_extra_stops} &nbsp;&nbsp;&nbsp;
                    <b>Extra Miles:</b> ${int(adj_extra_miles_plus_margin)} &nbsp;&nbsp;&nbsp;
                    <b>MCI:</b> {mci_origin} → {mci_destination}
                </div>
                """,
            unsafe_allow_html=True
            )

# -----------------------------
# LOCATION INPUT & PARSING
# -----------------------------
locations_input = parse_locations()
print(locations_input)





# -----------------------------
# GS AND DAT
# -----------------------------


def get_effective_avg_rate_with_blending(DAT_average, total_all_in, confidence):
    
    print(confidence)
    if total_all_in > 0 and confidence >= 89:
        base_rate = 0.5 * DAT_average + 0.5 * total_all_in
        blend_label = "50/50 DAT GS"
    elif total_all_in > 0 and confidence >= 76:
        base_rate = 0.65 * DAT_average + 0.35 * total_all_in
        blend_label = "65/35 DAT GS"
    else:
        base_rate = DAT_average
        blend_label = "100% DAT"

    
    if total_all_in > 0:
        discrepancy_pct = abs(DAT_average - total_all_in) / DAT_average * 100
        if discrepancy_pct > 20:
            st.caption("GS and DAT differ by more than 20%. Defaulting to DAT.")
        elif discrepancy_pct > 10:
            st.caption("GS and DAT differ by more than 10%.")

    return round(base_rate), blend_label


# -----------------------------
# BUTTON ACTION: CALCULATE
# -----------------------------
if st.button("Calculate"):
    if len(locations_input) < 2:
        st.error("Please enter at least two locations.")
    else:
        dat_result = get_DAT_data(locations_input, equipment_type, pricing_mode)
        
        if dat_result:
            DAT_fuel_per_trip = dat_result["fuel_per_trip"]
            DAT_miles = dat_result["miles"]
            DAT_average = dat_result["rate"] + round(DAT_fuel_per_trip, 0)

            if pricing_mode == "Spot":
                DAT_high = dat_result["high"]
                DAT_low = dat_result["low"]
            else: 
                
                forecasts = dat_result.get("monthly_forecasts", [])
                if forecasts:
                    DAT_high = max(point["highUSD"] for point in forecasts)
                    DAT_low = min(point["lowUSD"] for point in forecasts)

            if markup_mode == "Yes":
                Mark_up = user_markup
                st.success(f"Manual markup selected: {round(Mark_up * 100)}%")
            else:
                Mark_up = calculate_auto_markup(locations_input, equipment_type)
                st.success(f"Auto markup based on MCI: {round(Mark_up * 100)}%")

            mci_data = get_MCI_scores(locations_input, equipment_type, url_MCI)
            gs_data = get_greenscreens_rate(locations_input, equipment_type)

            if gs_data:
                total_all_in = gs_data["rate_per_mile"]
                confidence = gs_data["confidence"]

                effective_avg, blend_label = get_effective_avg_rate_with_blending(DAT_average, total_all_in, confidence)
                st.caption(f"Base Rate used for cost calculation: {blend_label}")

            else:
                total_all_in = 0
                confidence = 0
                effective_avg = DAT_average
                st.caption("Base Rate used: 100% DAT (no GS data)")

            route_data = get_route_info(
                locations_input,
                DAT_miles,
                DAT_average,
                effective_avg,
                blend_label
            )

            if mci_data and gs_data and route_data:
                SHOW_RESULT(route_data, mci_data, gs_data)



