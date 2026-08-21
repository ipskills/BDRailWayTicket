import requests


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
                self.auth_token = data.get("token") or data.get("data", {}).get("auth_token")
                if self.auth_token:
                    self.session.headers["Authorization"] = f"Bearer {self.auth_token}"
                return {"success": True, "message": "Login successful"}
            return {"success": False, "message": data.get("message", "Invalid OTP")}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def search_trips(self, from_city, to_city, date, seat_type=1):
        if not self.auth_token:
            return {"success": False, "message": "Not logged in"}
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/bookings/search-trips-v2",
                params={"from_city": from_city, "to_city": to_city, "date": date, "seat_type": seat_type},
                timeout=15,
            )
            data = resp.json()
            if resp.status_code == 200:
                trips = data.get("data", {}).get("trips", [])
                return {"success": True, "trains": trips}
            return {"success": False, "message": data.get("message", "Search failed")}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_seat_layout(self, train_id, trip_id, date, seat_type=1):
        if not self.auth_token:
            return {"success": False, "message": "Not logged in"}
        try:
            resp = self.session.post(
                f"{self.BASE_URL}/bookings/seat-layout",
                json={"train_id": train_id, "trip_id": trip_id, "date": date, "seat_type": seat_type},
                timeout=15,
            )
            data = resp.json()
            if resp.status_code == 200:
                return {"success": True, "layout": data.get("data", {})}
            return {"success": False, "message": data.get("message", "Failed")}
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

    def logout(self):
        self.auth_token = None
        self.session.headers.pop("Authorization", None)
