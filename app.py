import streamlit as st
import streamlit.components.v1 as components
from railway_api import RailwayAPI
from datetime import datetime, timedelta
import json
import os
import threading
import time

st.set_page_config(page_title="BD Railway Auto Seat Selector", page_icon="train", layout="wide")

if "api" not in st.session_state:
    st.session_state.api = RailwayAPI()
    st.session_state.api.handshake()

api = st.session_state.api

defaults = {
    "phase": "main",
    "selected_seats": [],
    "current_train": None,
    "otp_sent": False,
    "turnstile_token": None,
    "confirmed_seats": [],
    "gauge": "meter",
    "mode": "priority",
    "preferred": "11,12,13,14",
    "start_seat": 11,
    "num_seats": 4,
    "click_mode": "burst",
    "burst_ms": 10,
    "delay_ms": 500,
    "retry_enabled": True,
    "max_retry": 5,
    "retry_delay": 3,
    "activity_log": [],
    "chrome_status": "closed",
    "chrome_url": "",
    "inject_result": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def log_activity(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.activity_log.append(f"[{ts}] {msg}")


def get_targeted_seats():
    max_s = 60 if st.session_state.gauge == "meter" else 100
    if st.session_state.mode == "priority":
        try:
            return [int(x.strip()) for x in st.session_state.preferred.split(",") if x.strip().isdigit() and 1 <= int(x.strip()) <= max_s]
        except Exception:
            return []
    else:
        st_val = st.session_state.start_seat
        return list(range(st_val, min(st_val + st.session_state.num_seats, max_s + 1)))


CLICK_JS = """
var result = { clicked: [], verified: [], mode: '', error: null };

try {
    var need = {need};
    var prList = {pr_list};
    var seqFrom = {seq_from};
    var maxS = {max_seats};
    var isBurst = {is_burst};
    var delayMs = {delay_ms};
    var burstMs = {burst_ms};

    function getNum(b) {{
        var t = (b.getAttribute('title') || b.textContent || '').trim();
        var m = t.match(/\\d+/);
        return m ? parseInt(m[0]) : null;
    }}

    function buildMap() {{
        var map = new Map();
        document.querySelectorAll('button.btn-seat.seat-available').forEach(function(b) {{
            var n = getNum(b);
            if (n && n >= 1 && n <= maxS) map.set(n, b);
        }});
        return map;
    }}

    function fireClick(b) {{
        ['mousedown', 'mouseup', 'click'].forEach(function(t) {{
            b.dispatchEvent(new MouseEvent(t, {{view: window, bubbles: true, cancelable: true, buttons: 1}}));
        }});
    }}

    var initial = buildMap();
    if (!initial.size) {{
        result.error = 'No available seats found. Make sure you are on the seat selection page.';
        return result;
    }}

    var toClick = [];
    for (var i = 0; i < prList.length && toClick.length < need; i++) {{
        if (initial.has(prList[i])) toClick.push(prList[i]);
    }}
    if (toClick.length < need) {{
        var from = (seqFrom !== null) ? seqFrom : (prList.length ? Math.max.apply(null, prList) + 1 : 1);
        for (var n = from; n <= maxS && toClick.length < need; n++) {{
            if (toClick.indexOf(n) < 0 && initial.has(n)) toClick.push(n);
        }}
    }}

    if (!toClick.length) {{
        result.error = 'Target seats not available!';
        return result;
    }}

    result.clicked = toClick;
    result.mode = isBurst ? 'micro-burst (' + burstMs + 'ms)' : 'sequential (' + delayMs + 'ms)';
    var gap = isBurst ? burstMs : delayMs;
    var idx = 0;

    function doNext() {{
        if (idx >= toClick.length) return;
        var fresh = buildMap();
        var btn = fresh.get(toClick[idx]);
        if (btn) fireClick(btn);
        idx++;
        if (idx < toClick.length) setTimeout(doNext, gap);
    }}

    doNext();
}} catch(e) {{
    result.error = e.toString();
}}

return result;
"""


VERIFY_JS = """
(function() {{
    var seats = [];
    var seen = new Set();
    var selectors = [
        'button.btn-seat.seat-selected',
        'button.btn-seat.selected',
        'button.btn-seat.active',
        'button.btn-seat.booked-by-user',
        'button.btn-seat[class*="selected"]',
        'button.btn-seat[class*="active"]'
    ];
    selectors.forEach(function(sel) {{
        try {{
            document.querySelectorAll(sel).forEach(function(b) {{
                if (seen.has(b)) return;
                seen.add(b);
                var t = (b.getAttribute('title') || b.textContent || '').trim();
                var m = t.match(/\\d+/);
                if (m) seats.push(parseInt(m[0]));
            }});
        }} catch(e) {{}}
    }});
    if (!seats.length) {{
        document.querySelectorAll('button.btn-seat').forEach(function(b) {{
            var cls = b.className || '';
            if (cls.indexOf('seat-available') < 0) {{
                var t = (b.getAttribute('title') || b.textContent || '').trim();
                var m = t.match(/\\d+/);
                if (m) seats.push(parseInt(m[0]));
            }}
        }});
    }}
    return {{ verified: seats.length, seats: seats }};
}})();
"""

GRID_JS = """
function buildSeatGrid(containerId, maxSeats, targetSeats, confirmedSeats) {
    var c = document.getElementById(containerId);
    if (!c) return;
    c.innerHTML = '';
    var cols = 10;
    var t = document.createElement('div');
    t.style.display = 'grid';
    t.style.gridTemplateColumns = 'repeat(' + cols + ', 1fr)';
    t.style.gap = '2px';
    t.style.padding = '4px';
    for (var s = 1; s <= maxSeats; s++) {
        var cell = document.createElement('div');
        cell.textContent = s;
        cell.style.textAlign = 'center';
        cell.style.padding = '4px';
        cell.style.borderRadius = '3px';
        cell.style.fontSize = '11px';
        cell.style.fontWeight = '600';
        if (confirmedSeats.indexOf(s) >= 0) {
            cell.style.backgroundColor = '#10b981'; cell.style.color = '#fff';
        } else if (targetSeats.indexOf(s) >= 0) {
            cell.style.backgroundColor = '#3b82f6'; cell.style.color = '#fff';
        } else {
            cell.style.backgroundColor = '#374151'; cell.style.color = '#9ca3af';
        }
        t.appendChild(cell);
    }
    c.appendChild(t);
}
"""

CHROME_DRIVERS = {}
CHROME_LOCK = threading.Lock()


def _launch_chrome(sid):
    try:
        import undetected_chromedriver as uc
        opts = uc.ChromeOptions()
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--start-maximized")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        driver = uc.Chrome(options=opts, headless=False)
        driver.get("https://eticket.railway.gov.bd/login")
        try:
            from selenium_stealth import stealth
            stealth(driver, languages=["en-US", "en"],
                    vendor="Google Inc.", platform="Win32",
                    webgl_vendor="Intel Inc.",
                    renderer="Intel Iris OpenGL Engine",
                    fix_hairline=True)
        except ImportError:
            pass
        with CHROME_LOCK:
            CHROME_DRIVERS[sid] = driver
        st.session_state.chrome_status = "ready"
        st.session_state.chrome_url = driver.current_url
        log_activity("Chrome launched - Railway website opened")
    except Exception as e:
        st.session_state.chrome_status = "error"
        st.session_state.inject_result = f"Launch failed: {e}"
        log_activity(f"Chrome launch failed: {e}")


def _get_driver():
    sid = st.session_state.get("_sid")
    with CHROME_LOCK:
        return CHROME_DRIVERS.get(sid)


def _close_chrome():
    sid = st.session_state.get("_sid")
    with CHROME_LOCK:
        drv = CHROME_DRIVERS.pop(sid, None)
    if drv:
        try:
            drv.quit()
        except Exception:
            pass
    st.session_state.chrome_status = "closed"
    st.session_state.confirmed_seats = []
    st.session_state.chrome_url = ""
    log_activity("Chrome closed")


if "_sid" not in st.session_state:
    st.session_state._sid = id(st.session_state)


def _do_inject():
    driver = _get_driver()
    if not driver:
        st.session_state.inject_result = "Chrome not running!"
        return

    preferred = get_targeted_seats()
    seq_from = "null" if st.session_state.mode == "priority" else st.session_state.start_seat
    max_seats = 60 if st.session_state.gauge == "meter" else 100
    is_burst = "true" if st.session_state.click_mode == "burst" else "false"

    js = CLICK_JS.format(
        need=st.session_state.num_seats,
        pr_list=json.dumps(preferred),
        seq_from=seq_from,
        max_seats=max_seats,
        is_burst=is_burst,
        delay_ms=st.session_state.delay_ms,
        burst_ms=st.session_state.burst_ms,
    )

    max_retry = st.session_state.max_retry if st.session_state.retry_enabled else 1
    need = st.session_state.num_seats
    retry_delay = st.session_state.retry_delay

    for attempt in range(1, max_retry + 1):
        try:
            click_result = driver.execute_script(js)
        except Exception as e:
            st.session_state.inject_result = f"Attempt {attempt}: JS error - {e}"
            log_activity(f"Attempt {attempt}: JS error - {e}")
            if attempt < max_retry:
                time.sleep(retry_delay)
                continue
            break

        if click_result and click_result.get("error"):
            st.session_state.inject_result = f"Attempt {attempt}: {click_result['error']}"
            log_activity(f"Attempt {attempt}: {click_result['error']}")
            if attempt < max_retry:
                time.sleep(retry_delay)
                continue
            break

        time.sleep(max(1, len(click_result.get("clicked", [])) * 0.02 + 1))

        try:
            verify = driver.execute_script(VERIFY_JS)
        except Exception:
            verify = {"verified": 0, "seats": []}

        verified = verify.get("verified", 0)
        seats = verify.get("seats", [])
        clicked = click_result.get("clicked", []) if click_result else []

        st.session_state.confirmed_seats = seats

        msg = f"Attempt {attempt}/{max_retry}: Clicked {clicked}, Verified {verified} seat(s): {seats}"
        log_activity(msg)

        if verified >= need:
            st.session_state.inject_result = f"SUCCESS! {verified} seats selected: {seats}"
            log_activity(f"SUCCESS! {verified} seats: {seats}")
            return
        else:
            if attempt < max_retry:
                log_activity(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                st.session_state.inject_result = f"{verified}/{need} seats after {max_retry} attempts: {seats}"


with st.sidebar:
    st.title("BD Railway")
    st.markdown("**Auto Seat Selector**")
    st.divider()

    nav = st.radio("Navigation", ["Website", "Search Trains", "All Trains"], label_visibility="collapsed")
    st.divider()

    st.subheader("GAUGE TYPE")
    gauge = st.radio("Gauge", ["Meter (1-60)", "Broad (1-100)"], horizontal=True, key="gauge_radio")
    st.session_state.gauge = "meter" if "Meter" in gauge else "broad"
    max_seats = 60 if st.session_state.gauge == "meter" else 100

    st.subheader("SELECTION MODE")
    mode = st.radio("Mode", ["Priority", "Sequential"], horizontal=True, key="mode_radio")
    st.session_state.mode = mode.lower()

    if st.session_state.mode == "priority":
        st.session_state.preferred = st.text_input("Preferred Seats (comma-separated)", value=st.session_state.preferred)
    else:
        st.session_state.start_seat = st.number_input("Start Seat (scans upward)", min_value=1, max_value=max_seats, value=st.session_state.start_seat)

    sc1, sc2 = st.columns(2)
    with sc1:
        st.session_state.num_seats = st.number_input("Seats to Book", min_value=1, max_value=8, value=st.session_state.num_seats)
    with sc2:
        if st.session_state.click_mode == "burst":
            st.session_state.burst_ms = st.slider("Burst Gap (ms)", 5, 100, st.session_state.burst_ms)
        else:
            st.session_state.delay_ms = st.slider("Click Delay (ms)", 100, 2000, st.session_state.delay_ms, step=50)

    st.subheader("CLICK MODE")
    click_mode = st.radio("Click", ["Micro-Burst (10ms)", "Sequential (N ms)"], horizontal=True, key="click_radio")
    st.session_state.click_mode = "burst" if "Micro" in click_mode else "sequential"

    st.subheader("AUTO-RETRY")
    st.session_state.retry_enabled = st.checkbox("Enable", value=st.session_state.retry_enabled)
    if st.session_state.retry_enabled:
        ar1, ar2 = st.columns(2)
        with ar1:
            st.session_state.max_retry = st.number_input("Attempts", 1, 20, st.session_state.max_retry)
        with ar2:
            st.session_state.retry_delay = st.number_input("Delay (s)", 1, 30, st.session_state.retry_delay)

    st.divider()

    targeted = get_targeted_seats()
    confirmed = st.session_state.confirmed_seats
    max_s = 60 if st.session_state.gauge == "meter" else 100

    grid_html = f"""
    <div style="background:#1a1d24;padding:6px;border-radius:8px;">
    <div id="sidebar-grid" style="min-height:40px;"></div>
    <div style="display:flex;gap:12px;padding:4px 8px;font-size:11px;color:#9ca3af;">
        <span><span style="display:inline-block;width:10px;height:10px;background:#10b981;border-radius:2px;vertical-align:middle;"></span> Verified</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#3b82f6;border-radius:2px;vertical-align:middle;"></span> Targeted</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#374151;border-radius:2px;vertical-align:middle;"></span> Available</span>
    </div>
    </div>
    <script>
    {GRID_JS}
    buildSeatGrid('sidebar-grid', {max_s}, {targeted}, {confirmed});
    </script>
    """
    st.components.v1.html(grid_html, height=160)

    st.write(f"**Verified:** {len(confirmed)} seat(s)")
    if confirmed:
        st.success(f"{', '.join(map(str, confirmed))}")

    st.divider()

    st.subheader("CHROME CONTROL")
    cs = st.session_state.chrome_status
    if cs == "closed":
        if st.button("Launch Chrome & Open Railway", type="primary", use_container_width=True):
            st.session_state.chrome_status = "launching"
            st.session_state.confirmed_seats = []
            st.session_state.inject_result = ""
            log_activity("Launching Chrome...")
            t = threading.Thread(target=_launch_chrome, args=(st.session_state._sid,), daemon=True)
            t.start()
            st.rerun()
    elif cs == "launching":
        st.info("Launching Chrome... please wait")
        st.rerun()
    elif cs == "ready":
        try:
            driver = _get_driver()
            if driver:
                st.session_state.chrome_url = driver.current_url
        except Exception:
            pass
        st.success("Chrome ready")
        st.caption(f"URL: {st.session_state.chrome_url}")

        if st.button("Inject Auto-Select", type="primary", use_container_width=True):
            log_activity("Injecting auto-select script...")
            with st.spinner("Clicking seats..."):
                _do_inject()
            st.rerun()

        if st.button("Close Chrome", use_container_width=True):
            _close_chrome()
            st.rerun()
    elif cs == "error":
        st.error(st.session_state.inject_result)
        if st.button("Retry Launch", type="primary", use_container_width=True):
            st.session_state.chrome_status = "launching"
            log_activity("Retrying Chrome launch...")
            t = threading.Thread(target=_launch_chrome, args=(st.session_state._sid,), daemon=True)
            t.start()
            st.rerun()
        if st.button("Dismiss", use_container_width=True):
            st.session_state.chrome_status = "closed"
            st.rerun()

    if st.session_state.inject_result:
        r = st.session_state.inject_result
        if "SUCCESS" in r:
            st.success(r)
        else:
            st.warning(r)

    st.divider()

    st.subheader("ACTIVITY LOG")
    log_text = "\n".join(st.session_state.activity_log[-15:]) if st.session_state.activity_log else "No activity yet."
    st.code(log_text, language=None)


if nav == "Website":
    cs = st.session_state.chrome_status
    if cs == "ready":
        st.title("Bangladesh Railway - Controlled by Auto Seat Selector")
        st.info("Chrome is open and controlled by this app. Use the sidebar to inject auto-select.")
        try:
            driver = _get_driver()
            if driver:
                st.session_state.chrome_url = driver.current_url
        except Exception:
            pass
        st.caption(f"Current page: {st.session_state.chrome_url}")
    else:
        st.title("Bangladesh Railway E-Ticket")
        st.info("Click **Launch Chrome & Open Railway** in the sidebar to start.")
        st.components.v1.html(
            '<iframe src="https://eticket.railway.gov.bd" '
            'style="width:100%;height:85vh;border:none;border-radius:8px;" '
            'allow="clipboard-read; clipboard-write"></iframe>',
            height=900,
            scrolling=False,
        )

elif nav == "Search Trains":
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

                    with st.expander(f"{number} - {name} | Seats: {avail}"):
                        cc1, cc2, cc3, cc4 = st.columns(4)
                        with cc1: st.write(f"**Depart:** {dep}")
                        with cc2: st.write(f"**Arrive:** {arr}")
                        with cc3: st.write(f"**Fare:** {fare} BDT")
                        with cc4: st.write(f"**Available:** {avail}")
            else:
                st.warning("No trains found")
        else:
            st.error(result["message"])

elif nav == "All Trains":
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
