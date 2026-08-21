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

TOKEN_EXTRACT_HTML = """
<html><body>
<script>
window.addEventListener('message', function(event) {
    if (event.data && event.data.type === 'get-token') {
        try {
            let token = localStorage.getItem('token') || localStorage.getItem('auth_token');
            if (!token) {
                for (let i = 0; i < localStorage.length; i++) {
                    let key = localStorage.key(i);
                    let val = localStorage.getItem(key);
                    if (val && val.length > 50 && val.includes('.')) {
                        token = val;
                        break;
                    }
                }
            }
            if (token) {
                window.parent.postMessage({type: 'token-found', token: token}, '*');
                document.getElementById('status').innerText = 'Token found! Click Connect below.';
                document.getElementById('status').style.color = '#4CAF50';
            } else {
                document.getElementById('status').innerText = 'No token found. Login first on the Railway site.';
                document.getElementById('status').style.color = '#ff9800';
            }
        } catch(e) {
            document.getElementById('status').innerText = 'Error: ' + e.message;
        }
    }
});
</script>
<div id="status" style="padding:8px; color:#aaa; font-size:13px;">Waiting for token extraction...</div>
</body></html>
"""


def do_sidebar():
    st.sidebar.title("BD Railway")
    with st.sidebar:
        if st.session_state.selected_seats:
            st.subheader(f"Selected ({len(st.session_state.selected_seats)})")
            for seat in st.session_state.selected_seats:
                cols = st.columns([3, 1])
                cols[0].write(seat)
                if cols[1].button("X", key=f"rm_{seat}"):
                    st.session_state.selected_seats.remove(seat)
                    st.rerun()
            st.write(f"**Total: {len(st.session_state.selected_seats)} seats**")
            if st.button("Clear All", use_container_width=True):
                st.session_state.selected_seats = []
                st.rerun()
        else:
            st.info("No seats selected")


if phase == "landing":
    components.html(
        """<html><head><style>
            body{margin:0;font-family:Arial,sans-serif;background:#0e1117;color:white}
            .hero{background:linear-gradient(135deg,#1976d2,#0d47a1);text-align:center;padding:80px 20px;min-height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center}
            h1{font-size:52px;margin-bottom:10px}p{font-size:20px;opacity:0.9;margin-bottom:40px}
            .btn{padding:18px 60px;background:white;color:#0d47a1;border-radius:10px;font-size:22px;font-weight:bold;cursor:pointer;border:none;text-decoration:none;display:inline-block}
            .features{display:flex;gap:40px;margin-top:60px;flex-wrap:wrap;justify-content:center}
            .feat{background:rgba(255,255,255,0.1);padding:30px;border-radius:12px;width:220px;text-align:center}
            .feat h3{margin-bottom:10px;font-size:18px}.feat p{font-size:14px;opacity:0.8}
        </style></head><body>
            <div class="hero">
                <h1>Bangladesh Railway</h1>
                <p>E-Ticketing Service</p>
                <div class="features">
                    <div class="feat"><h3>Train Search</h3><p>Find all trains</p></div>
                    <div class="feat"><h3>Blank Seats</h3><p>See available seats</p></div>
                    <div class="feat"><h3>One-Click Select</h3><p>Select multiple seats</p></div>
                    <div class="feat"><h3>Auto Connect</h3><p>Login once, use all</p></div>
                </div>
            </div>
        </body></html>""",
        height=700,
    )
    if st.button("Get Started", type="primary", use_container_width=True):
        st.session_state.phase = "login"
        st.rerun()

elif phase == "login":
    do_sidebar()
    st.title("Login to Railway Website")

    c1, c2 = st.columns([2, 1])

    with c1:
        st.subheader("Step 1: Login Here")
        components.html(
            """<iframe
                src="https://eticket.railway.gov.bd/login"
                style="width:100%;height:700px;border:2px solid #1976d2;border-radius:12px;"
                frameborder="0" allowfullscreen>
            </iframe>""",
            height=740,
        )

    with c2:
        st.subheader("Step 2: Connect")

        st.write("**After login on the left:**")

        components.html(TOKEN_EXTRACT_HTML, height=50)

        st.write("**Click below to connect your Railway account:**")

        token = st.text_area("Your token (auto-filled after F12 method):", height=80, placeholder="Auto-extract or paste token...")

        if st.button("Auto-Detect Token from Railway Site", type="primary", use_container_width=True):
            components.html(
                """<html><body><script>
                    try {
                        let token = localStorage.getItem('token') || localStorage.getItem('auth_token');
                        if (!token) {
                            for (let i = 0; i < localStorage.length; i++) {
                                let key = localStorage.key(i);
                                let val = localStorage.getItem(key);
                                if (val && val.length > 50 && val.includes('.')) { token = val; break; }
                            }
                        }
                        if (token) {
                            window.parent.postMessage({type: 'token-result', token: token}, '*');
                        }
                    } catch(e) {}
                </script></body></html>""",
                height=0,
            )
            st.info("Check browser F12 -> Application -> Local Storage -> eticket.railway.gov.bd -> copy token value")

        if st.button("Connect & Enter Dashboard", type="primary", use_container_width=True):
            if token and token.strip():
                with st.spinner("Connecting..."):
                    result = api.set_token(token.strip())
                if result["success"]:
                    st.success("Connected!")
                    st.session_state.phase = "dashboard"
                    st.rerun()
                else:
                    st.error(result["message"])
            else:
                st.error("Enter your token. Get it from: F12 -> Application -> Local Storage -> eticket.railway.gov.bd -> token")

elif phase == "dashboard":
    do_sidebar()
    st.sidebar.divider()
    if st.sidebar.button("Search Trains", use_container_width=True):
        st.session_state.phase = "search"
        st.rerun()
    if st.sidebar.button("All Trains", use_container_width=True):
        st.session_state.phase = "alltrains"
        st.rerun()
    if st.sidebar.button("Home", use_container_width=True):
        st.session_state.phase = "landing"
        st.rerun()

    st.title("Dashboard")
    components.html(
        """<iframe src="https://eticket.railway.gov.bd/home"
            style="width:100%;height:700px;border:2px solid #1976d2;border-radius:12px;"
            frameborder="0" allowfullscreen></iframe>""",
        height=740,
    )

elif phase == "search":
    do_sidebar()
    st.sidebar.divider()
    if st.sidebar.button("Dashboard", use_container_width=True):
        st.session_state.phase = "dashboard"
        st.rerun()
    if st.sidebar.button("All Trains", use_container_width=True):
        st.session_state.phase = "alltrains"
        st.rerun()
    if st.sidebar.button("Home", use_container_width=True):
        st.session_state.phase = "landing"
        st.rerun()

    st.title("Search Trains")

    cities = api.cities
    city_names = [c.get("city_name", "") for c in cities] if cities else []

    c1, c2, c3 = st.columns(3)
    with c1:
        from_station = st.selectbox("From", city_names, key="from_s") if city_names else st.text_input("From")
    with c2:
        to_station = st.selectbox("To", city_names, key="to_s") if city_names else st.text_input("To")
    with c3:
        tomorrow = datetime.now() + timedelta(days=1)
        travel_date = st.date_input("Date", value=tomorrow, min_value=datetime.now())
        date_str = travel_date.strftime("%Y-%m-%d")

    seat_types = {"SHOVAN": 1, "SHOVAN_CHAIR": 2, "SNIGDHA": 3, "TURNTA": 4, "AC_SEAT": 5, "AC_BERTH": 6, "FIRST_CLASS": 7}
    seat_type_name = st.selectbox("Seat Class", list(seat_types.keys()))
    seat_type = seat_types[seat_type_name]

    if st.button("Search", type="primary", use_container_width=True):
        from_city = next((str(c.get("city_id", "")) for c in cities if c.get("city_name") == from_station), from_station)
        to_city = next((str(c.get("city_id", "")) for c in cities if c.get("city_name") == to_station), to_station)

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

                    with st.expander(f"{number} - {name} | Seats: {avail}"):
                        cc1, cc2, cc3, cc4 = st.columns(4)
                        with cc1: st.write(f"**Depart:** {dep}")
                        with cc2: st.write(f"**Arrive:** {arr}")
                        with cc3: st.write(f"**Fare:** {fare} BDT")
                        with cc4: st.write(f"**Available:** {avail}")

                        if st.button("View Blank Seats", key=f"v_{tid}_{trip_id}", type="primary"):
                            st.session_state.current_train = {"id": tid, "trip_id": trip_id, "name": name, "date": date_str, "seat_type": seat_type}
                            st.session_state.phase = "seats"
                            st.rerun()
            else:
                st.warning("No trains found")
        else:
            st.error(result["message"])

elif phase == "seats":
    do_sidebar()
    st.sidebar.divider()
    if st.sidebar.button("Back to Search", use_container_width=True):
        st.session_state.phase = "search"
        st.rerun()

    train = st.session_state.current_train
    st.title(f"Seats - {train['name']}")

    with st.spinner("Loading seats..."):
        result = api.get_seat_layout(train["id"], train["trip_id"], train["date"], train["seat_type"])

    if result["success"]:
        layout = result["layout"]
        if isinstance(layout, dict):
            for coach_name, coach_data in layout.items():
                if not isinstance(coach_data, dict):
                    continue
                seats = coach_data.get("seats", coach_data)
                blank = []
                booked = []
                if isinstance(seats, dict):
                    for seat_no, status in seats.items():
                        if isinstance(status, bool):
                            (blank if status else booked).append(seat_no)
                        elif isinstance(status, str):
                            (blank if status.lower() in ("available", "free", "blank", "0") else booked).append(seat_no)
                elif isinstance(seats, list):
                    for s in seats:
                        st_val = s.get("status")
                        s_no = s.get("seat_number", s.get("number", ""))
                        if st_val in ("available", "free", "blank", False, 0):
                            blank.append(s_no)
                        else:
                            booked.append(s_no)

                if blank or booked:
                    st.subheader(f"Coach: {coach_name}")
                    if blank:
                        st.success(f"Blank: {len(blank)} seats")
                        cols = st.columns(min(len(blank), 10))
                        for i, seat_no in enumerate(blank):
                            col = cols[i % len(cols)]
                            with col:
                                is_selected = seat_no in st.session_state.selected_seats
                                label = f"[X] {seat_no}" if is_selected else seat_no
                                if st.button(label, key=f"s_{coach_name}_{seat_no}", use_container_width=True):
                                    if is_selected:
                                        st.session_state.selected_seats.remove(seat_no)
                                    else:
                                        st.session_state.selected_seats.append(seat_no)
                                    st.rerun()
                    if booked:
                        st.error(f"Booked: {len(booked)} seats - {', '.join(booked[:20])}{'...' if len(booked)>20 else ''}")
        else:
            st.json(layout)
    else:
        st.error(result["message"])

elif phase == "alltrains":
    do_sidebar()
    st.sidebar.divider()
    if st.sidebar.button("Dashboard", use_container_width=True):
        st.session_state.phase = "dashboard"
        st.rerun()
    if st.sidebar.button("Search", use_container_width=True):
        st.session_state.phase = "search"
        st.rerun()
    if st.sidebar.button("Home", use_container_width=True):
        st.session_state.phase = "landing"
        st.rerun()

    st.title("All Trains")
    with st.spinner("Loading..."):
        result = api.get_all_trains()

    if result["success"]:
        trains = result["trains"]
        st.write(f"Total: {len(trains)} trains")

        c1, c2 = st.columns(2)
        with c1: f_from = st.text_input("Filter origin", placeholder="e.g. Dhaka")
        with c2: f_to = st.text_input("Filter destination", placeholder="e.g. Chattogram")

        filtered = trains
        if f_from: filtered = [t for t in filtered if f_from.lower() in t.get("origin_city", "").lower()]
        if f_to: filtered = [t for t in filtered if f_to.lower() in t.get("destination_city", "").lower()]

        for t in filtered:
            st.write(f"**Train {t.get('train_number', '')}** - {t.get('origin_city', '')} to {t.get('destination_city', '')} ({t.get('zone', '')})")
