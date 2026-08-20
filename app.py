import streamlit as st
from railway_api import RailwayAPI
from datetime import datetime, timedelta

st.set_page_config(
    page_title="BD Railway E-Ticket",
    page_icon="train",
    layout="wide",
)

st.title("BD Railway E-Ticket Service")

if "api" not in st.session_state:
    st.session_state.api = RailwayAPI()
    st.session_state.api.handshake()

api = st.session_state.api

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.otp_sent = False
    st.session_state.mobile = ""

st.sidebar.title("Navigation")

if not st.session_state.logged_in:
    st.subheader("Login to Bangladesh Railway")

    mobile = st.text_input("Mobile Number", placeholder="01XXXXXXXXX", value=st.session_state.mobile)

    if not st.session_state.otp_sent:
        if st.button("Send OTP", use_container_width=True):
            if len(mobile) != 11 or not mobile.startswith("01"):
                st.error("Enter a valid 11-digit mobile number starting with 01")
            else:
                with st.spinner("Sending OTP..."):
                    result = api.request_otp(mobile)
                if result["success"]:
                    st.session_state.otp_sent = True
                    st.session_state.mobile = mobile
                    st.success(result["message"])
                    st.rerun()
                else:
                    st.error(result["message"])
    else:
        st.info(f"OTP sent to {mobile}")
        otp = st.text_input("Enter OTP", placeholder="6-digit code", max_chars=6)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Verify OTP", use_container_width=True):
                if len(otp) != 6:
                    st.error("Enter a valid 6-digit OTP")
                else:
                    with st.spinner("Verifying..."):
                        result = api.verify_otp(mobile, otp)
                    if result["success"]:
                        st.session_state.logged_in = True
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error(result["message"])
        with col2:
            if st.button("Resend OTP", use_container_width=True):
                with st.spinner("Resending..."):
                    result = api.request_otp(mobile)
                if result["success"]:
                    st.success("OTP resent!")
                else:
                    st.error(result["message"])

        if st.button("Back", use_container_width=True):
            st.session_state.otp_sent = False
            st.rerun()

else:
    st.success("Logged in to Bangladesh Railway")
    if st.sidebar.button("Logout from Railway"):
        api.auth_token = None
        st.session_state.logged_in = False
        st.session_state.otp_sent = False
        st.rerun()

    st.subheader("Search Trains")

    cities = api.cities
    city_names = [c.get("name", c.get("city_name", "")) for c in cities] if cities else []
    city_codes = [c.get("code", c.get("city_code", "")) for c in cities] if cities else []

    col1, col2, col3 = st.columns(3)

    with col1:
        if city_names:
            from_idx = st.selectbox("From Station", range(len(city_names)), format_func=lambda i: city_names[i])
            from_station = city_codes[from_idx] if city_codes else city_names[from_idx]
        else:
            from_station = st.text_input("From Station Code", placeholder="e.g., DHK")
            st.caption("Enter station code manually")

    with col2:
        if city_names:
            to_idx = st.selectbox("To Station", range(len(city_names)), format_func=lambda i: city_names[i])
            to_station = city_codes[to_idx] if city_codes else city_names[to_idx]
        else:
            to_station = st.text_input("To Station Code", placeholder="e.g., CTG")
            st.caption("Enter station code manually")

    with col3:
        tomorrow = datetime.now() + timedelta(days=1)
        travel_date = st.date_input("Travel Date", value=tomorrow, min_value=datetime.now())
        date_str = travel_date.strftime("%Y-%m-%d")

    seat_types = ["SHOVAN", "SHOVAN_CHAIR", "SNIGDHA", "TURNTA", "AC_SEAT", "AC_BERTH", "FIRST_CLASS"]
    seat_type = st.selectbox("Seat Type", seat_types)

    if st.button("Search Trains", use_container_width=True, type="primary"):
        with st.spinner("Searching for trains..."):
            result = api.search_trips(from_station, to_station, date_str, seat_type)

        if result["success"]:
            trains = result["trains"]
            if trains:
                st.subheader(f"Available Trains ({len(trains)} found)")

                for train in trains:
                    with st.expander(f"Train: {train.get('train_name', train.get('name', 'Unknown'))}"):
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.write(f"**Train No:** {train.get('train_number', train.get('number', 'N/A'))}")
                            st.write(f"**Train Name:** {train.get('train_name', train.get('name', 'N/A'))}")

                        with col2:
                            st.write(f"**Departure:** {train.get('departure_time', train.get('depart_time', 'N/A'))}")
                            st.write(f"**Arrival:** {train.get('arrival_time', train.get('arrive_time', 'N/A'))}")

                        with col3:
                            st.write(f"**Duration:** {train.get('duration', 'N/A')}")
                            st.write(f"**Available:** {train.get('available_seats', train.get('seats_available', 'N/A'))}")

                        fare = train.get("fare", train.get("ticket_price", "N/A"))
                        st.write(f"**Fare:** {fare} BDT")

                        if st.button(
                            "Check Seats",
                            key=f"seat_{train.get('train_id', train.get('id', ''))}_{train.get('trip_id', '')}",
                        ):
                            with st.spinner("Loading seat layout..."):
                                seat_result = api.get_seat_layout(
                                    str(train.get("train_id", train.get("id", ""))),
                                    str(train.get("trip_id", "")),
                                    date_str,
                                    seat_type,
                                )

                            if seat_result["success"]:
                                layout = seat_result["layout"]
                                st.json(layout)
                            else:
                                st.error(seat_result["message"])
            else:
                st.warning("No trains found for this route and date.")
        else:
            st.error(result["message"])

    st.divider()
    st.subheader("Quick Train List")

    with st.spinner("Loading train information..."):
        info_result = api.get_train_info()

    if info_result["success"] and info_result["trains"]:
        trains_info = info_result["trains"]
        st.write(f"Total trains in system: {len(trains_info)}")

        search_query = st.text_input("Search train by name or number", placeholder="e.g., SUBORNO, 701")
        if search_query:
            filtered = [
                t for t in trains_info
                if search_query.lower() in str(t.get("train_name", t.get("name", ""))).lower()
                or search_query in str(t.get("train_number", t.get("number", "")))
            ]
        else:
            filtered = trains_info[:20]

        if filtered:
            for t in filtered:
                st.write(
                    f"**{t.get('train_number', t.get('number', ''))}** - "
                    f"{t.get('train_name', t.get('name', ''))} | "
                    f"Route: {t.get('route', t.get('from_station', ''))} → {t.get('destination', t.get('to_station', ''))}"
                )
    elif not info_result["success"]:
        st.warning("Could not load train information.")

st.sidebar.divider()
st.sidebar.markdown("**BD Railway E-Ticket**")
st.sidebar.markdown("View train schedules and seat availability.")
st.sidebar.markdown("---")
st.sidebar.markdown("Powered by Bangladesh Railway API")
