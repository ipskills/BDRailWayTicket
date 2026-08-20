import time
import json
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class RailwayAPI:
    SITE_URL = "https://eticket.railway.gov.bd"

    def __init__(self):
        self.driver = None
        self.logged_in = False
        self.cities = []

    def _get_driver(self):
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
        driver.implicitly_wait(10)
        return driver

    def login(self, mobile: str, password: str) -> dict:
        try:
            self.driver = self._get_driver()
            self.driver.get(f"{self.SITE_URL}/login")
            time.sleep(4)

            wait = WebDriverWait(self.driver, 20)

            mobile_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[type='tel'], input[placeholder*='Mobile'], input[placeholder*='phone']"))
            )
            mobile_input.clear()
            mobile_input.send_keys(mobile)

            pass_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
            )
            pass_input.clear()
            pass_input.send_keys(password)

            time.sleep(1)

            login_btn = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], button.btn-login, button.btn-primary"))
            )
            login_btn.click()

            time.sleep(6)

            current_url = self.driver.current_url

            if "login" not in current_url.lower():
                self.logged_in = True
                self._load_cities()
                return {"success": True, "message": "Login successful"}

            errors = []
            try:
                err_elements = self.driver.find_elements(By.CSS_SELECTOR, ".error, .alert-danger, .mat-error, [class*='error'], .toast-message")
                for e in err_elements:
                    txt = e.text.strip()
                    if txt:
                        errors.append(txt)
            except Exception:
                pass

            msg = " | ".join(errors) if errors else "Login failed. Check phone and password."
            return {"success": False, "message": msg}

        except Exception as e:
            logger.error(f"Login error: {e}")
            return {"success": False, "message": str(e)}

    def _load_cities(self):
        try:
            self.driver.get(f"{self.SITE_URL}/home")
            time.sleep(3)

            selects = self.driver.find_elements(By.CSS_SELECTOR, "select")
            for sel in selects:
                try:
                    options = sel.find_elements(By.TAG_NAME, "option")
                    for opt in options:
                        val = opt.get_attribute("value")
                        text = opt.text.strip()
                        if val and text and len(text) > 1:
                            self.cities.append({"code": val, "name": text})
                    if len(self.cities) > 3:
                        break
                except Exception:
                    continue
        except Exception:
            pass

    def search_trips(self, from_station: str, to_station: str, date: str) -> dict:
        if not self.logged_in or not self.driver:
            return {"success": False, "message": "Not logged in"}

        try:
            self.driver.get(f"{self.SITE_URL}/home")
            time.sleep(3)

            wait = WebDriverWait(self.driver, 15)

            selects = self.driver.find_elements(By.CSS_SELECTOR, "select")
            if len(selects) >= 2:
                from_sel = selects[0]
                to_sel = selects[1]

                from_options = from_sel.find_elements(By.TAG_NAME, "option")
                for opt in from_options:
                    if from_station.lower() in opt.text.lower() or opt.get_attribute("value") == from_station:
                        from_sel.find_element(By.CSS_SELECTOR, f"option[value='{opt.get_attribute('value')}']").click()
                        break

                time.sleep(1)

                to_options = to_sel.find_elements(By.TAG_NAME, "option")
                for opt in to_options:
                    if to_station.lower() in opt.text.lower() or opt.get_attribute("value") == to_station:
                        to_sel.find_element(By.CSS_SELECTOR, f"option[value='{opt.get_attribute('value')}']").click()
                        break

            date_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='date'], input[placeholder*='date']")
            if date_inputs:
                date_inputs[0].clear()
                date_inputs[0].send_keys(date)

            search_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], button.btn-search")
            if search_btns:
                search_btns[0].click()

            time.sleep(5)

            trains = self._parse_trains()
            return {"success": True, "trains": trains}

        except Exception as e:
            return {"success": False, "message": str(e)}

    def _parse_trains(self) -> list:
        trains = []
        try:
            cards = self.driver.find_elements(By.CSS_SELECTOR, ".train-list-item, .train-card, [class*='train'], table tbody tr, .list-group-item")

            for card in cards:
                try:
                    text = card.text.strip()
                    if not text:
                        continue

                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    if lines:
                        train = {
                            "name": lines[0],
                            "info": " | ".join(lines[1:]) if len(lines) > 1 else "",
                            "id": card.get_attribute("data-id") or card.get_attribute("id") or "",
                        }
                        trains.append(train)
                except Exception:
                    continue
        except Exception:
            pass

        return trains

    def get_seat_layout(self, train_id: str, date: str) -> dict:
        if not self.logged_in or not self.driver:
            return {"success": False, "message": "Not logged in"}

        try:
            url = f"{self.SITE_URL}/seat-plan/{train_id}?date={date}" if train_id else f"{self.SITE_URL}/seat-plan?date={date}"
            self.driver.get(url)
            time.sleep(5)

            result = {"classes": [], "seats": []}

            tabs = self.driver.find_elements(By.CSS_SELECTOR, "[role='tab'], .nav-tab, .mat-tab-label")
            for tab in tabs:
                name = tab.text.strip()
                if name:
                    result["classes"].append({"name": name, "available": True})

            seat_elements = self.driver.find_elements(By.CSS_SELECTOR, "[class*='seat']")
            for seat in seat_elements:
                try:
                    seat_text = seat.text.strip()
                    seat_class = seat.get_attribute("class") or ""
                    available = "available" in seat_class or "blank" in seat_class
                    if seat_text:
                        result["seats"].append({"number": seat_text, "available": available})
                except Exception:
                    continue

            return {"success": True, "layout": result}

        except Exception as e:
            return {"success": False, "message": str(e)}

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            self.logged_in = False
