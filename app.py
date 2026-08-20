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
        f"""
        <html>
        <head><style>
            body {{ margin:0; padding:0; font-family: Arial, sans-serif; }}
            .hero {{
                background: linear-gradient(135deg, #1976d2 0%, #0d47a1 100%);
                color: white; text-align: center; padding: 60px 20px;
                min-height: 100vh; display: flex; flex-direction: column;
                justify-content: center; align-items: center;
            }}
            h1 {{ font-size: 42px; margin-bottom: 10px; }}
            p {{ font-size: 18px; opacity: 0.9; margin-bottom: 30px; }}
            .url-box {{
                background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3);
                border-radius: 8px; padding: 12px 24px; font-size: 16px;
                color: white; margin-bottom: 30px; cursor: pointer;
            }}
            .url-box:hover {{ background: rgba(255,255,255,0.25); }}
            .btn {{
                display: inline-block; padding: 16px 50px; background: white;
                color: #1976d2; text-decoration: none; border-radius: 8px;
                font-size: 20px; font-weight: bold; cursor: pointer; border: none;
            }}
            .btn:hover {{ background: #e3f2fd; }}
        </style></head>
        <body>
            <div class="hero">
                <h1>Bangladesh Railway</h1>
                <p>E-Ticketing Service - Search Trains & View Seat Availability</p>
                <a href="https://eticket.railway.gov.bd" target="_blank" class="url-box">
                    eticket.railway.gov.bd
                </a>
                <br><br>
                <a href="https://eticket.railway.gov.bd/login" target="_blank" class="btn">
                    Open Railway Website
                </a>
            </div>
        </body>
        </html>
        """,
        height=700,
    )

    if st.button("Continue to App", type="primary", use_container_width=True):
        st.session_state.phase = "login"
        st.rerun()

elif phase == "login":
    st.subheader("Login to Bangladesh Railway")

    st.markdown(f"**Website:** [{api.SITE_URL}]({api.SITE_URL})")

    if "otp_sent" not in st.session_state:
        st.session_state.otp_sent = False

    if not st.session_state.otp_sent:
        mobile = st.text_input("Mobile Number", placeholder="01XXXXXXXXX", max_chars=11)

        if st.button("Send OTP", type="primary", use_container_width=True):
            if len(mobile) != 11 or not mobile.startswith("01"):
                st.error("Enter valid 11-digit mobile number (01XXXXXXXXX)")
            else:
                with st.spinner("Sending OTP..."):
                    result = api.request_otp(mobile)
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
                if len(otp) != 6:
                    st.error("Enter 6-digit OTP")
                else:
                    with st.spinner("Verifying..."):
                        result = api.verify_otp(mobile, otp)
                    if result["success"]:
                        st.session_state.phase = "dashboard"
                        del st.session_state.otp_sent
                        st.rerun()
                    else:
                        st.error(result["message"])
        with c2:
            if st.button("Resend OTP", use_container_width=True):
                with st.spinner("Resending..."):
                    api.request_otp(mobile)
                st.success("OTP resent!")

        if st.button("Back", use_container_width=True):
            st.session_state.otp_sent = False
            st.rerun()

elif phase == "dashboard":
    st.sidebar.title("BD Railway")
    st.sidebar.success("Logged In")
    if st.sidebar.button("Logout", use_container_width=True):
        api.logout()
        st.session_state.phase = "landing"
        st.rerun()

    st.subheader("Search Trains")

    cities = api.cities
    city_names = [c.get("name", c.get("city_name", "")) for c in cities] if cities else []
    city_codes = [c.get("code", c.get("city_code", "")) for c in cities] if cities else []

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

    seat_types = ["SHOVAN", "SHOVAN_CHAIR", "SNIGDHA", "TURNTA", "AC_SEAT", "AC_BERTH", "FIRST_CLASS"]
    seat_type = st.selectbox("Seat Class", seat_types)

    if st.button("Search", type="primary", use_container_width=True):
        with st.spinner("Searching trains..."):
            result = api.search_trips(from_station, to_station, date_str, seat_type)

        if result["success"]:
            trains = result["trains"]
            if trains:
                st.subheader(f"Found {len(trains)} Train(s)")

                for train in trains:
                    name = train.get("train_name", train.get("name", "Unknown"))
                    number = train.get("train_number", train.get("number", ""))
                    dep = train.get("departure_time", train.get("depart_time", ""))
                    arr = train.get("arrival_time", train.get("arrive_time", ""))
                    duration = train.get("duration", "")
                    avail = train.get("available_seats", train.get("seats_available", ""))
                    fare = train.get("fare", train.get("ticket_price", ""))
                    tid = train.get("train_id", train.get("id", ""))
                    trip_id = train.get("trip_id", "")

                    with st.expander(f"{number} - {name}", expanded=False):
                        cc1, cc2, cc3 = st.columns(3)
                        with cc1:
                            st.write(f"**Departure:** {dep}")
                            st.write(f"**Arrival:** {arr}")
                        with cc2:
                            st.write(f"**Duration:** {duration}")
                            st.write(f"**Fare:** {fare} BDT")
                        with cc3:
                            st.write(f"**Seats Available:** {avail}")

                        if st.button("View Blank Seats", key=f"btn_{tid}_{trip_id}"):
                            with st.spinner("Loading seat layout..."):
                                seat_result = api.get_seat_layout(str(tid), str(trip_id), date_str, seat_type)

                            if seat_result["success"]:
                                layout = seat_result["layout"]
                                st.write("**Seat Layout:**")

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
                                                if blank:
                                                    st.success(f"**{coach_name}** - Blank: {', '.join(blank[:30])}{'...' if len(blank)>30 else ''}")
                                                if booked:
                                                    st.error(f"**{coach_name}** - Booked: {len(booked)} seats")
                                            elif isinstance(seats, list):
                                                blank = [s for s in seats if s.get("status") in ("available", "free", "blank", False, 0)]
                                                booked = [s for s in seats if s.get("status") not in ("available", "free", "blank", False, 0)]
                                                if blank:
                                                    seat_nums = [s.get("seat_number", s.get("number", "?")) for s in blank]
                                                    st.success(f"**{coach_name}** - Blank: {', '.join(str(x) for x in seat_nums[:30])}")
                                                if booked:
                                                    st.error(f"**{coach_name}** - Booked: {len(booked)} seats")
                                elif isinstance(layout, list):
                                    blank = [s for s in layout if s.get("available", True)]
                                    st.success(f"**Blank Seats:** {len(blank)}")
                                else:
                                    st.json(layout)
                            else:
                                st.error(seat_result["message"])
            else:
                st.warning("No trains found for this route and date")
        else:
            st.error(result["message"])

    st.divider()

    with st.expander("Search All Trains"):
        search_q = st.text_input("Search by name or number", placeholder="e.g. SUBORNO or 701", key="search_all")
        if search_q:
            with st.spinner("Searching..."):
                result = api.search_trips(from_station, to_station, date_str, seat_type)
                if result["success"]:
                    filtered = [
                        t for t in result["trains"]
                        if search_q.lower() in str(t.get("train_name", t.get("name", ""))).lower()
                        or search_q in str(t.get("train_number", t.get("number", "")))
                    ]
                    if filtered:
                        for t in filtered:
                            st.write(f"**{t.get('train_number', t.get('number', ''))}** - {t.get('train_name', t.get('name', ''))}")
                    else:
                        st.info("No matching trains")
