import requests
import json
import time


class RailwayAPI:
    BASE_URL = "https://railspaapi.shohoz.com/v1.0/web"

    HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Origin": "https://eticket.railway.gov.bd",
        "Referer": "https://eticket.railway.gov.bd/",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.auth_token = None
        self.cities = []
        self.seat_types = []

    def handshake(self) -> dict:
        try:
            resp = self.session.post(f"{self.BASE_URL}/handshake", timeout=15)
            data = resp.json()

            if resp.status_code == 200:
                self.cities = data.get("cities", [])
                self.seat_types = data.get("seat_types", [])
                return {
                    "success": True,
                    "cities": self.cities,
                    "seat_types": self.seat_types,
                }
            return {"success": False, "message": "Handshake failed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def request_otp(self, mobile: str) -> dict:
        try:
            payload = {"mobile": mobile}
            resp = self.session.post(
                f"{self.BASE_URL}/auth/sign-in",
                json=payload,
                timeout=15,
            )
            data = resp.json()

            if resp.status_code == 200 and data.get("status") == "OK":
                return {"success": True, "message": "OTP sent to your mobile"}
            else:
                msg = data.get("message", data.get("msg", "Failed to send OTP"))
                return {"success": False, "message": msg}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def verify_otp(self, mobile: str, otp: str) -> dict:
        try:
            payload = {"mobile": mobile, "otp": otp}
            resp = self.session.post(
                f"{self.BASE_URL}/auth/validate-otp",
                json=payload,
                timeout=15,
            )
            data = resp.json()

            if resp.status_code == 200 and data.get("status") == "OK":
                self.auth_token = data.get("token") or data.get("data", {}).get("auth_token")
                if self.auth_token:
                    self.session.headers["Authorization"] = f"Bearer {self.auth_token}"
                return {"success": True, "message": "Login successful", "token": self.auth_token}
            else:
                msg = data.get("message", data.get("msg", "Invalid OTP"))
                return {"success": False, "message": msg}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def search_trips(self, from_city: str, to_city: str, date: str, seat_type: str = "SNIGDHA") -> dict:
        if not self.auth_token:
            return {"success": False, "message": "Not logged in"}

        try:
            payload = {
                "from_city": from_city,
                "to_city": to_city,
                "date": date,
                "seat_type": seat_type,
            }
            resp = self.session.post(
                f"{self.BASE_URL}/bookings/search-trips-v2",
                json=payload,
                timeout=15,
            )
            data = resp.json()

            if resp.status_code == 200:
                trips = data.get("trips", data.get("data", {}).get("trips", []))
                return {"success": True, "trains": trips}
            else:
                msg = data.get("message", "Search failed")
                return {"success": False, "message": msg}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_seat_layout(self, train_id: str, trip_id: str, date: str, seat_type: str = "SNIGDHA") -> dict:
        if not self.auth_token:
            return {"success": False, "message": "Not logged in"}

        try:
            payload = {
                "train_id": train_id,
                "trip_id": trip_id,
                "date": date,
                "seat_type": seat_type,
            }
            resp = self.session.post(
                f"{self.BASE_URL}/bookings/seat-layout",
                json=payload,
                timeout=15,
            )
            data = resp.json()

            if resp.status_code == 200:
                layout = data.get("seat_layout", data.get("data", {}))
                return {"success": True, "layout": layout}
            else:
                msg = data.get("message", "Failed to get seat layout")
                return {"success": False, "message": msg}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_train_info(self) -> dict:
        try:
            resp = self.session.get(f"{self.BASE_URL}/all-trains/info", timeout=15)
            data = resp.json()

            if resp.status_code == 200:
                trains = data.get("trains", data.get("data", []))
                return {"success": True, "trains": trains}
            return {"success": False, "message": "Failed to fetch train info"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def is_logged_in(self) -> bool:
        return self.auth_token is not None
