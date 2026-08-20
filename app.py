import streamlit as st
from railway_api import RailwayAPI
from datetime import datetime, timedelta

st.set_page_config(page_title="BD Railway E-Ticket", page_icon="train", layout="wide")

if "api" not in st.session_state:
    st.session_state.api = RailwayAPI()
    st.session_state.api.handshake()

api = st.session_state.api

st.title("Bangladesh Railway E-Ticket")

logged_in = api.auth_token is not None

if not logged_in:
    st.info(
        "**How to login:**\n"
        "1. Open [eticket.railway.gov.bd](https://eticket.railway.gov.bd) in a new tab\n"
        "2. Login with your phone and password\n"
        "3. Press **F12** on keyboard\n"
        "4. Go to **Application** tab → **Local Storage** → `eticket.railway.gov.bd`\n"
        "5. Find `token` or `auth_token` → copy the value\n"
        "6. Paste it below"
    )

    token = st.text_input("Paste your auth token", placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")

    if st.button("Login", type="primary", use_container_width=True):
        if token.strip():
            with st.spinner("Verifying..."):
                result = api.set_token(token.strip())
            if result["success"]:
                st.success(result["message"])
                st.rerun()
            else:
                st.error(result["message"])
        else:
            st.error("Paste your token")

    st.divider()

    st.subheader("All Trains (No Login Needed)")

    with st.spinner("Loading trains..."):
        result = api.get_all_trains()

    if result["success"]:
        trains = result["trains"]
        st.write(f"Total trains: {len(trains)}")

        filter_from = st.text_input("Filter origin", placeholder="e.g. Dhaka")
        filter_to = st.text_input("Filter destination", placeholder="e.g. Chattogram")

        filtered = trains
        if filter_from:
            filtered = [t for t in filtered if filter_from.lower() in t.get("origin_city", "").lower()]
        if filter_to:
            filtered = [t for t in filtered if filter_to.lower() in t.get("destination_city", "").lower()]

        if filtered:
            for t in filtered:
                st.write(f"**Train {t.get('train_number', '')}** - {t.get('origin_city', '')} to {t.get('destination_city', '')} ({t.get('zone', '')})")
        else:
            st.info("No trains match filter")

else:
    st.sidebar.success("Logged In")
    if st.sidebar.button("Logout", use_container_width=True):
        api.logout()
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

    seat_types = {"SHOVAN": 1, "SHOVAN_CHAIR": 2, "SNIGDHA": 3, "TURNTA": 4, "AC_SEAT": 5, "AC_BERTH": 6, "FIRST_CLASS": 7}
    seat_type_name = st.selectbox("Seat Class", list(seat_types.keys()))
    seat_type = seat_types[seat_type_name]

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
                        with cc3:
                            st.write(f"**Available:** {avail}")

                        if st.button("View Seats", key=f"seat_{tid}_{trip_id}"):
                            with st.spinner("Loading..."):
                                seat_result = api.get_seat_layout(tid, trip_id, date_str, seat_type)
                            if seat_result["success"]:
                                st.json(seat_result["layout"])
                            else:
                                st.error(seat_result["message"])
            else:
                st.warning("No trains found")
        else:
            st.error(result["message"])
