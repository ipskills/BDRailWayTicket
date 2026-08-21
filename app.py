import streamlit as st
from railway_api import RailwayAPI
from datetime import datetime, timedelta

st.set_page_config(page_title="BD Railway E-Ticket", page_icon="train", layout="wide")

if "api" not in st.session_state:
    st.session_state.api = RailwayAPI()

api = st.session_state.api

if "phase" not in st.session_state:
    st.session_state.phase = "login"
if "selected_seats" not in st.session_state:
    st.session_state.selected_seats = []
if "current_train" not in st.session_state:
    st.session_state.current_train = None

phase = st.session_state.phase

st.markdown("""<style>
    [data-testid="stSidebar"] {background-color: #0e1117}
    .stButton>button {border-radius: 8px; font-weight: 600}
    .seat-btn {display:inline-block; padding:8px 12px; margin:3px; border-radius:6px; cursor:pointer; font-weight:bold; text-align:center; min-width:45px}
    .seat-blank {background:#1b5e20; color:white; border:2px solid #4caf50}
    .seat-booked {background:#b71c1c; color:white; border:2px solid #f44336}
    .seat-selected {background:#1565c0; color:white; border:2px solid #42a5f5}
</style>""", unsafe_allow_html=True)


if phase == "login":
    st.title("Bangladesh Railway E-Ticket")
    st.markdown("---")

    left, right = st.columns([1, 1])

    with left:
        st.subheader("Login")
        mobile = st.text_input("Mobile Number", placeholder="01XXXXXXXXX", max_chars=11)
        password = st.text_input("Password", type="password", placeholder="Enter password")

        if st.button("Login & Start", type="primary", use_container_width=True):
            if not mobile or not password:
                st.error("Enter mobile and password")
            elif len(mobile) != 11:
                st.error("Enter valid 11-digit mobile")
            else:
                with st.spinner("Opening browser and logging in..."):
                    result = api.login(mobile, password)
                if result["success"]:
                    st.session_state.phase = "dashboard"
                    st.rerun()
                else:
                    st.error(result["message"])

    with right:
        st.subheader("How it works")
        st.write("1. Enter your Railway phone & password")
        st.write("2. Browser opens and logs in automatically")
        st.write("3. Search trains, view blank seats")
        st.write("4. Select multiple seats with one click")
        st.info("Your credentials are used only to login to Bangladesh Railway website. They are not stored anywhere.")

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
            st.subheader(f"Selected Seats ({len(st.session_state.selected_seats)})")
            for seat in st.session_state.selected_seats:
                st.write(f"  {seat}")
            if st.button("Clear Selection", use_container_width=True):
                st.session_state.selected_seats = []
                st.rerun()
        if st.button("Logout", use_container_width=True):
            api.close()
            st.session_state.phase = "login"
            st.session_state.selected_seats = []
            st.rerun()

    st.title("Dashboard")
    st.info("Use the sidebar to navigate. Search trains and view blank seats.")

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
            st.subheader(f"Selected Seats ({len(st.session_state.selected_seats)})")
            for seat in st.session_state.selected_seats:
                st.write(f"  {seat}")
            st.write(f"**Total: {len(st.session_state.selected_seats)}**")
            if st.button("Clear Selection", use_container_width=True):
                st.session_state.selected_seats = []
                st.rerun()
        if st.button("Logout", use_container_width=True):
            api.close()
            st.session_state.phase = "login"
            st.session_state.selected_seats = []
            st.rerun()

    st.title("Search Trains")

    cities = api.cities
    city_names = [c["name"] for c in cities] if cities else []

    c1, c2, c3 = st.columns(3)
    with c1:
        from_station = st.selectbox("From", city_names, key="from_s") if city_names else st.text_input("From")
    with c2:
        to_station = st.selectbox("To", city_names, key="to_s") if city_names else st.text_input("To")
    with c3:
        tomorrow = datetime.now() + timedelta(days=1)
        travel_date = st.date_input("Date", value=tomorrow, min_value=datetime.now())
        date_str = travel_date.strftime("%Y-%m-%d")

    if st.button("Search", type="primary", use_container_width=True):
        with st.spinner("Searching trains..."):
            result = api.search_trips(from_station, to_station, date_str)
        if result["success"]:
            trains = result["trains"]
            if trains:
                st.subheader(f"Found {len(trains)} Train(s)")
                for train in trains:
                    with st.expander(train.get("name", "Train")):
                        st.write(train.get("info", ""))
                        if st.button("View Blank Seats", key=f"vs_{train.get('id','')}"):
                            st.session_state.current_train = {"id": train.get("id", ""), "name": train.get("name", ""), "date": date_str}
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

    with st.spinner("Loading seat layout..."):
        result = api.get_seats(train["id"], train["date"])

    if result["success"]:
        layout = result["layout"]
        for coach in layout.get("coaches", []):
            name = coach["name"]
            blank = coach.get("blank", [])
            booked = coach.get("booked", [])

            st.subheader(f"Coach: {name}")

            if blank:
                st.success(f"Blank Seats: {len(blank)}")
                cols = st.columns(min(len(blank), 10))
                for i, seat_no in enumerate(blank):
                    col = cols[i % len(cols)]
                    with col:
                        is_sel = seat_no in st.session_state.selected_seats
                        label = f"[X] {seat_no}" if is_sel else seat_no
                        if st.button(label, key=f"sel_{name}_{seat_no}", use_container_width=True):
                            if is_sel:
                                st.session_state.selected_seats.remove(seat_no)
                            else:
                                st.session_state.selected_seats.append(seat_no)
                            st.rerun()

            if booked:
                st.error(f"Booked Seats: {len(booked)} - {', '.join(booked[:30])}{'...' if len(booked) > 30 else ''}")
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
            api.close()
            st.session_state.phase = "login"
            st.rerun()

    st.title("All Trains on Route")

    with st.spinner("Loading trains..."):
        if api.cities:
            city_names = [c["name"] for c in api.cities]
            c1, c2 = st.columns(2)
            with c1:
                f_from = st.selectbox("From", city_names, key="af")
            with c2:
                f_to = st.selectbox("To", city_names, key="at")

            if st.button("Load Trains", type="primary", use_container_width=True):
                with st.spinner("Searching..."):
                    result = api.search_trips(f_from, f_to, datetime.now().strftime("%Y-%m-%d"))
                if result["success"] and result["trains"]:
                    for t in result["trains"]:
                        st.write(f"**{t.get('name', '')}** - {t.get('info', '')}")
                else:
                    st.info("No trains found on this route")
        else:
            st.warning("No station data available")
