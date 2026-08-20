import streamlit as st
import streamlit.components.v1 as components
from railway_api import RailwayAPI
from datetime import datetime, timedelta
import threading
import time

st.set_page_config(page_title="BD Railway E-Ticket", page_icon="train", layout="wide")

if "api" not in st.session_state:
    st.session_state.api = RailwayAPI()

api = st.session_state.api

if "phase" not in st.session_state:
    st.session_state.phase = "landing"

phase = st.session_state.phase

if phase == "landing":
    st.markdown("""
    <div style="text-align:center; padding:40px 0;">
        <h1 style="color:#1976d2;">Bangladesh Railway E-Ticket</h1>
        <p style="font-size:18px; color:#555;">Search Trains & View Seat Availability</p>
    </div>
    """, unsafe_allow_html=True)

    st.info("**How it works:**\n1. Click Start below\n2. Railway website opens in a browser\n3. Login with your phone and password\n4. Come back here - data loads automatically")

    if st.button("Start", type="primary", use_container_width=True):
        st.session_state.phase = "login"
        st.rerun()

elif phase == "login":
    st.subheader("Step 1: Login to Railway Website")
    st.info("A browser window will open. Login with your phone and password on the Railway website.")

    if "login_status" not in st.session_state:
        st.session_state.login_status = "not_started"
        st.session_state.browser_ready = False

    if st.session_state.login_status == "not_started":
        if st.button("Open Railway Website", type="primary", use_container_width=True):
            st.session_state.login_status = "opening"
            st.rerun()

    elif st.session_state.login_status == "opening":
        with st.spinner("Opening browser..."):
            api.start_browser()
            time.sleep(3)
        st.session_state.login_status = "opened"
        st.rerun()

    elif st.session_state.login_status == "opened":
        st.success("Browser opened! Please login on the Railway website.")
        st.write("After you login, click the button below.")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("I Logged In - Load My Data", type="primary", use_container_width=True):
                with st.spinner("Checking login..."):
                    result = api.check_login()
                if result["success"]:
                    st.session_state.phase = "dashboard"
                    st.rerun()
                else:
                    st.error(result["message"])
        with c2:
            if st.button("Cancel", use_container_width=True):
                api.close()
                st.session_state.login_status = "not_started"
                st.rerun()

elif phase == "dashboard":
    st.sidebar.title("BD Railway")
    st.sidebar.success("Logged In")
    if st.sidebar.button("Logout", use_container_width=True):
        api.close()
        st.session_state.phase = "landing"
        st.rerun()

    st.subheader("Search Trains")

    cities = api.cities
    city_names = [c.get("name", "") for c in cities] if cities else []

    c1, c2, c3 = st.columns(3)

    with c1:
        if city_names:
            from_station = st.selectbox("From", city_names, key="from")
        else:
            from_station = st.text_input("From Station")

    with c2:
        if city_names:
            to_station = st.selectbox("To", city_names, key="to")
        else:
            to_station = st.text_input("To Station")

    with c3:
        tomorrow = datetime.now() + timedelta(days=1)
        travel_date = st.date_input("Date", value=tomorrow, min_value=datetime.now())
        date_str = travel_date.strftime("%Y-%m-%d")

    if st.button("Search", type="primary", use_container_width=True):
        with st.spinner("Searching trains on the website..."):
            result = api.search_trips(from_station, to_station, date_str)

        if result["success"]:
            trains = result["trains"]
            if trains:
                st.subheader(f"Found {len(trains)} Train(s)")
                for train in trains:
                    name = train.get("name", "Unknown")
                    with st.expander(name):
                        st.write(train.get("info", ""))
                        if st.button("View Seats", key=f"seat_{train.get('id','')}"):
                            with st.spinner("Loading seat layout..."):
                                seat_result = api.get_seat_layout(train.get("id",""), date_str)
                            if seat_result["success"]:
                                st.json(seat_result["layout"])
                            else:
                                st.error(seat_result["message"])
            else:
                st.warning("No trains found")
        else:
            st.error(result["message"])

    st.divider()
    st.subheader("Open Railway Website in Browser")
    if st.button("Open Website", use_container_width=True):
        api.open_url("https://eticket.railway.gov.bd")

    if st.button("Show All Trains", use_container_width=True):
        with st.spinner("Loading..."):
            result = api.get_train_list()
        if result["success"]:
            for t in result["trains"]:
                st.write(f"**{t.get('name', '')}** - {t.get('info', '')}")
