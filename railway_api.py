import time
import json
import logging

logger = logging.getLogger(__name__)
RAILWAY_URL = "https://eticket.railway.gov.bd"
API_URL = "https://railspaapi.shohoz.com/v1.0/web"


class RailwayAPI:
    def __init__(self):
        self.browser = None
        self.logged_in = False
        self.cities = []
        self.token = None

    def _start_browser(self):
        from DrissionPage import ChromiumPage, ChromiumOptions

        co = ChromiumOptions()
        co.headless()
        co.set_argument("--no-sandbox")
        co.set_argument("--disable-dev-shm-usage")
        co.set_argument("--disable-gpu")
        co.set_argument("--window-size=1920,1080")
        co.set_argument("--disable-blink-features=AutomationControlled")
        co.set_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

        page = ChromiumPage(co)
        return page

    def login(self, mobile, password):
        try:
            self.browser = self._start_browser()
            self.browser.get(f"{RAILWAY_URL}/login")
            time.sleep(5)

            mobile_el = self.browser.ele("css:input[type='text'], input[type='tel'], input[placeholder*='Mobile'], input[placeholder*='phone']")
            if mobile_el:
                mobile_el.clear()
                mobile_el.input(mobile)

            pass_el = self.browser.ele("css:input[type='password']")
            if pass_el:
                pass_el.clear()
                pass_el.input(password)

            time.sleep(1)

            btn = self.browser.ele("css:button[type='submit'], button.btn-primary")
            if btn:
                btn.click()

            time.sleep(8)

            url = self.browser.url
            if "login" not in url.lower():
                self.logged_in = True
                self._extract_token()
                self._load_cities()
                return {"success": True, "message": "Login successful"}

            errors = []
            try:
                for e in self.browser.eles("css:.error, .alert-danger, [class*='error'], .toast-message"):
                    t = e.text.strip()
                    if t:
                        errors.append(t)
            except Exception:
                pass

            return {"success": False, "message": " | ".join(errors) if errors else "Login failed. Check credentials."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _extract_token(self):
        try:
            js = """
            (function() {
                let keys = ['token', 'auth_token', 'accessToken', 'access_token'];
                for (let key of keys) {
                    let val = localStorage.getItem(key);
                    if (val) return val;
                }
                for (let i = 0; i < localStorage.length; i++) {
                    let key = localStorage.key(i);
                    let val = localStorage.getItem(key);
                    if (val && val.length > 50 && val.includes('.')) return val;
                }
                return null;
            })()
            """
            self.token = self.browser.run_js(js)
        except Exception:
            pass

    def _load_cities(self):
        try:
            self.browser.get(f"{RAILWAY_URL}/home")
            time.sleep(3)
            self.cities = []
            for sel in self.browser.eles("css:select"):
                for opt in sel.eles("tag:option"):
                    val = opt.attr("value")
                    txt = opt.text.strip()
                    if val and txt and len(txt) > 1 and txt.lower() not in ("select", "from", "to", "choose"):
                        self.cities.append({"name": txt, "code": val})
                if len(self.cities) > 5:
                    break
        except Exception:
            pass

    def _api_headers(self):
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Origin": "https://eticket.railway.gov.bd",
            "Referer": "https://eticket.railway.gov.bd/",
        }
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def search_trips(self, from_station, to_station, date):
        if not self.logged_in:
            return {"success": False, "message": "Not logged in"}

        if self.token:
            import requests
            try:
                resp = requests.get(
                    f"{API_URL}/bookings/search-trips-v2",
                    params={"from_city": from_station, "to_city": to_station, "date": date, "seat_type": 1},
                    headers=self._api_headers(),
                    timeout=15,
                )
                data = resp.json()
                if resp.status_code == 200:
                    trips = data.get("data", {}).get("trips", [])
                    if trips:
                        return {"success": True, "trains": trips}
            except Exception:
                pass

        try:
            self.browser.get(f"{RAILWAY_URL}/home")
            time.sleep(3)

            selects = self.browser.eles("css:select")
            if len(selects) >= 2:
                for opt in selects[0].eles("tag:option"):
                    if from_station.lower() in opt.text.lower():
                        selects[0].run_js(f"this.value='{opt.attr('value')}';this.dispatchEvent(new Event('change'))")
                        break
                time.sleep(1)
                for opt in selects[1].eles("tag:option"):
                    if to_station.lower() in opt.text.lower():
                        selects[1].run_js(f"this.value='{opt.attr('value')}';this.dispatchEvent(new Event('change'))")
                        break

            date_inputs = self.browser.eles("css:input[type='date']")
            if date_inputs:
                date_inputs[0].run_js(f"this.value='{date}';this.dispatchEvent(new Event('input'))")

            btns = self.browser.eles("css:button[type='submit'], button.btn-search")
            if btns:
                btns[0].click()

            time.sleep(5)

            trains = []
            for card in self.browser.eles("css:.train-list-item, .train-card, [class*='train'], .list-group-item, table tbody tr"):
                txt = card.text.strip()
                if txt:
                    lines = [l.strip() for l in txt.split("\n") if l.strip()]
                    trains.append({"name": lines[0], "info": " | ".join(lines[1:]) if len(lines) > 1 else "", "id": card.attr("data-id") or str(len(trains))})
            return {"success": True, "trains": trains}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_seats(self, train_id, date):
        if not self.logged_in:
            return {"success": False, "message": "Not logged in"}
        try:
            self.browser.get(f"{RAILWAY_URL}/seat-plan?train={train_id}&date={date}")
            time.sleep(5)

            result = {"coaches": []}
            for tab in self.browser.eles("css:[role='tab'], .nav-tab, .mat-tab-label"):
                name = tab.text.strip()
                if not name:
                    continue
                try:
                    tab.click()
                    time.sleep(2)
                except Exception:
                    pass

                coach = {"name": name, "blank": [], "booked": []}
                for seat in self.browser.eles("css:[class*='seat']"):
                    stxt = seat.text.strip()
                    scls = seat.attr("class") or ""
                    if stxt:
                        if "available" in scls or "blank" in scls or "free" in scls:
                            coach["blank"].append(stxt)
                        else:
                            coach["booked"].append(stxt)
                result["coaches"].append(coach)
            return {"success": True, "layout": result}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def close(self):
        if self.browser:
            try:
                self.browser.quit()
            except Exception:
                pass
            self.browser = None
            self.logged_in = False
