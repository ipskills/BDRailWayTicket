import streamlit as st
import streamlit.components.v1 as components
from railway_api import RailwayAPI
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="BD Railway E-Ticket", page_icon="train", layout="wide")

turnstile_component = components.declare_component("turnstile", path=os.path.join(os.path.dirname(__file__), "components"))

if "api" not in st.session_state:
    st.session_state.api = RailwayAPI()
    st.session_state.api.handshake()

api = st.session_state.api

if "phase" not in st.session_state:
    st.session_state.phase = "login"
if "selected_seats" not in st.session_state:
    st.session_state.selected_seats = []
if "current_train" not in st.session_state:
    st.session_state.current_train = None
if "otp_sent" not in st.session_state:
    st.session_state.otp_sent = False
if "turnstile_token" not in st.session_state:
    st.session_state.turnstile_token = None

st.markdown("""<style>
    [data-testid="stSidebar"] {background-color: #0e1117}
    .stButton>button {border-radius: 8px; font-weight: 600}
</style>""", unsafe_allow_html=True)

phase = st.session_state.phase

if phase == "login":
    st.title("Bangladesh Railway E-Ticket")
    st.markdown("---")

    left, right = st.columns([1, 1])

    with left:
        st.subheader("Login")

        if not st.session_state.otp_sent:
            mobile = st.text_input("Mobile Number", placeholder="01XXXXXXXXX", max_chars=11)

            st.write("**Human Verification:**")
            turnstile_token = turnstile_component(key="turnstile_login")

            if turnstile_token:
                st.session_state.turnstile_token = turnstile_token

            if st.session_state.turnstile_token:
                st.success("Verification complete")
            else:
                st.caption("Waiting for verification...")

            if st.button("Send OTP", type="primary", use_container_width=True):
                if not mobile or len(mobile) != 11:
                    st.error("Enter valid 11-digit mobile")
                elif not st.session_state.turnstile_token:
                    st.error("Please complete the human verification")
                else:
                    with st.spinner("Sending OTP..."):
                        result = api.request_otp(mobile, st.session_state.turnstile_token)
                    if result["success"]:
                        st.session_state.otp_sent = True
                        st.session_state.mobile = mobile
                        st.rerun()
                    else:
                        st.error(result["message"])

        else:
            mobile = st.session_state.mobile
            st.success(f"OTP sent to {mobile}")
            otp = st.text_input("Enter OTP Code", placeholder="6-digit code", max_chars=6)

            c1, c2 = st.columns(2)
            with c1:
                if st.button("Verify & Login", type="primary", use_container_width=True):
                    if not otp or len(otp) != 6:
                        st.error("Enter 6-digit OTP")
                    else:
                        with st.spinner("Verifying..."):
                            result = api.verify_otp(mobile, otp)
                        if result["success"]:
                            st.session_state.phase = "dashboard"
                            st.session_state.otp_sent = False
                            st.session_state.turnstile_token = None
                            st.rerun()
                        else:
                            st.error(result["message"])
            with c2:
                if st.button("Resend OTP", use_container_width=True):
                    st.session_state.turnstile_token = None
                    st.session_state.otp_sent = False
                    st.rerun()

            if st.button("Back", use_container_width=True):
                st.session_state.otp_sent = False
                st.session_state.turnstile_token = None
                st.rerun()

    with right:
        st.subheader("How it works")
        st.write("1. Enter your phone number")
        st.write("2. Complete the verification")
        st.write("3. Receive OTP on your phone")
        st.write("4. Enter OTP to login")
        st.write("5. Search trains & view blank seats")
        st.write("6. Select multiple seats with one click")

elif phase == "dashboard":
    with st.sidebar:
        st.title("BD Railway")
        st.success("Logged In")
        st.divider()
        nav = st.radio("Navigation", ["Dashboard", "Search Trains", "All Trains"], label_visibility="collapsed")
        if nav == "Search Trains":
            st.session_state.phase = "search"
            st.rerun()
        elif nav == "All Trains":
            st.session_state.phase = "alltrains"
            st.rerun()
        st.divider()
        if st.session_state.selected_seats:
            st.subheader(f"Selected ({len(st.session_state.selected_seats)})")
            for seat in st.session_state.selected_seats:
                st.write(f"  {seat}")
            if st.button("Clear", use_container_width=True):
                st.session_state.selected_seats = []
                st.rerun()
        if st.button("Logout", use_container_width=True):
            api.logout()
            st.session_state.phase = "login"
            st.session_state.selected_seats = []
            st.rerun()

    st.title("Dashboard")
    st.info("Use sidebar to navigate. Search trains and view blank seats.")

elif phase == "search":
    with st.sidebar:
        st.title("BD Railway")
        st.success("Logged In")
        st.divider()
        nav = st.radio("Navigation", ["Dashboard", "Search Trains", "All Trains"], index=1, label_visibility="collapsed")
        if nav == "Dashboard":
            st.session_state.phase = "dashboard"
            st.rerun()
        elif nav == "All Trains":
            st.session_state.phase = "alltrains"
            st.rerun()
        st.divider()
        if st.session_state.selected_seats:
            st.subheader(f"Selected ({len(st.session_state.selected_seats)})")
            for seat in st.session_state.selected_seats:
                st.write(f"  {seat}")
            if st.button("Clear", use_container_width=True):
                st.session_state.selected_seats = []
                st.rerun()
        if st.button("Logout", use_container_width=True):
            api.logout()
            st.session_state.phase = "login"
            st.session_state.selected_seats = []
            st.rerun()

    st.title("Search Trains")

    cities = api.cities
    city_names = [c["name"] for c in cities] if cities else []
    city_ids = [str(c["city_id"]) for c in cities] if cities else []

    c1, c2, c3 = st.columns(3)
    with c1:
        if city_names:
            from_idx = st.selectbox("From", city_names, key="from_s")
            from_city = city_ids[from_idx]
        else:
            from_city = st.text_input("From City ID")
    with c2:
        if city_names:
            to_idx = st.selectbox("To", city_names, key="to_s")
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
        with st.spinner("Searching trains..."):
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
                        if st.button("View Blank Seats", key=f"vs_{tid}_{trip_id}"):
                            st.session_state.current_train = {"id": tid, "name": name, "date": date_str, "seat_type": seat_type}
                            st.session_state.phase = "seats"
                            st.rerun()
            else:
                st.warning("No trains found")
        else:
            st.error(result["message"])

elif phase == "seats":
    train = st.session_state.current_train
    with st.sidebar:
        st.title("BD Railway")
        st.success("Logged In")
        st.divider()
        if st.button("Back to Search", use_container_width=True):
            st.session_state.phase = "search"
            st.rerun()
        st.divider()
        if st.session_state.selected_seats:
            st.subheader(f"Selected ({len(st.session_state.selected_seats)})")
            for seat in st.session_state.selected_seats:
                cols = st.columns([3, 1])
                cols[0].write(seat)
                if cols[1].button("X", key=f"rm_{seat}"):
                    st.session_state.selected_seats.remove(seat)
                    st.rerun()
            st.write(f"**Total: {len(st.session_state.selected_seats)}**")
            if st.button("Clear All", use_container_width=True):
                st.session_state.selected_seats = []
                st.rerun()

    st.title(f"Seats - {train['name']}")

    with st.spinner("Loading seats..."):
        result = api.get_seat_layout(train["id"], "", train["date"], train.get("seat_type", 1))

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
                                is_sel = seat_no in st.session_state.selected_seats
                                label = f"[X] {seat_no}" if is_sel else seat_no
                                if st.button(label, key=f"sel_{coach_name}_{seat_no}", use_container_width=True):
                                    if is_sel:
                                        st.session_state.selected_seats.remove(seat_no)
                                    else:
                                        st.session_state.selected_seats.append(seat_no)
                                    st.rerun()
                    if booked:
                        st.error(f"Booked: {len(booked)} - {', '.join(booked[:30])}{'...' if len(booked) > 30 else ''}")
        else:
            st.json(layout)
    else:
        st.error(result["message"])

elif phase == "alltrains":
    with st.sidebar:
        st.title("BD Railway")
        st.success("Logged In")
        st.divider()
        nav = st.radio("Navigation", ["Dashboard", "Search Trains", "All Trains"], index=2, label_visibility="collapsed")
        if nav == "Dashboard":
            st.session_state.phase = "dashboard"
            st.rerun()
        elif nav == "Search Trains":
            st.session_state.phase = "search"
            st.rerun()
        st.divider()
        if st.button("Logout", use_container_width=True):
            api.logout()
            st.session_state.phase = "login"
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
