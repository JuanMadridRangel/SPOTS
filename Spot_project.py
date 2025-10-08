# -----------------------------
# LIBRARIES
# -----------------------------
import requests  # For making API requests (DAT and Google Maps)
import streamlit as st  # For Streamlit app interface
from datetime import datetime, timezone
from collections import defaultdict
import statistics

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
def get_dat_access_token(force_refresh=False):
    
    if (
        not force_refresh
        and "DAT_BEARER_TOKEN" in st.session_state
        and "DAT_TOKEN_EXPIRY" in st.session_state
    ):
        now = datetime.now(timezone.utc)
        expiry = st.session_state["DAT_TOKEN_EXPIRY"]
        if now < expiry:
            return st.session_state["DAT_BEARER_TOKEN"]  

    
    try:
        org_payload = {
            "username": ORG_USERNAME,
            "password": ORG_PASSWORD
        }
        org_response = requests.post(org_url, json=org_payload)
        org_response.raise_for_status()
        org_token = org_response.json()["accessToken"]

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
        expires_raw = data.get("expiresWhen")

        
        if expires_raw:
            expires_dt = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
        else:
            expires_dt = datetime.now(timezone.utc)  # fallback inmediato

        
        st.session_state["DAT_BEARER_TOKEN"] = access_token
        st.session_state["DAT_TOKEN_EXPIRY"] = expires_dt

        #st.sidebar.success(f"DAT token refreshed\nExpires: {expires_dt.strftime('%Y-%m-%d %H:%M')}")

        return access_token

    except Exception as e:
        st.sidebar.error(f"Error authenticating with DAT: {e}")
        return None


# -----------------------------
# STREAMLIT INITIALIZATION
# -----------------------------
access_token = get_dat_access_token()
st.session_state["DAT_BEARER_TOKEN"] = access_token

st.title("Multis Spot or Contract: Pricing Department")


# -----------------------------
# SELECT CONTRACT OR SPOT
# -----------------------------
st.markdown("""
<style>
/* Container: pastel gradient + frosted card + shadow */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f8fbfd 0%, #e6f6fb 45%, #e8f7f6 100%);
    padding: 26px 22px;
    border-right: 1px solid rgba(22, 31, 45, 0.04);
    box-shadow: 0 10px 30px rgba(14, 30, 60, 0.06);
    backdrop-filter: blur(6px);
    color: #0f1724;
}

/* Headings and titles */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #073763 !important;  /* deep blue accent */
    font-weight: 700;
    margin-bottom: 12px;
}

/* Section headers (markdown ###) */
[data-testid="stSidebar"] .css-1d391kg { color: #073763 !important; } /* fallback for some versions */

/* Labels and small text */
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] .stMarkdown {
    color: #0f1724 !important;
    opacity: 0.9;
}

/* Inputs styling: number input, select, radio; make them look like pills */
[data-testid="stSidebar"] .stNumberInput > div,
[data-testid="stSidebar"] .stRadio,
[data-testid="stSidebar"] .stSelectbox {
    background: #ffffff;
    border-radius: 10px;
    padding: 8px 10px;
    box-shadow: 0 6px 18px rgba(14, 30, 60, 0.04);
    border: 1px solid rgba(14,30,60,0.04);
}

/* Number input inner - remove default borders (works for many versions) */
[data-testid="stSidebar"] input[type="number"] {
    background: transparent;
    border: none;
    outline: none;
    color: #0f1724;
    font-weight: 600;
}

/* Radio buttons labels */
[data-testid="stSidebar"] .stRadio label, 
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label {
    color: #0f1724 !important;
    font-weight: 600;
}


/* Small utility: subtle separators */
[data-testid="stSidebar"] hr {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, rgba(11,108,255,0.06), rgba(0,0,0,0));
    margin: 18px 0;
}

/* Sidebar captions */
[data-testid="stSidebar"] .stCaption {
    color: #475569 !important;
    opacity: 0.9;
}

/* Make toggles/switches nicer */
[data-testid="stSidebar"] .stCheckbox>div, 
[data-testid="stSidebar"] .stSwitch>div {
    padding: 6px;
}

/* Responsive safety for narrow windows (won't shrink below 300) */
@media (max-width: 900px) {
  [data-testid="stSidebar"]{
    width: 320px;
    min-width: 320px;
  }
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Pricing Mode")
    pricing_mode = st.radio("Select pricing mode:", ["Spot", "Contract"])

    if pricing_mode == "Contract":
        months_to_forecast = st.sidebar.number_input(
            "Forecast months",
            min_value=1,
            max_value=12,
            value=12,
            step=1
        )

        if months_to_forecast < 12:
            selected_months = months_to_forecast + 1

        else:
            selected_months=12

    else:
        selected_months = 1
 

    st.markdown("---")
    st.sidebar.markdown("### Quote History")
    if "quote_history" in st.session_state:
        for quote in st.session_state.quote_history:
            lane_label = f"{quote['Lane']}"
            with st.sidebar.expander(lane_label):
                st.write(f"**Mode:** {quote['mode']}")
                st.write(f"**Equipment:** {quote['equipment']}")
                st.write(f"**Rate:** ${quote['rate']}")
    else:
        st.caption("No recent quotes yet.")




# -----------------------------
# USER INPUT: CUSTOMER & EQUIPMENT
# -----------------------------
col1, col2 = st.columns(2)

with col1:
    opcion_stops = st.selectbox("Select Customer:", ["Fabuwood Cabinetry", "Other"])
with col2:
    equipment_type = st.selectbox("Select Equipment Type:", ["VAN", "FLATBED", "REEFER", "STEPDECK", "CONESTOGA", "HOTSHOT"])

# weight para HOTSHOT
hotshot_weight_lbs = None
if equipment_type == "HOTSHOT":
    hotshot_weight_lbs = st.number_input(
        "Hotshot weight (lbs)",
        min_value=0, max_value=40000, value=8000, step=500
    )

# -----------------------------
# LOGIC: VALUE PER STOP BASED ON CUSTOMER
# -----------------------------
if opcion_stops == "Fabuwood Cabinetry":
    variable_stops = 150
elif opcion_stops == "Other":
    variable_stops = 100

# -----------------------------
# ESCALATION TYPE
# -----------------------------
escalation_type = "Best_fit"  # Fixed globally

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


# -----------------------------
# RULES FOR MCI
# -----------------------------

def get_mci_adjustment(mci_score, rules):
    for condition, adjustment in rules:
        if condition(mci_score):
            return adjustment
    return 0


def calculate_auto_markup(mci_data, equipment_type):
    if not mci_data:
        return 0.01

    origin_mci = mci_data["origin_mci"]
    destination_mci = mci_data["destination_mci"]

    # Base por equipo
    if equipment_type == "VAN":
        base_markup = 0.08
    elif equipment_type in ["REEFER", "FLATBED"]:
        base_markup = 0.12
    elif equipment_type == "STEPDECK":
        base_markup = 0.12 + 0.06   # Flatbed (12%) + 6 pp = 18%
    elif equipment_type == "CONESTOGA":
        base_markup = 0.12 + 0.08   # Flatbed (12%) + 8 pp = 20%
    else:
        base_markup = 0.10

    origin_rules = [
        (lambda x: x >= 90, 0.02),
        (lambda x: x >= 75, 0.015),
        (lambda x: x >= 50, 0.01),
        (lambda x: x <= -75, 0.01)
    ]
    destination_rules = [
        (lambda x: x >= 75, -0.02),
        (lambda x: x >= 50, -0.01),
        (lambda x: x <= -75, 0.015)
    ]

    origin_adj = get_mci_adjustment(origin_mci, origin_rules)
    dest_adj = get_mci_adjustment(destination_mci, destination_rules)

    return base_markup + origin_adj + dest_adj


# -----------------------------
# FUNCTION: Identify equipment 
# -----------------------------

def provider_equipment(equipment_type: str) -> str:
    return "FLATBED" if equipment_type in ("STEPDECK", "CONESTOGA", "HOTSHOT") else equipment_type

# -----------------------------
# FUNCTION: Stops Greenscreens  
# -----------------------------

def build_stops_from_locations(locations: list) -> list:
    
    stops = []
    for idx, loc in enumerate(locations):
        parsed = parse_location_string_spots(loc)
        if not parsed:
            continue
        stops.append({
            "order": idx,
            "city": parsed.get("city", ""),
            "state": parsed.get("stateOrProvince", ""),
            "country": "US",
            "zip": parsed.get("postalCode", "")
        })
    return stops

# -----------------------------
# FUNCTION: GET DAT RATE DATA
# -----------------------------
def get_DAT_data(locations, equipment_type, pricing_mode, selected_months):

    headers = {
        "Authorization": f"Bearer {st.session_state['DAT_BEARER_TOKEN']}",
        "Content-Type": "application/json"
    }

   
    if pricing_mode == "Spot":

        origin = parse_location_string_spots(locations[0])
        destination = parse_location_string_spots(locations[-1])

        print("Origin:", origin)
        print("Destination:", destination)
        
        target_escalation = {
            "escalationType": "BEST_FIT"
        }


        body = [
            {
                "origin": origin,
                "destination": destination,
                "rateType": "SPOT",
                "equipment": provider_equipment(equipment_type),
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

        print("Origin:", origin_spot)
        print("Destination:", destination_spot)

        try:

           # --------- Forecast Request (Contract base rate + miles) ---------
            body_forecast = {
                "origin": origin,
                "destination": destination,
                "equipmentCategory": provider_equipment(equipment_type),
                "forecastPeriod": "52WEEKS"
            }

            response_forecast = requests.post(url_forecast, headers=headers, json=body_forecast)
            response_forecast.raise_for_status()
            data_forecast = response_forecast.json()

            per_trip_data = data_forecast.get("forecasts", {}).get("perTrip", [])
            monthly_values = defaultdict(list)

            monthly_values = defaultdict(lambda: {"avg": []})

            for point in per_trip_data:
                date_str = point.get("forecastDate")
                avg_usd = point.get("forecastUSD", 0)

                if not date_str or avg_usd == 0:
                    continue

                date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                year_month = (date.year, date.month)

                monthly_values[year_month]["avg"].append(avg_usd)

           
            sorted_months = sorted(monthly_values.keys())
            selected_month_keys = sorted_months[:selected_months]

            monthly_forecasts = []
            monthly_medians = []

            for ym in selected_month_keys:
                year, month = ym
                values = monthly_values[ym]
                
                med_avg  = statistics.median(values["avg"])

                monthly_medians.append(med_avg)

                monthly_forecasts.append({
                    "date": f"{year}-{month:02d}-01T00:00:00Z",
                    "forecastUSD": int(med_avg),
                })

            if not monthly_medians:
                st.warning("No forecast data available for this lane.")
                return None

            average_rate = sum(monthly_medians) / len(monthly_medians)

            mileage = data_forecast.get("mileage", 0)

            for point in monthly_forecasts:
                print(f"{point['date']} - Avg: ${point['forecastUSD']}")


            # --- Spot request for fuel, high, low (Contract Mode) ---

            if selected_months >= 12:
                specific_timeframe = "180_DAYS"
                rateType = 'CONTRACT'
            elif selected_months >= 3:
                specific_timeframe = "90_DAYS"
                rateType = 'SPOT'
            elif selected_months == 2:
                specific_timeframe = "60_DAYS"
                rateType = 'SPOT'
            else:
                specific_timeframe = "30_DAYS"
                rateType = 'SPOT'

            spot_body_contract = [
                {
                    "origin": origin_spot,
                    "destination": destination_spot,
                    "rateType": rateType,
                    "equipment": provider_equipment(equipment_type),
                    "includeMyRate": True,
                    "targetEscalation": {
                        "escalationType": "SPECIFIC_AREA_TYPE_AND_SPECIFIC_TIME_FRAME",
                        "specificTimeFrame": specific_timeframe,
                        "specificAreaType": "MARKET_AREA"
                    }
                }
            ]


            spot_response = requests.post(url_spot, headers=headers, json=spot_body_contract)
            spot_response.raise_for_status()
            spot_data = spot_response.json()

            rate_block = spot_data["rateResponses"][0]["response"]["rate"]["perTrip"]
            rate_block_fuel = spot_data["rateResponses"][0]["response"]["rate"]

            fuel_per_trip = rate_block_fuel.get("averageFuelSurchargePerTripUsd", 0)
            contract_highUSD = rate_block.get("highUsd", 0)
            contract_lowUSD = rate_block.get("lowUsd", 0)

            print('high:',contract_highUSD)
            print('low:',contract_lowUSD)
            print("Fuel:",fuel_per_trip)

            return {
                "rate": average_rate,
                "miles": mileage,
                "fuel_per_trip": fuel_per_trip,
                "monthly_forecasts": monthly_forecasts,
                "contract_highUSD": contract_highUSD,
                "contract_lowUSD": contract_lowUSD
            }

        

        except Exception as e:
            st.error(f"Error calling DAT Contract logic: {e}")
            return None

# -----------------------------
# FUNCTION: MCI NUMBERS

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
            f"&areaType=MARKET_AREA"
            f"&direction=OUTBOUND"
            f"&equipmentCategory={provider_equipment(equipment_type)}"
            f"&timeframe=PREVIOUS_BUSINESS_DAY"
            f"&city={origin.get('city')}"
            f"&stateOrProvince={origin.get('stateOrProvince')}"
            f"&country=US"
            
            
            
        )

        mci_destination_body = (

            f"page=0"
            f"&pageSize=10"
            f"&areaType=MARKET_AREA"
            f"&direction=OUTBOUND"
            f"&equipmentCategory={provider_equipment(equipment_type)}"
            f"&timeframe=PREVIOUS_BUSINESS_DAY"
            f"&city={destination.get('city')}"
            f"&stateOrProvince={destination.get('stateOrProvince')}"
            f"&country=US"
            
            
            
        )

        # Make requests
        origin_response = requests.get(url_MCI,headers=headers, params = mci_origin_body)
        destination_response = requests.get(url_MCI, headers=headers,params = mci_destination_body)

        origin_response.raise_for_status()
        destination_response.raise_for_status()

        origin_data = origin_response.json()
        destination_data = destination_response.json()

        # Extract values — validate structure before indexing
        mci_origin = origin_data[0]["marketConditionsIndexes"][0]["mciScore"]
        mci_destination = destination_data[0]["marketConditionsIndexes"][0]["mciScore"]

        print(mci_origin,mci_destination)

        if mci_origin is None or mci_destination is None:
            st.warning("Could not retrieve MCI scores for both locations.")
            return None

        return {
            "origin_mci": mci_origin,
            "destination_mci": mci_destination,
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
        stops_array = build_stops_from_locations(locations)

        body = {
            "pickupDateTime": datetime.now(timezone.utc).isoformat(),
            "transportType": provider_equipment(equipment_type),
            "stops":stops_array,
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
def get_route_info(locations, DAT_miles, DAT_average, effective_avg_rate=None, blend_label=None, Mark_up=0.1, chaos_premium=0):

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
        total_distance_miles = round(sum(route["distanceMeters"] for route in data["routes"]) / 1609.344)


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

        if stops > 0:
            base_rate_for_rpm = DAT_average
        else:
            base_rate_for_rpm = effective_avg_rate if effective_avg_rate is not None else DAT_average
            
        RPM = base_rate_for_rpm / DAT_miles
        mileage_charge = RPM * total_distance_miles

        
        miles_diff = total_distance_miles - DAT_miles

           
        if miles_diff >= 0:
            total_cost = round_to_nearest_5(
                mileage_charge + total_additions + increase_per_stop + layover
            )
        else:
            total_cost = round_to_nearest_5(
                base_rate_for_rpm + total_additions + increase_per_stop + layover
            )


        Final_Rate = round_to_nearest_5(total_cost * (1 + Mark_up)) #+ chaos_premium)

        Manual_adj_buy = total_cost - base_rate_for_rpm
        
        correction_factor = effective_avg_rate - DAT_average if effective_avg_rate is not None else 0

        adj_layover = layover  
        adj_extra_stops = increase_per_stop + total_additions
        adj_extra_miles_plus_margin = round((Manual_adj_buy) - (adj_layover + adj_extra_stops), 2) if miles_diff >= 0 else 0

    
   
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
        "effective_avg_rate": base_rate_for_rpm,
        "Stops": stops,
        "Correction_factor": correction_factor,
        "Origin": locations[0]
        }
    
    except Exception as e:
        st.error(f"Error in Google Maps API: {str(e)}")

# -----------------------------
# RESULT
# -----------------------------  
def SHOW_RESULT(route_data, mci_data, gs_data, Mark_up, chaos_data,pricing_mode):

    total_distance_miles = route_data["google_miles"]
    DAT_miles = route_data["dat_miles"]
    DAT_average = route_data["dat_avg_rate"]
    effective_avg = route_data["effective_avg_rate"]
    total_cost = route_data["total_cost"]
    Final_Rate = route_data["final_rate"]
    markup = int(Final_Rate - chaos_data['chaos_premium'] - total_cost)
    adj_layover = route_data["layover"]
    adj_extra_stops = route_data["extra_stops"]
    adj_extra_miles_plus_margin = route_data["extra_miles"]
    correction_factor= route_data["Correction_factor"]
    stops= route_data["Stops"] + 1
    mci_origin = mci_data["origin_mci"]
    mci_destination = mci_data["destination_mci"]
    origin= route_data["Origin"]

    total_all_in = gs_data["rate_per_mile"]
    confidence = gs_data["confidence"]
    print(total_all_in)
    gs_spot_sell = None

    if route_data["Stops"] > 0 and total_all_in:
        gs_spot_sell = round(total_all_in * (1 + Mark_up))

    
    if pricing_mode == "Contract":
        
        market_html = (
            f"<div style='font-weight:700;color:#4b5563;margin-bottom:8px'>DAT Market</div>"
            f"<div style='font-size:14px;color:#111'>"
            f"<strong>DAT Avg Rate:</strong> ${int(DAT_average):,}<br>"
            f"<strong>Base Rate:</strong> ${int(effective_avg):,}"
            f"</div>"
        )
    else:
        
        if gs_spot_sell is not None:
            
            market_html = (
                f"<div style='font-weight:700;color:#4b5563;margin-bottom:8px'>DAT Market</div>"
                f"<div style='font-size:14px;color:#111'>"
                f"<strong>DAT Avg Rate:</strong> ${int(DAT_average):,}<br>"
                f"<strong>Base Rate:</strong> ${int(effective_avg):,}"
                f"</div><br>"
                f"<div style='font-weight:700;color:#4b5563;margin-bottom:8px'>Multi rate</div>"
                f"<div style='font-size:14px;color:#111'>"
                f"<strong>Greenscreens Multi Rate:</strong> ${gs_spot_sell:,} · {confidence}%<br>"
                f"<span style='color:#6b7280;font-size:13px'><strong>DAT Multi Rate:</strong> ${Final_Rate:,}</span>"
                f"</div>"
            )
        else:
            
            market_html = (
                f"<div style='font-weight:700;color:#4b5563;margin-bottom:8px'>DAT Market</div>"
                f"<div style='font-size:14px;color:#111'>"
                f"<strong>DAT Avg Rate:</strong> ${int(DAT_average):,}<br>"
                f"<strong>Base Rate:</strong> ${int(effective_avg):,}"
                f"</div><br>"
                f"<div style='font-weight:700;color:#4b5563;margin-bottom:8px'>Greenscreens Market</div>"
                f"<div style='font-size:14px;color:#111'>"
                f"<strong>Greenscreens Market:</strong> ${total_all_in:,} · {confidence}%"
                f"</div>"
            )



    with st.container():
            st.markdown(
                f"""
                <div style="
                    font-family: Inter, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial;
                    color:#222;
                    max-width:900px;
                    margin:12px auto;
                    ">
                    <!-- Header: origin -> destination -->
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                        <div style="font-size:18px;font-weight:700;color:#111;">
                            <span style="opacity:.85">Origin</span> → <span style="opacity:.6">{origin}</span>
                            <div style="font-size:13px;color:#666;margin-top:4px;"></div>
                        </div>
                        <div style="text-align:right">
                            <div style="font-size:14px;color:#333;font-weight:700">Distance</div>
                            <div style="font-size:13px;color:#666">{stops} stops · {total_distance_miles} mi (Google) · {DAT_miles} mi (DAT)</div>
                        </div>
                    </div>
                    <!-- Grid: left market / right rates -->
                    <div style="display:flex;gap:16px;">
                        <!-- Left card: market & multi -->
                        <div style="flex:1;background:#fff;padding:14px;border-radius:8px;border:1px solid #e6e9ee;box-shadow:0 1px 2px rgba(16,24,40,0.04)">
                            {market_html}
                        </div>
                        <!-- Right card: rates -->
                        <div style="width:340px;background:#fff;padding:14px;border-radius:8px;border:1px solid #e6e9ee;box-shadow:0 1px 2px rgba(16,24,40,0.04)">
                            <div style="font-weight:700;color:#111;font-size:15px;margin-bottom:10px">Rates (All-in)</div>
                            <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px">
                                <div style="font-size:13px;color:#666">Buy Rate</div>
                                <div style="font-size:18px;font-weight:800;color:#0b6cff">${total_cost:,}</div>
                            </div>
                            <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px">
                                <div style="font-size:13px;color:#666">Sell Rate</div>
                                <div style="font-size:18px;font-weight:800;color:#059669">${Final_Rate:,}</div>
                            </div>
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                                <div style="font-size:13px;color:#666">Markup</div>
                                <div style="font-size:15px;font-weight:700">${markup:,}</div>
                            </div>
                            <div style="margin-top:6px;font-size:13px;color:#666">
                                <strong>Correction Factor:</strong> ${int(correction_factor)}
                            </div>
                            <hr style="margin:12px 0;border:none;border-top:1px solid #f4f6f8" />
                            <div style="display:flex;gap:8px;flex-wrap:wrap">
                                <div style="background:#f3f4f6;padding:8px 10px;border-radius:999px;font-size:13px;">Layover: ${adj_layover}</div>
                                <div style="background:#f3f4f6;padding:8px 10px;border-radius:999px;font-size:13px;">Extra stops: ${adj_extra_stops}</div>
                                <div style="background:#f3f4f6;padding:8px 10px;border-radius:999px;font-size:13px;">Extra miles: ${int(adj_extra_miles_plus_margin)}</div>
                            </div>
                            <div style="margin-top:12px;font-size:13px;color:#6b7280">
                                <strong>Market info</strong><br>
                                MCI: {mci_origin} → {mci_destination}
                            </div>
                        </div>
                    </div>
                    <!-- Footer actions -->
                    <div style="margin-top:12px;display:flex;gap:8px;justify-content:flex-end">
                        <button
                            title="Copy the summarized rate text"
                            aria-label="Copy rate"
                            aria-disabled="true"
                            style="background:#0b6cff;color:#fff;padding:10px 14px;border-radius:8px;border:none;cursor:not-allowed;font-weight:600;box-shadow:0 6px 12px rgba(11,108,255,0.14)">
                            Copy rate
                        </button>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )


    total_markup_pct = round(((Final_Rate - total_cost) / total_cost) * 100, 0)
        
   # with st.container():
    #        st.markdown(
     #           f"""
      #          <div style="margin-top:10px; padding:15px; background-color:#fff3cd;
       #           <b>Stops:</b> {Stops}<br>
        #            <b>Volatility:</b> {chaos_data['volatility']}<br>
         #           <b>Skew:</b> {chaos_data['skew']}<br>
          #          <b>Volatility Premium:</b> ${chaos_data['volatility_premium']}<br>
           #         <b>Skew Premium:</b> ${chaos_data['skew_premium']}<br>
            #        <b>Chaos Premium:</b> <b>${chaos_data['chaos_premium']}</b><br>
             #       <b>Risk Level:</b> <span style="color: {'red' if chaos_data['risk_level']=="High Risk" else 'orange' if chaos_data['risk_level']=="Moderate Risk" else 'green'};">
              #      {chaos_data['risk_level']}</span><br><br>
               #     <b>Total Markup %:</b>
                #    <span style="font-size:16px; color:#003366;"><b>{total_markup_pct}%</b></span>
                #</div>
                #""",
                #unsafe_allow_html=True
            #)



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
# CALCULATE CHAOS PREMIUMS 
# -----------------------------
def calculate_chaos_premiums(DAT_avg, DAT_high, DAT_low, miles, adjusted_base_rate):
    if not all([DAT_avg, DAT_high, DAT_low]):
        return {
            "volatility": 0,
            "skew": 0,
            "volatility_premium": 0,
            "skew_premium": 0,
            "chaos_premium": 0,
            "risk_level": "Unknown"
        }

    volatility = (DAT_high - DAT_low) / DAT_avg if DAT_avg else 0
    skew = (DAT_high - DAT_avg) / (DAT_avg - DAT_low) if (DAT_avg - DAT_low) else 0
    upper_spread = DAT_high - DAT_avg

    # Risk level y cap
    if volatility > 0.4 or skew > 2.0:
        risk = "High Risk"
        max_chaos_pct = 0.20
    elif volatility > 0.2 or skew > 1.0:
        risk = "Moderate Risk"
        max_chaos_pct = 0.10
    else:
        risk = "Low Risk"
        max_chaos_pct = 0.05

    if volatility <= 0.1:
        vol_pct = 0.02
    elif volatility <= 0.2:
        vol_pct = 0.04
    elif volatility <= 0.3:
        vol_pct = 0.06
    elif volatility <= 0.4:
        vol_pct = 0.08
    else:
        vol_pct = 0.12

    if skew <= 0.5:
        skew_pct = 0.00
    elif skew <= 1.0:
        skew_pct = 0.04
    elif skew <= 1.5:
        skew_pct = 0.06
    elif skew <= 2.0:
        skew_pct = 0.08
    else:
        skew_pct = 0.12

    raw_vol_premium = vol_pct * upper_spread
    raw_skew_premium = skew_pct * upper_spread
    raw_chaos_premium = raw_vol_premium + raw_skew_premium

    capped_chaos_premium = min(raw_chaos_premium, max_chaos_pct * adjusted_base_rate)

    if raw_chaos_premium > 0:
        vol_premium = round(capped_chaos_premium * (raw_vol_premium / raw_chaos_premium), 2)
        skew_premium = round(capped_chaos_premium * (raw_skew_premium / raw_chaos_premium), 2)
    else:
        vol_premium = 0
        skew_premium = 0


    if miles < 100:
        chaos_multiplier = 0.25
    elif miles < 250:
        chaos_multiplier = 0.5
    else:
        chaos_multiplier = 1.0

    chaos_premium = round((vol_premium + skew_premium) * chaos_multiplier, 2)



    return {
        "volatility": round(volatility, 3),
        "skew": round(skew, 3),
        "volatility_premium": vol_premium,
        "skew_premium": skew_premium,
        "chaos_premium": chaos_premium,
        "risk_level": risk
    }




# -----------------------------
# RUN PRICING FLOW
# -----------------------------

def run_pricing_flow(locations_input, equipment_type, pricing_mode, markup_mode, user_markup=None, hotshot_weight_lbs=None):
    dat_result = get_DAT_data(locations_input, equipment_type, pricing_mode, selected_months)
    if not dat_result:
        st.error("No DAT result returned.")
        return

    raw_avg = dat_result["rate"]
    DAT_fuel_per_trip = dat_result["fuel_per_trip"]
    DAT_miles = dat_result["miles"]
    DAT_average = dat_result["rate"] + round(DAT_fuel_per_trip, 0)

    if pricing_mode == "Spot":
        DAT_high = dat_result["high"]
        DAT_low = dat_result["low"]
    else:
        DAT_high = dat_result["contract_highUSD"]
        DAT_low = dat_result["contract_lowUSD"]

    mci_data = get_MCI_scores(locations_input, equipment_type, url_MCI)

    if not mci_data:
        st.error("Failed to retrieve MCI data.")
        return

    if markup_mode == "Yes" and user_markup is not None:
        Mark_up = user_markup
        st.success(f"Manual markup selected: {round(Mark_up * 100)}%")
    else:
        Mark_up = calculate_auto_markup(mci_data, equipment_type)
        st.success(f"Auto markup based on MCI: {round(Mark_up * 100)}%")

    adjusted_base_rate = raw_avg * (1 + Mark_up)

    
    chaos_data = calculate_chaos_premiums(
        raw_avg,
        DAT_high,
        DAT_low,
        DAT_miles,
        adjusted_base_rate
    )


    
    gs_data = get_greenscreens_rate(locations_input, equipment_type)
    if gs_data:
        total_all_in = gs_data["rate_per_mile"]
        confidence = gs_data["confidence"]

        # calcula stops ANTES del if
        stops = max(0, len(locations_input) - 2)

        use_gs = True
        if pricing_mode == "Contract":
            use_gs = False

       
        if use_gs and stops == 0:

            effective_avg, blend_label = get_effective_avg_rate_with_blending(
                DAT_average, total_all_in, confidence
            )
        else:

            effective_avg = DAT_average
            blend_label = "100% DAT (stops>0)" if stops > 0 else "100% DAT"

        st.caption(f"Base Rate used for cost calculation: {blend_label}")
    else:
        total_all_in = 0
        confidence = 0
        effective_avg = DAT_average
        blend_label = "100% DAT"
        st.caption("Base Rate used: 100% DAT (no GS data)")

    print(equipment_type)
    if equipment_type == "HOTSHOT":
        w = hotshot_weight_lbs or 0 
        hotshot_factor = 1.0 if w > 10000 else 0.8
        effective_avg = round(effective_avg * hotshot_factor)
        

    if "quote_history" not in st.session_state:
        st.session_state.quote_history = []

    from_location = parse_location_string_spots(locations_input[0])
    to_location = parse_location_string_spots(locations_input[-1])

    origin_city = from_location.get("city", "Unknown")
    origin_state = from_location.get("stateOrProvince", "Unknown")
    destination_city = to_location.get("city", "Unknown")
    destination_state = to_location.get("stateOrProvince", "Unknown") 

    route_data = get_route_info(locations_input, DAT_miles, DAT_average, effective_avg, blend_label,Mark_up,chaos_data["chaos_premium"])
    if not route_data:
        st.error("Error processing route information.")
        return
    
    final_rate =  route_data["final_rate"]
    lane_display = f"{origin_city}, {origin_state} → {destination_city}, {destination_state}"  

    

    new_quote = {
        "equipment": equipment_type,
        "mode": pricing_mode,
        "Lane": lane_display,
        "rate": final_rate
    }


    st.session_state.quote_history.insert(0, new_quote)
    st.session_state.quote_history = st.session_state.quote_history[:10]  # máximo 10 elementos

    SHOW_RESULT(route_data, mci_data, gs_data, Mark_up, chaos_data,pricing_mode)



# -----------------------------
# BUTTON ACTION: CALCULATE
# -----------------------------
if st.button("Calculate"):
    if len(locations_input) < 2:
        st.error("Please enter at least two locations.")
    else:
        run_pricing_flow(
            locations_input,
            equipment_type,
            pricing_mode,
            markup_mode,
            user_markup if markup_mode == "Yes" else None,
            hotshot_weight_lbs
        )
   
        
        
            

        
        
            


        
            


        
   
        
        













