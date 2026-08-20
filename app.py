import streamlit as st
import streamlit.components.v1 as components
from railway_api import RailwayAPI
from datetime import datetime, timedelta

st.set_page_config(page_title="BD Railway E-Ticket", page_icon="train", layout="wide")

if "api" not in st.session_state:
    st.session_state.api = RailwayAPI()
    st.session_state.api.handshake()

api = st.session_state.api

if "phase" not in st.session_state:
    st.session_state.phase = "landing"

phase = st.session_state.phase

if phase == "landing":
    components.html(
        """
        <html><head><style>
            body { margin:0; font-family:Arial,sans-serif; }
            .hero {
                background: linear-gradient(135deg, #1976d2, #0d47a1);
                color:white; text-align:center; padding:60px 20px;
                min-height:100vh; display:flex; flex-direction:column;
                justify-content:center; align-items:center;
            }
            h1 { font-size:42px; margin-bottom:10px; }
            p { font-size:18px; opacity:0.9; margin-bottom:30px; }
            .url { background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.3);
                border-radius:8px; padding:12px 24px; font-size:16px; color:white;
                margin-bottom:30px; text-decoration:none; }
        </style></head><body>
            <div class="hero">
                <h1>Bangladesh Railway</h1>
                <p>E-Ticketing Service</p>
                <a href="https://eticket.railway.gov.bd" target="_blank" class="url">eticket.railway.gov.bd</a>
            </div>
        </body></html>
        """,
        height=600,
    )
    if st.button("Continue to App", type="primary", use_container_width=True):
        st.session_state.phase = "trains"
        st.rerun()

elif phase == "trains":
    st.sidebar.title("BD Railway")
    logged_in = api.auth_token is not None

    if logged_in:
        st.sidebar.success("Logged In")
        if st.sidebar.button("Logout", use_container_width=True):
            api.logout()
            st.rerun()
        if st.sidebar.button("Search Trains", use_container_width=True):
            st.session_state.phase = "search"
            st.rerun()
    else:
        st.sidebar.warning("Not Logged In")
        if st.sidebar.button("Login with Token", use_container_width=True):
            st.session_state.phase = "token_login"
            st.rerun()

    st.subheader("All Trains")

    if api.cities:
        search = st.text_input("Filter by station name", placeholder="e.g. Dhaka, Chittagong")
        filtered_cities = api.cities
        if search:
            filtered_cities = [c for c in api.cities if search.lower() in c.get("city_name", "").lower()]

        st.caption(f"Total stations: {len(filtered_cities)}")

        cols = st.columns(3)
        for i, city in enumerate(filtered_cities[:90]):
            with cols[i % 3]:
                st.write(f"- {city.get('city_name', '')} (ID: {city.get('city_id', '')})")

    st.divider()

    with st.spinner("Loading all trains..."):
        result = api.get_all_trains()

    if result["success"]:
        trains = result["trains"]
        st.subheader(f"All Trains ({len(trains)})")

        filter_from = st.text_input("Filter by origin", placeholder="e.g. Dhaka")
        filter_to = st.text_input("Filter by destination", placeholder="e.g. Chattogram")

        filtered = trains
        if filter_from:
            filtered = [t for t in filtered if filter_from.lower() in t.get("origin_city", "").lower()]
        if filter_to:
            filtered = [t for t in filtered if filter_to.lower() in t.get("destination_city", "").lower()]

        if filtered:
            st.write(f"Showing {len(filtered)} trains")
            for t in filtered:
                with st.expander(f"Train {t.get('train_number', '')} - {t.get('origin_city', '')} to {t.get('destination_city', '')}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write(f"**Train No:** {t.get('train_number', '')}")
                    with c2:
                        st.write(f"**From:** {t.get('origin_city', '')}")
                        st.write(f"**To:** {t.get('destination_city', '')}")
                    with c3:
                        st.write(f"**Zone:** {t.get('zone', '')}")
                        st.write(f"**Opening:** {t.get('opening_time', '')}")
        else:
            st.info("No trains match filter")
    else:
        st.error(result["message"])

elif phase == "token_login":
    st.sidebar.title("BD Railway")
    if st.sidebar.button("Back", use_container_width=True):
        st.session_state.phase = "trains"
        st.rerun()

    st.subheader("Login with Auth Token")
    st.info("1. Open eticket.railway.gov.bd in your browser\n2. Login with your phone\n3. Press F12 -> Application -> Local Storage\n4. Find 'token' or 'auth_token' and copy it\n5. Paste below")

    token = st.text_area("Paste your auth token here", height=100, placeholder="eyJhbGciOiJIUzI1NiIs...")

    if st.button("Verify & Login", type="primary", use_container_width=True):
        if not token.strip():
            st.error("Paste your token")
        else:
            with st.spinner("Verifying token..."):
                result = api.set_token(token.strip())
            if result["success"]:
                st.success(result["message"])
                st.session_state.phase = "search"
                st.rerun()
            else:
                st.error(result["message"])

elif phase == "search":
    st.sidebar.title("BD Railway")
    st.sidebar.success("Logged In")
    if st.sidebar.button("All Trains", use_container_width=True):
        st.session_state.phase = "trains"
        st.rerun()
    if st.sidebar.button("Logout", use_container_width=True):
        api.logout()
        st.session_state.phase = "trains"
        st.rerun()

    st.subheader("Search Trains")

    cities = api.cities
    city_names = [c.get("city_name", "") for c in cities] if cities else []
    city_ids = [str(c.get("city_id", "")) for c in cities] if cities else []

    c1, c2, c3 = st.columns(3)

    with c1:
        if city_names:
            from_idx = st.selectbox("From", range(len(city_names)), format_func=lambda i: city_names[i], key="from")
            from_city = city_ids[from_idx]
        else:
            from_city = st.text_input("From City ID")

    with c2:
        if city_names:
            to_idx = st.selectbox("To", range(len(city_names)), format_func=lambda i: city_names[i], key="to")
            to_city = city_ids[to_idx]
        else:
            to_city = st.text_input("To City ID")

    with c3:
        tomorrow = datetime.now() + timedelta(days=1)
        travel_date = st.date_input("Date", value=tomorrow, min_value=datetime.now())
        date_str = travel_date.strftime("%Y-%m-%d")

    seat_type_map = {"SHOVAN": 1, "SHOVAN_CHAIR": 2, "SNIGDHA": 3, "TURNTA": 4, "AC_SEAT": 5, "AC_BERTH": 6, "FIRST_CLASS": 7}
    seat_type_name = st.selectbox("Seat Class", list(seat_type_map.keys()))
    seat_type = seat_type_map[seat_type_name]

    if st.button("Search", type="primary", use_container_width=True):
        with st.spinner("Searching..."):
            result = api.search_trips(from_city, to_city, date_str, seat_type)

        if result["success"]:
            trains = result["trains"]
            if trains:
                st.subheader(f"Found {len(trains)} Train(s)")
                for train in trains:
                    name = train.get("train_name", train.get("name", "Unknown"))
                    number = train.get("train_number", train.get("number", ""))
                    dep = train.get("departure_time", train.get("depart_time", ""))
                    arr = train.get("arrival_time", train.get("arrive_time", ""))
                    fare = train.get("fare", train.get("ticket_price", ""))
                    avail = train.get("available_seats", train.get("seats_available", ""))
                    tid = str(train.get("train_id", train.get("id", "")))
                    trip_id = str(train.get("trip_id", ""))

                    with st.expander(f"{number} - {name}"):
                        cc1, cc2, cc3 = st.columns(3)
                        with cc1:
                            st.write(f"**Departure:** {dep}")
                            st.write(f"**Arrival:** {arr}")
                        with cc2:
                            st.write(f"**Fare:** {fare} BDT")
                        st.write(f"**Available:** {avail}")

                        if st.button("View Seats", key=f"seat_{tid}_{trip_id}"):
                            with st.spinner("Loading..."):
                                seat_result = api.get_seat_layout(tid, trip_id, date_str, seat_type)
                            if seat_result["success"]:
                                layout = seat_result["layout"]
                                st.json(layout)
                            else:
                                st.error(seat_result["message"])
            else:
                st.warning("No trains found")
        else:
            st.error(result["message"])
