"""
Standalone seat-availability monitor for Bangladesh Railway.

Polls a route / date / seat-class and emails you (via Gmail) the moment seats
become bookable online. The same `monitor_loop` is imported by the Streamlit
app so the in-app "Start alerts" button runs identical logic in a thread.

AUTH
----
Searching requires a logged-in session. Two options:
  * Recommended: paste a Bearer token into RAILWAY_AUTH_TOKEN in .env (grab it
    from the site: F12 > Network > any request > Authorization header, drop the
    leading "Bearer "). Long-running friendly.
  * Or run with --login to sign in with mobile + OTP (you'll paste the
    Cloudflare Turnstile token from the browser; the OTP is texted to you).

EXAMPLES
--------
  python monitor.py --from Dhaka --to Chattogram --date 2026-09-01 \
      --seat-class SNIGDHA --train "SUBORNA EXPRESS"

  python monitor.py --from 1 --to 5 --date 2026-09-01 --seat-type 3 --login

Press Ctrl+C to stop.
"""
import argparse
import sys
import time
from datetime import datetime

from config import Config
from notifier import notifier_from_config
from railway_api import SEAT_TYPES, RailwayAPI


def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _interruptible_sleep(seconds, stop_event=None):
    """Sleep that wakes up promptly when stop_event is set."""
    end = time.time() + seconds
    while True:
        if stop_event is not None and stop_event.is_set():
            return
        remaining = end - time.time()
        if remaining <= 0:
            return
        time.sleep(min(1.0, remaining))


def _norm(s):
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def _class_matches(api_type, requested):
    """Loose match between the API's seat-type string and the class the user
    picked (their formats differ, e.g. 'S_CHAIR' vs 'SHOVAN_CHAIR')."""
    a, b = _norm(api_type), _norm(requested)
    if not a or not b:
        return False
    return a == b or a.startswith(b) or b.startswith(a) or a in b or b in a


def build_alert(train, available, params, class_exact=True):
    class_line = params["seat_class"] if class_exact else f"{params['seat_class']} (count is across all classes)"
    subject = f"[BD Railway] Seats available: {train} ({available})"
    text = (
        f"Seats are now available!\n\n"
        f"Train:      {train}\n"
        f"Route:      {params['from_name']} -> {params['to_name']}\n"
        f"Date:       {params['date']}\n"
        f"Seat class: {class_line}\n"
        f"Available:  {available} (online-bookable)\n\n"
        f"Book now: https://eticket.railway.gov.bd\n\n"
        f"(Detected {_ts()} by your monitor.)"
    )
    html = (
        f"<h2>Seats available!</h2>"
        f"<table cellpadding='6' style='border-collapse:collapse'>"
        f"<tr><td><b>Train</b></td><td>{train}</td></tr>"
        f"<tr><td><b>Route</b></td><td>{params['from_name']} &rarr; {params['to_name']}</td></tr>"
        f"<tr><td><b>Date</b></td><td>{params['date']}</td></tr>"
        f"<tr><td><b>Seat class</b></td><td>{class_line}</td></tr>"
        f"<tr><td><b>Available</b></td><td>{available} (online-bookable)</td></tr>"
        f"</table>"
        f"<p><a href='https://eticket.railway.gov.bd'>Book now &rarr;</a></p>"
        f"<p style='color:#888;font-size:12px'>Detected {_ts()}.</p>"
    )
    return subject, text, html


def run_once(api, params):
    """One availability check. Returns {ok, matches:[{train, available, class_exact}], error}."""
    res = api.search_trips(
        params["from_city"], params["to_city"], params["date"], params["seat_type"]
    )
    if not res.get("success"):
        return {"ok": False, "error": res.get("message"), "matches": []}
    matches = []
    train_filter = (params.get("train_filter") or "").lower()
    seat_class = params.get("seat_class", "")
    for trip in res.get("trains", []):
        name = RailwayAPI.train_name(trip)
        if train_filter and train_filter not in name.lower():
            continue
        infos = RailwayAPI.seat_types_availability(trip)
        # search-trips-v2 lists every class per trip, so narrow to the one the
        # user is watching; fall back to the whole trip if we can't match it.
        matched = [s for s in infos if _class_matches(s["type"], seat_class)]
        used = matched if matched else infos
        available = sum(s["online"] for s in used)
        matches.append({"train": name, "available": available, "class_exact": bool(matched)})
    return {"ok": True, "matches": matches, "error": None}


def monitor_loop(
    api,
    notifier,
    recipient,
    params,
    interval,
    realert_minutes=0,
    stop_event=None,
    status_cb=None,
    logger=print,
):
    """Poll until stop_event is set (or forever). Emails on the transition from
    'no seats' to 'seats available', and optionally re-alerts every
    realert_minutes while seats remain.
    """
    seen = {}  # train -> {"available": int, "last_alert": float}
    logger(f"[{_ts()}] Monitoring {params['from_name']} -> {params['to_name']} "
           f"on {params['date']} ({params['seat_class']}), every {interval}s.")

    while not (stop_event is not None and stop_event.is_set()):
        result = run_once(api, params)
        now = time.time()

        if not result["ok"]:
            msg = f"[{_ts()}] Search error: {result['error']}"
            logger(msg)
            if status_cb:
                status_cb({"time": _ts(), "error": result["error"], "matches": []})
            # Back off a little on errors so we don't spam a failing endpoint.
            _interruptible_sleep(max(interval, 30), stop_event)
            continue

        alerts_sent = []
        for m in result["matches"]:
            train, available = m["train"], m["available"]
            class_exact = m.get("class_exact", True)
            prev = seen.get(train)
            should_alert = False
            if available > 0:
                if prev is None or prev["available"] == 0:
                    should_alert = True  # just appeared
                elif realert_minutes and (now - prev["last_alert"]) >= realert_minutes * 60:
                    should_alert = True  # periodic reminder

            if should_alert and notifier and recipient:
                subject, text, html = build_alert(train, available, params, class_exact)
                send_res = notifier.send(recipient, subject, text, html)
                if send_res["success"]:
                    logger(f"[{_ts()}] ALERT emailed: {train} ({available} seats) -> {recipient}")
                    alerts_sent.append(train)
                    seen[train] = {"available": available, "last_alert": now}
                    continue
                else:
                    logger(f"[{_ts()}] Email FAILED for {train}: {send_res['message']}")

            # Update state (preserve last_alert if we didn't just alert).
            last_alert = prev["last_alert"] if prev else 0
            seen[train] = {"available": available, "last_alert": last_alert}

        summary = ", ".join(f"{m['train']}:{m['available']}" for m in result["matches"]) or "no matching trains"
        logger(f"[{_ts()}] {summary}")
        if status_cb:
            status_cb({
                "time": _ts(),
                "error": None,
                "matches": result["matches"],
                "alerts_sent": alerts_sent,
            })

        _interruptible_sleep(interval, stop_event)

    logger(f"[{_ts()}] Monitor stopped.")


def _resolve_params(api, args):
    from_city = api.find_city_id(args.from_city)
    to_city = api.find_city_id(args.to_city)
    if not from_city or not to_city:
        print("ERROR: could not resolve city names to IDs. Use numeric city IDs, "
              "or check spelling. (Handshake may have failed.)")
        sys.exit(2)

    if args.seat_type:
        seat_type = args.seat_type
        seat_class = next((k for k, v in SEAT_TYPES.items() if v == seat_type), str(seat_type))
    else:
        seat_class = (args.seat_class or "SNIGDHA").upper()
        if seat_class not in SEAT_TYPES:
            print(f"ERROR: unknown seat class '{seat_class}'. Options: {', '.join(SEAT_TYPES)}")
            sys.exit(2)
        seat_type = SEAT_TYPES[seat_class]

    def _city_name(cid):
        for c in api.cities:
            if str(c.get("city_id")) == str(cid):
                return c.get("name", cid)
        return cid

    return {
        "from_city": from_city,
        "to_city": to_city,
        "from_name": _city_name(from_city),
        "to_name": _city_name(to_city),
        "date": args.date,
        "seat_type": seat_type,
        "seat_class": seat_class,
        "train_filter": args.train,
    }


def _interactive_login(api):
    print("Interactive login. You'll need the Cloudflare Turnstile token from the "
          "browser (F12 > Network > sign-in request > payload 'cft_response').")
    mobile = input("Mobile (e.g. 01XXXXXXXXX): ").strip()
    turnstile = input("Turnstile token (cft_response): ").strip()
    res = api.request_otp(mobile, turnstile)
    if not res["success"]:
        print("Failed to request OTP:", res["message"])
        sys.exit(2)
    print(res["message"])
    otp = input("Enter OTP: ").strip()
    res = api.verify_otp(mobile, otp)
    if not res["success"]:
        print("Login failed:", res["message"])
        sys.exit(2)
    print("Logged in.")


def main():
    parser = argparse.ArgumentParser(description="BD Railway seat-availability email monitor")
    parser.add_argument("--from", dest="from_city", required=True, help="Origin city name or id")
    parser.add_argument("--to", dest="to_city", required=True, help="Destination city name or id")
    parser.add_argument("--date", required=True, help="Travel date YYYY-MM-DD")
    parser.add_argument("--seat-class", dest="seat_class", help="e.g. SNIGDHA, SHOVAN_CHAIR, AC_SEAT")
    parser.add_argument("--seat-type", dest="seat_type", type=int, help="Numeric seat_type (overrides --seat-class)")
    parser.add_argument("--train", help="Only alert for trains whose name contains this text")
    parser.add_argument("--interval", type=int, default=Config.POLL_INTERVAL_SECONDS,
                        help=f"Seconds between checks (default {Config.POLL_INTERVAL_SECONDS})")
    parser.add_argument("--realert-minutes", type=int, default=Config.REALERT_MINUTES,
                        help="Re-email every N minutes while seats stay available (0 = once)")
    parser.add_argument("--to-email", dest="to_email", help="Recipient (default: NOTIFY_EMAIL or your railway profile email)")
    parser.add_argument("--token", help="Bearer token (overrides RAILWAY_AUTH_TOKEN)")
    parser.add_argument("--login", action="store_true", help="Interactive mobile+OTP login instead of a token")
    args = parser.parse_args()

    if args.interval < 20:
        print("WARNING: interval < 20s is aggressive and may get you rate-limited. Continuing.")

    notifier = notifier_from_config(Config)
    if notifier is None:
        print("ERROR: Gmail not configured. Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD "
              "in .env (see .env.example). Missing:", ", ".join(Config.missing_email_fields()))
        sys.exit(2)
    test = notifier.test_connection()
    if not test["success"]:
        print("ERROR: Gmail login failed:", test["message"])
        sys.exit(2)
    print("Gmail SMTP: OK")

    api = RailwayAPI()
    api.handshake()

    token = args.token or Config.RAILWAY_AUTH_TOKEN
    if args.login:
        _interactive_login(api)
    elif token:
        api.set_auth_token(token)
    else:
        print("ERROR: no auth. Provide --token / RAILWAY_AUTH_TOKEN, or use --login.")
        sys.exit(2)

    params = _resolve_params(api, args)

    recipient = args.to_email or Config.NOTIFY_EMAIL
    if not recipient:
        prof = api.get_profile()
        if prof.get("success"):
            recipient = RailwayAPI.extract_email(prof["profile"])
    if not recipient:
        print("ERROR: no recipient email. Set NOTIFY_EMAIL, pass --to-email, or "
              "ensure your railway profile has an email.")
        sys.exit(2)
    print(f"Alerts will be sent to: {recipient}")

    try:
        monitor_loop(
            api, notifier, recipient, params,
            interval=args.interval,
            realert_minutes=args.realert_minutes,
        )
    except KeyboardInterrupt:
        print("\nStopped by user.")


if __name__ == "__main__":
    main()
