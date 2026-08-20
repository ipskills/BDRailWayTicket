import streamlit as st
import streamlit.components.v1 as components
from railway_api import RailwayAPI
from datetime import datetime, timedelta

st.set_page_config(page_title="BD Railway E-Ticket", page_icon="train", layout="wide")

if "api" not in st.session_state:
    st.session_state.api = RailwayAPI()

api = st.session_state.api

if "phase" not in st.session_state:
    st.session_state.phase = "landing"

phase = st.session_state.phase

if phase == "landing":
    components.html(
        """
        <html>
        <head><style>
            body { margin:0; padding:0; font-family: Arial, sans-serif; }
            .hero {
                background: linear-gradient(135deg, #1976d2 0%, #0d47a1 100%);
                color: white; text-align: center; padding: 60px 20px;
                min-height: 100vh; display: flex; flex-direction: column;
                justify-content: center; align-items: center;
            }
            h1 { font-size: 42px; margin-bottom: 10px; }
            p { font-size: 18px; opacity: 0.9; margin-bottom: 30px; }
            .url-box {
                background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3);
                border-radius: 8px; padding: 12px 24px; font-size: 16px;
                color: white; margin-bottom: 30px; cursor: pointer; text-decoration: none;
            }
            .url-box:hover { background: rgba(255,255,255,0.25); }
        </style></head>
        <body>
            <div class="hero">
                <h1>Bangladesh Railway</h1>
                <p>E-Ticketing Service - Search Trains & View Seat Availability</p>
                <a href="https://eticket.railway.gov.bd" target="_blank" class="url-box">
                    eticket.railway.gov.bd
                </a>
            </div>
        </body>
        </html>
        """,
        height=600,
    )

    if st.button("Continue to App", type="primary", use_container_width=True):
        st.session_state.phase = "login"
        st.rerun()

elif phase == "login":
    st.subheader("Login to Bangladesh Railway")
    st.caption("Enter your Railway website phone and password")

    if "login_error" not in st.session_state:
        st.session_state.login_error = ""

    if st.session_state.login_error:
        st.error(st.session_state.login_error)
        st.session_state.login_error = ""

    mobile = st.text_input("Phone Number", placeholder="01XXXXXXXXX", max_chars=11)
    password = st.text_input("Password", type="password", placeholder="Your Railway password")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Login", type="primary", use_container_width=True):
            if not mobile or not password:
                st.error("Enter phone and password")
            elif len(mobile) != 11:
                st.error("Enter valid 11-digit phone number")
            else:
                with st.spinner("Logging in to Bangladesh Railway..."):
                    result = api.login(mobile, password)
                if result["success"]:
                    st.session_state.phase = "dashboard"
                    st.rerun()
                else:
                    st.session_state.login_error = result["message"]
                    st.rerun()

    with c2:
        if st.button("Open Railway Website", use_container_width=True):
            components.html(
                '<script>window.open("https://eticket.railway.gov.bd/login", "_blank");</script>',
                height=0,
            )

    st.divider()
    st.info("Login with the same phone and password you use on eticket.railway.gov.bd")

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
    city_codes = [c.get("code", "") for c in cities] if cities else []

    c1, c2, c3 = st.columns(3)

    with c1:
        if city_names:
            from_idx = st.selectbox("From", range(len(city_names)), format_func=lambda i: city_names[i], key="from")
            from_station = city_codes[from_idx] if city_codes else city_names[from_idx]
        else:
            from_station = st.text_input("From Station", placeholder="e.g. DHK")

    with c2:
        if city_names:
            to_idx = st.selectbox("To", range(len(city_names)), format_func=lambda i: city_names[i], key="to")
            to_station = city_codes[to_idx] if city_codes else city_names[to_idx]
        else:
            to_station = st.text_input("To Station", placeholder="e.g. CTG")

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
                        st.write(train.get("info", "No details"))
                        st.write(f"**Route:** {from_station} -> {to_station}")
                        st.write(f"**Date:** {date_str}")

                        tid = train.get("id", "")
                        if tid and st.button("View Seats", key=f"seat_{tid}"):
                            with st.spinner("Loading seats..."):
                                seat_result = api.get_seat_layout(tid, date_str)
                            if seat_result["success"]:
                                layout = seat_result["layout"]

                                if layout.get("classes"):
                                    st.write("**Seat Classes:**")
                                    for cls in layout["classes"]:
                                        st.write(f"- {cls['name']}")

                                if layout.get("seats"):
                                    blank = [s for s in layout["seats"] if s["available"]]
                                    booked = [s for s in layout["seats"] if not s["available"]]
                                    if blank:
                                        st.success(f"**Blank Seats ({len(blank)}):** {', '.join(s['number'] for s in blank[:50])}")
                                    if booked:
                                        st.error(f"**Booked Seats ({len(booked)}):** {', '.join(s['number'] for s in booked[:20])}...")
                                else:
                                    st.json(layout)
                            else:
                                st.error(seat_result["message"])
            else:
                st.warning("No trains found")
        else:
            st.error(result["message"])

    st.divider()

    with st.expander("All Trains on Route"):
        if st.button("Load All Trains", key="load_all"):
            with st.spinner("Loading..."):
                result = api.search_trips(from_station, to_station, date_str)
                if result["success"] and result["trains"]:
                    for t in result["trains"]:
                        st.write(f"**{t.get('name', 'Unknown')}** - {t.get('info', '')}")
                else:
                    st.info("No trains found")
