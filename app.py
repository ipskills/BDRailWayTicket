"""
BD Railway Auto Seat Selector + Email Alerts (Streamlit UI).

Pages (via the sidebar radio -- this replaces the old `__name__`-based routing,
which never worked because __name__ is always "__main__"):
  * Website           -- the official site embedded in an iframe
  * Login             -- mobile + OTP, or paste a Bearer token
  * Search & Select   -- search trips, view availability, auto-reserve via API
  * Seat Alerts       -- start/stop the email monitor in a background thread
  * Console Script    -- the paste-into-DevTools auto-clicker (fallback)

Run:  streamlit run app.py
"""
import json
import threading
from datetime import datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components

from config import Config
from monitor import monitor_loop
from notifier import notifier_from_config
from railway_api import SEAT_TYPES, RailwayAPI

st.set_page_config(page_title="BD Railway Auto Seat Selector", page_icon="🚆", layout="wide")

# --------------------------------------------------------------------- state
if "api" not in st.session_state:
    st.session_state.api = RailwayAPI()
    st.session_state.api.handshake()
    # Auto-login from a token in .env if present.
    if Config.RAILWAY_AUTH_TOKEN:
        st.session_state.api.set_auth_token(Config.RAILWAY_AUTH_TOKEN)

api = st.session_state.api

_defaults = {
    "preferred": "11,12,13,14",
    "start_seat": 11,
    "num_seats": 4,
    "gauge": "meter",
    "mode": "priority",
    "click_mode": "burst",
    "burst_ms": 10,
    "delay_ms": 500,
    "retry_enabled": True,
    "max_retry": 5,
    "retry_delay": 3,
    "confirmed_seats": [],
    "search_results": [],
    "monitor_thread": None,
    "monitor_stop": None,
    "monitor_status": [],
    "monitor_lock": None,
    "dry_run": True,
}
for k, v in _defaults.items():
    st.session_state.setdefault(k, v)


def city_options():
    cities = api.cities or []
    names = [c.get("name") for c in cities if c.get("name")]
    ids = {c.get("name"): str(c.get("city_id")) for c in cities if c.get("name")}
    return names, ids


def resolve_recipient():
    """Recipient precedence: explicit config -> railway profile email.
    Cached in session_state so we don't hit the profile endpoint on every rerun
    (also avoids racing the monitor thread on the shared HTTP session)."""
    if Config.NOTIFY_EMAIL:
        return Config.NOTIFY_EMAIL, "config (NOTIFY_EMAIL)"
    if st.session_state.get("cached_recipient"):
        return st.session_state.cached_recipient, "railway profile"
    if api.is_logged_in:
        prof = api.get_profile()
        if prof.get("success"):
            email = RailwayAPI.extract_email(prof["profile"])
            if email:
                st.session_state.cached_recipient = email
                return email, "railway profile"
    return None, None


def _auto_select(api, seat_info):
    """Fetch layout, pick available seats, and reserve (or dry-run)."""
    n = st.session_state.num_seats
    with st.spinner("Fetching seat layout…"):
        layout = api.get_seat_layout(seat_info["trip_id"], seat_info["trip_route_id"])
    if not layout["success"]:
        st.error(f"Seat layout failed: {layout['message']}")
        return
    seats = RailwayAPI.extract_available_seats(layout["layout"])
    if not seats:
        st.warning("Layout loaded but no available seats parsed. "
                  "The layout schema may differ — check the Console Script fallback.")
        return

    # Honour the sidebar preference: try preferred seat numbers first.
    preferred = [x.strip() for x in st.session_state.preferred.split(",") if x.strip()]

    def _rank(seat):
        sn = str(seat.get("seat_number", ""))
        return preferred.index(sn) if sn in preferred else len(preferred)

    seats.sort(key=_rank)

    picked = seats[:n]
    st.write("Would reserve: " + ", ".join(str(s["seat_number"]) for s in picked))

    if st.session_state.dry_run:
        st.info("DRY-RUN is on (no real reservation made). Turn it off in the "
                "sidebar of the Search page to actually hold seats.")
        return

    with st.spinner("Reserving…"):
        result = api.reserve_seats(picked, seat_info["trip_route_id"], n)
    if result["success"]:
        nums = [str(s["seat_number"]) for s in result["reserved"]]
        st.session_state.confirmed_seats = nums
        st.success(f"Reserved {len(nums)} seat(s): {', '.join(nums)}. "
                  f"Finish payment on the Website tab within the hold window.")
    else:
        st.error("Could not reserve the requested number of seats.")
        for f in result["failed"]:
            st.caption(f"seat {f['seat'].get('seat_number')}: {f['error']}")


# ------------------------------------------------------------------- sidebar
with st.sidebar:
    st.title("🚆 BD Railway")
    st.caption("Auto seat selector + email alerts")
    st.divider()

    page = st.radio(
        "Page",
        ["Website", "Login", "Search & Select", "Seat Alerts", "Console Script"],
        label_visibility="collapsed",
    )

    st.divider()
    if api.is_logged_in:
        st.success("Logged in")
    else:
        st.warning("Not logged in")

    email_ok = Config.email_ready()
    st.caption(("✅ Gmail configured" if email_ok else "⚠️ Gmail not configured (.env)"))


# ==================================================================== WEBSITE
if page == "Website":
    st.title("Bangladesh Railway E-Ticket")
    st.caption("Official site embedded for reference. Booking/payment happens here.")
    components.html(
        '<iframe src="https://eticket.railway.gov.bd" '
        'style="width:100%;height:80vh;border:none;border-radius:8px;" '
        'allow="clipboard-read; clipboard-write"></iframe>',
        height=800,
        scrolling=False,
    )

# ===================================================================== LOGIN
elif page == "Login":
    st.title("Login")
    st.info(
        "The site uses a Cloudflare Turnstile challenge that can't be solved here. "
        "Two ways in:"
    )

    tab_token, tab_otp = st.tabs(["Paste Bearer token (easiest)", "Mobile + OTP"])

    with tab_token:
        st.markdown(
            "1. Log in normally at eticket.railway.gov.bd in your browser.\n"
            "2. Press **F12 → Network**, click any request, find the "
            "**Authorization: Bearer …** header.\n"
            "3. Copy everything after `Bearer ` and paste it below."
        )
        token = st.text_input("Bearer token", type="password",
                              value=Config.RAILWAY_AUTH_TOKEN or "")
        if st.button("Use token", type="primary"):
            api.set_auth_token(token.strip())
            prof = api.get_profile()
            if prof.get("success"):
                email = RailwayAPI.extract_email(prof["profile"]) or "(no email on profile)"
                st.success(f"Token accepted. Profile email: {email}")
            else:
                st.error(f"Token set, but profile check failed: {prof.get('message')}")

    with tab_otp:
        st.markdown(
            "Grab the Turnstile token: **F12 → Network → the `auth/sign-in` "
            "request → Payload → `cft_response`**, then paste it here."
        )
        mobile = st.text_input("Mobile", value=Config.RAILWAY_MOBILE or "", placeholder="01XXXXXXXXX")
        turnstile = st.text_input("Turnstile token (cft_response)", type="password")
        if st.button("Send OTP"):
            res = api.request_otp(mobile.strip(), turnstile.strip())
            (st.success if res["success"] else st.error)(res["message"])
        otp = st.text_input("OTP", placeholder="6-digit code")
        if st.button("Verify OTP", type="primary"):
            res = api.verify_otp(mobile.strip(), otp.strip())
            (st.success if res["success"] else st.error)(res["message"])

# =========================================================== SEARCH & SELECT
elif page == "Search & Select":
    st.title("Search & Auto-Select Seats")

    if not api.is_logged_in:
        st.warning("Please log in first (Login page).")
        st.stop()

    names, ids = city_options()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        from_city = st.selectbox("From", names, key="from_sel") if names else st.text_input("From city id")
    with c2:
        to_city = st.selectbox("To", names, key="to_sel") if names else st.text_input("To city id")
    with c3:
        travel_date = st.date_input("Date", value=datetime.now() + timedelta(days=1),
                                    min_value=datetime.now())
    with c4:
        seat_class = st.selectbox("Seat class", list(SEAT_TYPES.keys()), index=2)

    from_id = ids.get(from_city, from_city)
    to_id = ids.get(to_city, to_city)
    date_str = travel_date.strftime("%Y-%m-%d")
    seat_type = SEAT_TYPES[seat_class]

    with st.expander("Selection settings", expanded=True):
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            st.session_state.num_seats = st.number_input(
                "Seats to reserve", 1, 8, st.session_state.num_seats)
        with sc2:
            st.session_state.preferred = st.text_input(
                "Preferred seat numbers (optional, comma-separated)",
                value=st.session_state.preferred)
        with sc3:
            st.session_state.dry_run = st.checkbox(
                "Dry-run (don't actually reserve)", value=st.session_state.dry_run)
        if not st.session_state.dry_run:
            st.warning("Dry-run is OFF — clicking Auto-select will really hold seats "
                      "on your account. Finish or cancel payment promptly.")

    if st.button("Search trips", type="primary"):
        with st.spinner("Searching…"):
            res = api.search_trips(from_id, to_id, date_str, seat_type)
        if res["success"]:
            st.session_state.search_results = res["trains"]
            if not res["trains"]:
                st.warning("No trains found for that route/date.")
        else:
            st.error(res["message"])
            st.session_state.search_results = []

    for i, trip in enumerate(st.session_state.search_results):
        name = RailwayAPI.train_name(trip)
        seat_infos = RailwayAPI.seat_types_availability(trip)
        total_online = sum(s["online"] for s in seat_infos)
        with st.expander(f"{name} — {total_online} online seat(s)", expanded=(i == 0)):
            for s in seat_infos:
                cols = st.columns([2, 1, 1, 2])
                cols[0].write(f"**{s['type']}**")
                cols[1].write(f"Fare: {s['fare']}")
                cols[2].write(f"Online: **{s['online']}**")
                target = cols[3]
                key = f"sel_{i}_{s['type']}"
                if s["online"] > 0 and s.get("trip_id") and s.get("trip_route_id"):
                    if target.button("Auto-select", key=key):
                        _auto_select(api, s)
                else:
                    target.caption("—")

# ================================================================ SEAT ALERTS
elif page == "Seat Alerts":
    st.title("Seat Availability Email Alerts")

    if not Config.email_ready():
        st.error("Gmail isn't configured. Add GMAIL_ADDRESS and GMAIL_APP_PASSWORD "
                "to your .env file (see .env.example), then restart. Missing: "
                + ", ".join(Config.missing_email_fields()))
        st.stop()

    if not api.is_logged_in:
        st.warning("Log in first so the monitor can search trips.")
        st.stop()

    names, ids = city_options()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        a_from = st.selectbox("From", names, key="a_from") if names else st.text_input("From id", key="a_from_t")
    with c2:
        a_to = st.selectbox("To", names, key="a_to") if names else st.text_input("To id", key="a_to_t")
    with c3:
        a_date = st.date_input("Date", value=datetime.now() + timedelta(days=1),
                              min_value=datetime.now(), key="a_date")
    with c4:
        a_class = st.selectbox("Seat class", list(SEAT_TYPES.keys()), index=2, key="a_class")

    c5, c6, c7 = st.columns(3)
    with c5:
        a_train = st.text_input("Train filter (optional)", placeholder="e.g. SUBORNA")
    with c6:
        a_interval = st.number_input("Check every (seconds)", 20, 3600,
                                    Config.POLL_INTERVAL_SECONDS, step=10)
    with c7:
        a_realert = st.number_input("Re-alert every (min, 0=once)", 0, 720,
                                    Config.REALERT_MINUTES, step=5)

    recipient, source = resolve_recipient()
    if recipient:
        st.caption(f"Alerts will go to **{recipient}** (from {source}).")
    else:
        st.warning("No recipient email found. Set NOTIFY_EMAIL in .env, or make "
                  "sure your railway profile has an email.")

    running = (
        st.session_state.monitor_thread is not None
        and st.session_state.monitor_thread.is_alive()
    )

    col_start, col_stop = st.columns(2)
    with col_start:
        if st.button("▶ Start alerts", type="primary", disabled=running or not recipient):
            notifier = notifier_from_config(Config)
            test = notifier.test_connection()
            if not test["success"]:
                st.error(f"Gmail login failed: {test['message']}")
            else:
                from_id = ids.get(a_from, a_from)
                to_id = ids.get(a_to, a_to)

                def _city_name(cid):
                    for c in api.cities:
                        if str(c.get("city_id")) == str(cid):
                            return c.get("name", cid)
                    return cid

                params = {
                    "from_city": from_id, "to_city": to_id,
                    "from_name": _city_name(from_id), "to_name": _city_name(to_id),
                    "date": a_date.strftime("%Y-%m-%d"),
                    "seat_type": SEAT_TYPES[a_class], "seat_class": a_class,
                    "train_filter": a_train,
                }
                stop_event = threading.Event()
                status_list = st.session_state.monitor_status
                status_lock = threading.Lock()
                st.session_state.monitor_lock = status_lock

                def _status_cb(entry):
                    # Runs in the monitor thread; guard the shared list so the
                    # main thread can render it without a "changed size" error.
                    with status_lock:
                        status_list.insert(0, entry)
                        del status_list[25:]

                def _run():
                    monitor_loop(
                        api, notifier, recipient, params,
                        interval=int(a_interval),
                        realert_minutes=int(a_realert),
                        stop_event=stop_event,
                        status_cb=_status_cb,
                        logger=lambda *a: None,
                    )

                t = threading.Thread(target=_run, daemon=True)
                t.start()
                st.session_state.monitor_thread = t
                st.session_state.monitor_stop = stop_event
                st.success("Monitor started. Leave this app running.")
                st.rerun()
    with col_stop:
        if st.button("⏹ Stop", disabled=not running):
            if st.session_state.monitor_stop:
                st.session_state.monitor_stop.set()
            st.session_state.monitor_thread = None
            st.info("Stopping…")
            st.rerun()

    st.divider()
    if running:
        st.success("● Monitor is running.")
    else:
        st.caption("Monitor is stopped.")

    st.subheader("Recent checks")
    if st.button("Refresh log"):
        st.rerun()
    _lock = st.session_state.get("monitor_lock")
    if _lock:
        with _lock:
            _entries = list(st.session_state.monitor_status)
    else:
        _entries = list(st.session_state.monitor_status)
    if _entries:
        for e in _entries:
            if e.get("error"):
                st.error(f"{e['time']} — error: {e['error']}")
            else:
                summary = ", ".join(f"{m['train']}: {m['available']}" for m in e["matches"]) or "no matching trains"
                sent = e.get("alerts_sent") or []
                line = f"{e['time']} — {summary}"
                if sent:
                    st.success(line + f"  ✉️ emailed: {', '.join(sent)}")
                else:
                    st.write(line)
    else:
        st.caption("No checks yet.")

    st.info("Note: the in-app monitor runs only while this app is open. For an "
            "always-on watcher, run `python monitor.py` in a terminal (see README).")

# ============================================================ CONSOLE SCRIPT
elif page == "Console Script":
    st.title("Console Auto-Clicker (fallback)")
    st.caption("If the API reserve flow changes, this pastes into the site's "
              "DevTools console and clicks available seats fast.")

    max_seats = 60 if st.session_state.gauge == "meter" else 100
    c1, c2 = st.columns(2)
    with c1:
        g = st.radio("Gauge", ["Meter (1-60)", "Broad (1-100)"], horizontal=True)
        st.session_state.gauge = "meter" if "Meter" in g else "broad"
        m = st.radio("Mode", ["Priority", "Sequential"], horizontal=True)
        st.session_state.mode = m.lower()
    with c2:
        st.session_state.num_seats = st.number_input("Seats to book", 1, 8, st.session_state.num_seats)
        if st.session_state.mode == "priority":
            st.session_state.preferred = st.text_input("Preferred seats (comma-separated)",
                                                      value=st.session_state.preferred)
        else:
            st.session_state.start_seat = st.number_input("Start seat", 1, max_seats,
                                                        st.session_state.start_seat)

    def get_targeted_seats():
        mx = 60 if st.session_state.gauge == "meter" else 100
        if st.session_state.mode == "priority":
            return [int(x.strip()) for x in st.session_state.preferred.split(",")
                    if x.strip().isdigit() and 1 <= int(x.strip()) <= mx]
        s = st.session_state.start_seat
        return list(range(s, min(s + st.session_state.num_seats, mx + 1)))

    def build_click_js():
        preferred = get_targeted_seats()
        seq_from = "null" if st.session_state.mode == "priority" else str(st.session_state.start_seat)
        max_s = 60 if st.session_state.gauge == "meter" else 100
        need = st.session_state.num_seats
        js = (
            "(function(){"
            f"var need={need};var prList={json.dumps(preferred)};var seqFrom={seq_from};"
            f"var maxS={max_s};var gap=10;"
            "function getNum(b){var t=(b.getAttribute('title')||b.textContent||'').trim();"
            "var m=t.match(/\\d+/);return m?parseInt(m[0]):null;}"
            "function buildMap(){var map=new Map();"
            "document.querySelectorAll('button.btn-seat.seat-available').forEach(function(b){"
            "var n=getNum(b);if(n&&n>=1&&n<=maxS)map.set(n,b);});return map;}"
            "function fireClick(b){['mousedown','mouseup','click'].forEach(function(t){"
            "b.dispatchEvent(new MouseEvent(t,{view:window,bubbles:true,cancelable:true,buttons:1}));});}"
            "var initial=buildMap();"
            "if(!initial.size){alert('No available seats! Go to the seat selection page.');return;}"
            "var toClick=[];"
            "for(var i=0;i<prList.length&&toClick.length<need;i++){if(initial.has(prList[i]))toClick.push(prList[i]);}"
            "if(toClick.length<need){var from=(seqFrom!==null)?seqFrom:(prList.length?Math.max.apply(null,prList)+1:1);"
            "for(var n=from;n<=maxS&&toClick.length<need;n++){if(toClick.indexOf(n)<0&&initial.has(n))toClick.push(n);}}"
            "if(!toClick.length){alert('Target seats not available!');return;}"
            "var idx=0;function doNext(){if(idx>=toClick.length)return;"
            "var fresh=buildMap();var btn=fresh.get(toClick[idx]);if(btn)fireClick(btn);"
            "idx++;if(idx<toClick.length)setTimeout(doNext,gap);}doNext();"
            "setTimeout(function(){alert('Clicked: '+toClick.join(', '));},toClick.length*gap+500);"
            "})();"
        )
        return js

    js_code = build_click_js()
    st.warning("Copy the script, open the seat-selection page in the Website tab, "
              "press F12 → Console, paste, and press Enter.")
    st.code(js_code, language="javascript")
