import streamlit as st
import streamlit.components.v1 as components
from railway_api import RailwayAPI
from datetime import datetime, timedelta

st.set_page_config(page_title="BD Railway E-Ticket", page_icon="train", layout="wide", initial_sidebar_state="expanded")

if "api" not in st.session_state:
    st.session_state.api = RailwayAPI()
    st.session_state.api.handshake()

api = st.session_state.api

if "phase" not in st.session_state:
    st.session_state.phase = "landing"
if "selected_seats" not in st.session_state:
    st.session_state.selected_seats = []
if "current_train" not in st.session_state:
    st.session_state.current_train = None

phase = st.session_state.phase

if phase == "landing":
    components.html(
        """
        <html><head><style>
            body { margin:0; font-family:Arial,sans-serif; background:#0e1117; color:white; }
            .hero {
                background: linear-gradient(135deg, #1976d2, #0d47a1);
                text-align:center; padding:80px 20px; min-height:100vh;
                display:flex; flex-direction:column; justify-content:center; align-items:center;
            }
            h1 { font-size:52px; margin-bottom:10px; }
            p { font-size:20px; opacity:0.9; margin-bottom:40px; }
            .btn {
                display:inline-block; padding:18px 60px; background:white; color:#0d47a1;
                text-decoration:none; border-radius:10px; font-size:22px; font-weight:bold;
                cursor:pointer; border:none; transition:0.3s;
            }
            .btn:hover { background:#e3f2fd; transform:scale(1.05); }
            .features { display:flex; gap:40px; margin-top:60px; flex-wrap:wrap; justify-content:center; }
            .feat { background:rgba(255,255,255,0.1); padding:30px; border-radius:12px; width:220px; text-align:center; }
            .feat h3 { margin-bottom:10px; font-size:18px; }
            .feat p { font-size:14px; opacity:0.8; }
        </style></head><body>
            <div class="hero">
                <h1>Bangladesh Railway</h1>
                <p>E-Ticketing Service - Search Trains & Book Seats</p>
                <a href="https://eticket.railway.gov.bd" target="_blank" class="btn">Open Railway Website</a>
                <div class="features">
                    <div class="feat"><h3>Train Search</h3><p>Find all available trains</p></div>
                    <div class="feat"><h3>Blank Seats</h3><p>See available seats instantly</p></div>
                    <div class="feat"><h3>One-Click Select</h3><p>Select multiple seats quickly</p></div>
                    <div class="feat"><h3>Dark Mode</h3><p>Easy on your eyes</p></div>
                </div>
            </div>
        </body></html>
        """,
        height=800,
    )
    if st.button("Get Started", type="primary", use_container_width=True):
        st.session_state.phase = "login"
        st.rerun()

elif phase == "login":
    st.title("Login to Bangladesh Railway")

    components.html(
        """
        <iframe
            src="https://eticket.railway.gov.bd/login"
            style="width:100%; height:750px; border:2px solid #1976d2; border-radius:12px;"
            frameborder="0" allowfullscreen>
        </iframe>
        """,
        height=790,
    )

    st.info("**After login on the website above, click below to enter the dashboard**")

    if st.button("I Logged In - Enter Dashboard", type="primary", use_container_width=True):
        st.session_state.phase = "dashboard"
        st.rerun()

elif phase == "dashboard":
    st.sidebar.title("BD Railway")
    st.sidebar.success("Connected")

    with st.sidebar:
        st.subheader("Quick Actions")
        if st.button("Search Trains", use_container_width=True):
            st.session_state.phase = "search"
            st.rerun()
        if st.button("View All Trains", use_container_width=True):
            st.session_state.phase = "alltrains"
            st.rerun()
        if st.button("Back to Home", use_container_width=True):
            st.session_state.phase = "landing"
            st.rerun()

        st.divider()
        if st.session_state.selected_seats:
            st.subheader(f"Selected Seats ({len(st.session_state.selected_seats)})")
            for seat in st.session_state.selected_seats:
                st.write(f"- {seat}")
            if st.button("Clear Selection", use_container_width=True):
                st.session_state.selected_seats = []
                st.rerun()
            if st.button("Book Selected", type="primary", use_container_width=True):
                st.info("Booking will open on the Railway website")
        else:
            st.info("No seats selected yet")

    st.subheader("Railway Website")
    components.html(
        """
        <iframe
            src="https://eticket.railway.gov.bd/home"
            style="width:100%; height:700px; border:2px solid #1976d2; border-radius:12px;"
            frameborder="0" allowfullscreen>
        </iframe>
        """,
        height=740,
    )

elif phase == "search":
    st.sidebar.title("BD Railway")
    st.sidebar.success("Connected")

    with st.sidebar:
        st.subheader(f"Selected Seats ({len(st.session_state.selected_seats)})")
        if st.session_state.selected_seats:
            for seat in st.session_state.selected_seats:
                st.write(f"- {seat}")
            if st.button("Clear", use_container_width=True):
                st.session_state.selected_seats = []
                st.rerun()
        else:
            st.info("Click seats to select them")

        st.divider()
        if st.button("Dashboard", use_container_width=True):
            st.session_state.phase = "dashboard"
            st.rerun()
        if st.button("All Trains", use_container_width=True):
            st.session_state.phase = "alltrains"
            st.rerun()
        if st.button("Home", use_container_width=True):
            st.session_state.phase = "landing"
            st.rerun()

    st.title("Search Trains")

    c1, c2, c3 = st.columns(3)

    with c1:
        city_names = [c.get("city_name", "") for c in api.cities] if api.cities else []
        if city_names:
            from_idx = st.selectbox("From", city_names, key="from_station")
        else:
            from_idx = st.text_input("From Station")

    with c2:
        if city_names:
            to_idx = st.selectbox("To", city_names, key="to_station")
        else:
            to_idx = st.text_input("To Station")

    with c3:
        tomorrow = datetime.now() + timedelta(days=1)
        travel_date = st.date_input("Date", value=tomorrow, min_value=datetime.now())
        date_str = travel_date.strftime("%Y-%m-%d")

    seat_types = {"SHOVAN": 1, "SHOVAN_CHAIR": 2, "SNIGDHA": 3, "TURNTA": 4, "AC_SEAT": 5, "AC_BERTH": 6, "FIRST_CLASS": 7}
    seat_type_name = st.selectbox("Seat Class", list(seat_types.keys()))
    seat_type = seat_types[seat_type_name]

    if st.button("Search", type="primary", use_container_width=True):
        with st.spinner("Searching..."):
            from_city = next((str(c.get("city_id", "")) for c in api.cities if c.get("city_name") == from_idx), from_idx)
            to_city = next((str(c.get("city_id", "")) for c in api.cities if c.get("city_name") == to_idx), to_idx)
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

                    with st.expander(f"{number} - {name} | Available: {avail}"):
                        cc1, cc2, cc3, cc4 = st.columns(4)
                        with cc1:
                            st.write(f"**Departure:** {dep}")
                        with cc2:
                            st.write(f"**Arrival:** {arr}")
                        with cc3:
                            st.write(f"**Fare:** {fare} BDT")
                        with cc4:
                            st.write(f"**Seats:** {avail}")

                        if st.button("View Blank Seats", key=f"view_{tid}_{trip_id}", type="primary"):
                            st.session_state.current_train = {"id": tid, "trip_id": trip_id, "name": name, "date": date_str, "seat_type": seat_type}
                            st.session_state.phase = "seats"
                            st.rerun()
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
            style="width:100%; height:600px; border:2px solid #1976d2; border-radius:12px;"
            frameborder="0" allowfullscreen>
        </iframe>
        """,
        height=640,
    )

elif phase == "seats":
    train = st.session_state.current_train

    st.sidebar.title("BD Railway")

    with st.sidebar:
        st.subheader(f"Selected Seats ({len(st.session_state.selected_seats)})")
        if st.session_state.selected_seats:
            for seat in st.session_state.selected_seats:
                st.write(f"- {seat}")
            st.write(f"**Total:** {len(st.session_state.selected_seats)} seats")
            if st.button("Clear All", use_container_width=True):
                st.session_state.selected_seats = []
                st.rerun()
        else:
            st.info("Click seats below to select")

        st.divider()
        if st.button("Back to Search", use_container_width=True):
            st.session_state.phase = "search"
            st.rerun()

    st.title(f"Seats - {train['name']}")

    with st.spinner("Loading seat layout..."):
        result = api.get_seat_layout(train["id"], train["trip_id"], train["date"], train["seat_type"])

    if result["success"]:
        layout = result["layout"]

        if isinstance(layout, dict):
            for coach_name, coach_data in layout.items():
                if isinstance(coach_data, dict):
                    seats = coach_data.get("seats", coach_data)
                    if isinstance(seats, dict):
                        blank = []
                        booked = []
                        for seat_no, status in seats.items():
                            if isinstance(status, bool):
                                if status:
                                    blank.append(seat_no)
                                else:
                                    booked.append(seat_no)
                            elif isinstance(status, str):
                                if status.lower() in ("available", "free", "blank", "0"):
                                    blank.append(seat_no)
                                else:
                                    booked.append(seat_no)

                        if blank or booked:
                            st.subheader(f"Coach: {coach_name}")

                            if blank:
                                st.success(f"**Blank Seats: {len(blank)}**")

                                cols = st.columns(min(len(blank), 10))
                                for i, seat_no in enumerate(blank):
                                    col = cols[i % len(cols)]
                                    with col:
                                        if st.button(f"{seat_no}", key=f"sel_{coach_name}_{seat_no}"):
                                            if seat_no not in st.session_state.selected_seats:
                                                st.session_state.selected_seats.append(seat_no)
                                                st.rerun()
                                        if seat_no in st.session_state.selected_seats:
                                            st.caption("Selected")

                            if booked:
                                st.error(f"**Booked Seats: {len(booked)}**")

                    elif isinstance(seats, list):
                        blank = [s for s in seats if s.get("status") in ("available", "free", "blank", False, 0)]
                        booked = [s for s in seats if s.get("status") not in ("available", "free", "blank", False, 0)]

                        if blank or booked:
                            st.subheader(f"Coach: {coach_name}")
                            if blank:
                                st.success(f"**Blank Seats: {len(blank)}**")
                                cols = st.columns(min(len(blank), 10))
                                for i, s in enumerate(blank):
                                    seat_no = s.get("seat_number", s.get("number", f"S{i+1}"))
                                    col = cols[i % len(cols)]
                                    with col:
                                        if st.button(f"{seat_no}", key=f"sel_{coach_name}_{i}"):
                                            if seat_no not in st.session_state.selected_seats:
                                                st.session_state.selected_seats.append(seat_no)
                                                st.rerun()
                                        if seat_no in st.session_state.selected_seats:
                                            st.caption("Selected")
                            if booked:
                                st.error(f"**Booked Seats: {len(booked)}**")
        else:
            st.json(layout)
    else:
        st.error(result["message"])

elif phase == "alltrains":
    st.sidebar.title("BD Railway")
    with st.sidebar:
        if st.button("Dashboard", use_container_width=True):
            st.session_state.phase = "dashboard"
            st.rerun()
        if st.button("Search", use_container_width=True):
            st.session_state.phase = "search"
            st.rerun()
        if st.button("Home", use_container_width=True):
            st.session_state.phase = "landing"
            st.rerun()

    st.title("All Trains")

    with st.spinner("Loading..."):
        result = api.get_all_trains()

    if result["success"]:
        trains = result["trains"]
        st.write(f"Total trains: {len(trains)}")

        c1, c2 = st.columns(2)
        with c1:
            filter_from = st.text_input("Filter origin", placeholder="e.g. Dhaka")
        with c2:
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
