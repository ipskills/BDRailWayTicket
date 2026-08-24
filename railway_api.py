"""
Thin client for the Bangladesh Railway e-ticketing API (Shohoz backend).

This is an UNOFFICIAL, undocumented API. Endpoint paths, request methods, field
names and status codes can change without notice. The constants at the top of
`RailwayAPI` are the values most likely to drift -- if something stops working,
open eticket.railway.gov.bd in your browser, press F12 > Network, perform the
action manually, and compare the real request/response to what's here.

Authentication keeps a human in the loop on purpose: the login OTP and the
Cloudflare Turnstile challenge are solved by you, not bypassed here.
"""
import time

import requests

# Seat-class name -> API seat_type id. Shared by the app and the monitor.
SEAT_TYPES = {
    "SHOVAN": 1,
    "SHOVAN_CHAIR": 2,
    "SNIGDHA": 3,
    "TURNTA": 4,
    "AC_SEAT": 5,
    "AC_BERTH": 6,
    "FIRST_CLASS": 7,
}


class RailwayAPI:
    BASE_URL = "https://railspaapi.shohoz.com/v1.0/web"

    # --- Values that may drift; verify in DevTools > Network if things break ---
    # HTTP method used by reserve-seat / release-seat. Seen as both PATCH and
    # POST across deployments; flip this if you get HTTP 405 (Method Not Allowed).
    RESERVE_METHOD = "PATCH"
    # seat_availability code that means "bookable". Typically: 1 = available,
    # 2 = booked/sold, 3 = in-process/held.
    SEAT_AVAILABLE_CODE = 1

    HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Origin": "https://eticket.railway.gov.bd",
        "Referer": "https://eticket.railway.gov.bd/",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.auth_token = None
        self.cities = []

    # ------------------------------------------------------------------ auth
    def set_auth_token(self, token):
        """Use an existing Bearer token (e.g. copied from the browser)."""
        self.auth_token = token or None
        if self.auth_token:
            self.session.headers["Authorization"] = f"Bearer {self.auth_token}"
        else:
            self.session.headers.pop("Authorization", None)

    @property
    def is_logged_in(self):
        return bool(self.auth_token)

    def handshake(self):
        try:
            resp = self.session.post(f"{self.BASE_URL}/handshake", json={}, timeout=15)
            data = resp.json()
            if resp.status_code == 200:
                self.cities = data.get("data", {}).get("cities", [])
                return {"success": True, "count": len(self.cities)}
            return {"success": False, "message": "Connection failed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def request_otp(self, mobile, turnstile_token):
        try:
            resp = self.session.post(
                f"{self.BASE_URL}/auth/sign-in",
                json={"mobile": mobile, "cft_response": turnstile_token},
                timeout=15,
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("status") == "OK":
                return {"success": True, "message": f"OTP sent to {mobile}"}
            return {"success": False, "message": data.get("message", "Failed to send OTP")}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def verify_otp(self, mobile, otp):
        try:
            resp = self.session.post(
                f"{self.BASE_URL}/auth/validate-otp",
                json={"mobile": mobile, "otp": otp},
                timeout=15,
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("status") == "OK":
                token = data.get("token") or data.get("data", {}).get("auth_token")
                if token:
                    self.set_auth_token(token)
                return {"success": True, "message": "Login successful"}
            return {"success": False, "message": data.get("message", "Invalid OTP")}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def logout(self):
        self.set_auth_token(None)

    def get_profile(self):
        if not self.auth_token:
            return {"success": False, "message": "Not logged in"}
        try:
            resp = self.session.get(f"{self.BASE_URL}/auth/profile", timeout=15)
            data = resp.json()
            if resp.status_code == 200:
                return {"success": True, "profile": data.get("data", data)}
            return {"success": False, "message": data.get("message", "Failed")}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    def extract_email(profile):
        """Best-effort pull of the registered email out of a profile payload."""
        if not isinstance(profile, dict):
            return None
        for key in ("email", "user_email", "email_address"):
            if profile.get(key):
                return profile[key]
        user = profile.get("user")
        if isinstance(user, dict):
            for key in ("email", "user_email"):
                if user.get(key):
                    return user[key]
        return None

    # ---------------------------------------------------------------- search
    def find_city_id(self, value):
        """Resolve a city given either a numeric id or a (partial) name."""
        if value is None:
            return None
        text = str(value).strip()
        if text.isdigit():
            return text
        low = text.lower()
        for city in self.cities:
            if low == str(city.get("name", "")).lower():
                return str(city.get("city_id"))
        for city in self.cities:
            if low in str(city.get("name", "")).lower():
                return str(city.get("city_id"))
        return None

    def search_trips(self, from_city, to_city, date, seat_type=1):
        if not self.auth_token:
            return {"success": False, "message": "Not logged in"}
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/bookings/search-trips-v2",
                params={
                    "from_city": from_city,
                    "to_city": to_city,
                    "date": date,
                    "seat_type": seat_type,
                },
                timeout=20,
            )
            data = resp.json()
            if resp.status_code == 200:
                trips = data.get("data", {}).get("trips", [])
                return {"success": True, "trains": trips}
            return {"success": False, "message": data.get("message", f"HTTP {resp.status_code}"), "raw": data}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_all_trains(self):
        try:
            resp = self.session.get(f"{self.BASE_URL}/all-trains/info", timeout=15)
            data = resp.json()
            if resp.status_code == 200:
                return {"success": True, "trains": data.get("data", {}).get("trains", [])}
            return {"success": False, "message": "Failed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    def train_name(trip):
        return (
            trip.get("train_name")
            or trip.get("trip_number")
            or trip.get("name")
            or trip.get("train_number")
            or "Unknown"
        )

    @staticmethod
    def seat_types_availability(trip):
        """From a search-trips-v2 trip, return a list of:
        {type, trip_id, trip_route_id, fare, online, offline}
        'online' is the count you can book through the website.
        Defensive against schema differences.
        """
        out = []
        for stype in trip.get("seat_types", []) or []:
            counts = stype.get("seat_counts") or {}

            def _int(v):
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return 0

            online = _int(counts.get("online"))
            offline = _int(counts.get("offline"))
            # Fallbacks if seat_counts isn't shaped as expected.
            if online == 0 and offline == 0:
                for key in ("available_seats", "seat_count", "available", "online_seats"):
                    if stype.get(key) is not None:
                        online = _int(stype.get(key))
                        break
            out.append({
                "type": stype.get("type") or stype.get("seat_type") or "",
                "trip_id": stype.get("trip_id"),
                "trip_route_id": stype.get("trip_route_id"),
                "fare": stype.get("fare") or stype.get("ticket_price") or "",
                "online": online,
                "offline": offline,
            })
        return out

    @staticmethod
    def trip_online_available(trip):
        """Total online-bookable seats across all seat types of a trip."""
        return sum(s["online"] for s in RailwayAPI.seat_types_availability(trip))

    # ----------------------------------------------------------- seat layout
    def get_seat_layout(self, trip_id, trip_route_id):
        """Fetch the coach/seat map for a specific trip + route.
        trip_id and trip_route_id both come from a seat_type entry of a
        search-trips-v2 result.
        """
        if not self.auth_token:
            return {"success": False, "message": "Not logged in"}
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/bookings/seat-layout",
                params={"trip_id": trip_id, "trip_route_id": trip_route_id},
                timeout=20,
            )
            data = resp.json()
            if resp.status_code == 200:
                return {"success": True, "layout": data.get("data", {})}
            return {"success": False, "message": data.get("message", f"HTTP {resp.status_code}"), "raw": data}
        except Exception as e:
            return {"success": False, "message": str(e)}

    @classmethod
    def extract_available_seats(cls, layout_data, available_code=None):
        """Flatten a seat-layout payload into a list of available seats:
        [{seat_number, ticket_id, floor}, ...]
        """
        if available_code is None:
            available_code = cls.SEAT_AVAILABLE_CODE
        seats = []
        if not isinstance(layout_data, dict):
            return seats
        floors = layout_data.get("seatLayout") or layout_data.get("seat_layout") or []
        for floor in floors:
            if not isinstance(floor, dict):
                continue
            floor_name = floor.get("floor_name") or floor.get("name") or ""
            rows = floor.get("layout") or floor.get("seats") or []
            for row in rows:
                cells = row if isinstance(row, list) else [row]
                for cell in cells:
                    if not isinstance(cell, dict):
                        continue
                    avail = cell.get("seat_availability", cell.get("availability"))
                    if avail == available_code:
                        seats.append({
                            "seat_number": (
                                cell.get("seat_number")
                                or cell.get("seat_no")
                                or str(cell.get("ticket_id", ""))
                            ),
                            "ticket_id": cell.get("ticket_id") or cell.get("id"),
                            "floor": floor_name,
                        })
        return seats

    # -------------------------------------------------------------- reserve
    def _reserve_request(self, path, ticket_id, route_id):
        payload = {"ticket_id": ticket_id, "route_id": route_id}
        try:
            resp = self.session.request(
                self.RESERVE_METHOD,
                f"{self.BASE_URL}/{path}",
                json=payload,
                timeout=20,
            )
            try:
                data = resp.json()
            except ValueError:
                data = {}
            if resp.status_code in (200, 201):
                return {"success": True, "data": data.get("data", data)}
            return {
                "success": False,
                "message": data.get("message", f"HTTP {resp.status_code}"),
                "status_code": resp.status_code,
                "raw": data,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def reserve_seat(self, ticket_id, route_id):
        """Hold a single seat. route_id is the trip_route_id."""
        if not self.auth_token:
            return {"success": False, "message": "Not logged in"}
        return self._reserve_request("bookings/reserve-seat", ticket_id, route_id)

    def release_seat(self, ticket_id, route_id):
        """Release a previously held seat."""
        if not self.auth_token:
            return {"success": False, "message": "Not logged in"}
        return self._reserve_request("bookings/release-seat", ticket_id, route_id)

    def reserve_seats(self, seats, route_id, count, delay=0.3):
        """Try to reserve up to `count` seats from `seats` (list of dicts with a
        'ticket_id'). Stops once `count` succeed. Returns reserved + failed.
        """
        reserved, failed = [], []
        for seat in seats:
            if len(reserved) >= count:
                break
            res = self.reserve_seat(seat.get("ticket_id"), route_id)
            if res.get("success"):
                reserved.append(seat)
            else:
                failed.append({"seat": seat, "error": res.get("message")})
            time.sleep(delay)
        return {
            "success": len(reserved) >= count and count > 0,
            "reserved": reserved,
            "failed": failed,
        }
