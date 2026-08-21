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
if "token" not in st.session_state:
    st.session_state.token = ""

phase = st.session_state.phase

if phase == "landing":
    st.title("Bangladesh Railway E-Ticket")

    components.html(
        """
        <div style="text-align:center; padding:20px;">
            <h2 style="color:#1976d2;">Welcome to BD Railway E-Ticket</h2>
            <p style="font-size:16px; color:#555; margin-bottom:20px;">
                Login with your phone and password, then search trains
            </p>
        </div>
        """,
        height=120,
    )

    st.info("**Instructions:**\n1. Click **Login to Railway** below\n2. The Railway website loads on the right side\n3. Login with your phone and password\n4. After login, click **Extract My Token**\n5. Then search trains and view seats!")

    if st.button("Login to Railway", type="primary", use_container_width=True):
        st.session_state.phase = "login"
        st.rerun()

elif phase == "login":
    st.title("Bangladesh Railway Login")

    c1, c2 = st.columns([1, 1])

    with c1:
        st.subheader("Instructions")
        st.write("1. Login on the right side")
        st.write("2. Enter your phone and password")
        st.write("3. Click **Extract Token** after login")

        st.divider()

        token_input = st.text_area(
            "Or paste token manually (if auto-extract fails):",
            placeholder="eyJhbGciOiJIUzI1NiIs...",
            height=80,
        )

        if st.button("Use This Token", type="primary", use_container_width=True):
            if token_input.strip():
                with st.spinner("Verifying..."):
                    result = api.set_token(token_input.strip())
                if result["success"]:
                    st.session_state.token = token_input.strip()
                    st.session_state.phase = "dashboard"
                    st.rerun()
                else:
                    st.error(result["message"])

        if st.button("Back", use_container_width=True):
            st.session_state.phase = "landing"
            st.rerun()

    with c2:
        st.subheader("Railway Website")
        st.caption("Login here with phone and password:")

        components.html(
            """
            <iframe
                src="https://eticket.railway.gov.bd/login"
                style="width:100%; height:600px; border:2px solid #1976d2; border-radius:8px;"
                frameborder="0"
                allowfullscreen>
            </iframe>
            """,
            height=640,
        )

        st.caption("After login, copy token from browser: F12 -> Application -> Local Storage -> eticket.railway.gov.bd -> token")

elif phase == "dashboard":
    st.sidebar.title("BD Railway")
    st.sidebar.success("Logged In")
    if st.sidebar.button("Logout", use_container_width=True):
        api.logout()
        st.session_state.phase = "landing"
        st.session_state.token = ""
        st.rerun()
    if st.sidebar.button("Search Trains", use_container_width=True):
        st.session_state.phase = "search"
        st.rerun()

    st.title("Dashboard")

    st.subheader("All Trains (Public)")

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
                with st.expander(f"Train {t.get('train_number', '')} - {t.get('origin_city', '')} to {t.get('destination_city', '')}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write(f"**Number:** {t.get('train_number', '')}")
                    with c2:
                        st.write(f"**Zone:** {t.get('zone', '')}")
                    with c3:
                        st.write(f"**Opens:** {t.get('opening_time', '')}")
        else:
            st.info("No trains match filter")

elif phase == "search":
    st.sidebar.title("BD Railway")
    st.sidebar.success("Logged In")
    if st.sidebar.button("Dashboard", use_container_width=True):
        st.session_state.phase = "dashboard"
        st.rerun()
    if st.sidebar.button("Logout", use_container_width=True):
        api.logout()
        st.session_state.phase = "landing"
        st.session_state.token = ""
        st.rerun()

    st.title("Search Trains")

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

    st.divider()

    st.subheader("Railway Website")
    components.html(
        """
        <iframe
            src="https://eticket.railway.gov.bd/home"
            style="width:100%; height:500px; border:2px solid #1976d2; border-radius:8px;"
            frameborder="0">
        </iframe>
        """,
        height=540,
    )
