import time
import json
import logging
import webbrowser
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
        self.trains = []

    def _get_driver(self):
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
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
        driver.implicitly_wait(5)
        return driver

    def start_browser(self):
        try:
            if self.driver:
                self.driver.quit()
            self.driver = self._get_driver()
            self.driver.get(f"{self.SITE_URL}/login")
            time.sleep(3)
        except Exception as e:
            logger.error(f"Browser start error: {e}")
            raise

    def check_login(self) -> dict:
        if not self.driver:
            return {"success": False, "message": "Browser not open. Click 'Open Railway Website' first."}

        try:
            current_url = self.driver.current_url

            if "login" not in current_url.lower():
                self.logged_in = True
                self._load_page_data()
                return {"success": True, "message": "Login detected!"}

            return {"success": False, "message": "Not logged in yet. Please login on the browser window."}

        except Exception as e:
            return {"success": False, "message": str(e)}

    def _load_page_data(self):
        try:
            self.driver.get(f"{self.SITE_URL}/home")
            time.sleep(3)

            self.cities = []
            selects = self.driver.find_elements(By.CSS_SELECTOR, "select")
            for sel in selects:
                try:
                    options = sel.find_elements(By.TAG_NAME, "option")
                    for opt in options:
                        val = opt.get_attribute("value")
                        text = opt.text.strip()
                        if val and text and len(text) > 1 and text.lower() not in ("select", "from", "to"):
                            self.cities.append({"name": text, "code": val})
                    if len(self.cities) > 5:
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
                for opt in selects[0].find_elements(By.TAG_NAME, "option"):
                    if from_station.lower() in opt.text.lower():
                        selects[0].find_element(By.CSS_SELECTOR, f"option[value='{opt.get_attribute('value')}']").click()
                        break
                time.sleep(1)

                for opt in selects[1].find_elements(By.TAG_NAME, "option"):
                    if to_station.lower() in opt.text.lower():
                        selects[1].find_element(By.CSS_SELECTOR, f"option[value='{opt.get_attribute('value')}']").click()
                        break

            date_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='date']")
            if date_inputs:
                date_inputs[0].clear()
                date_inputs[0].send_keys(date)

            search_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], button.btn-search")
            if search_btns:
                search_btns[0].click()

            time.sleep(5)

            self.trains = self._parse_trains()
            return {"success": True, "trains": self.trains}

        except Exception as e:
            return {"success": False, "message": str(e)}

    def _parse_trains(self) -> list:
        trains = []
        try:
            cards = self.driver.find_elements(By.CSS_SELECTOR, ".train-list-item, .train-card, [class*='train'], .list-group-item")
            for card in cards:
                try:
                    text = card.text.strip()
                    if text:
                        lines = [l.strip() for l in text.split("\n") if l.strip()]
                        trains.append({
                            "name": lines[0] if lines else "Unknown",
                            "info": " | ".join(lines[1:]) if len(lines) > 1 else "",
                            "id": card.get_attribute("data-id") or card.get_attribute("id") or str(len(trains)),
                        })
                except Exception:
                    continue
        except Exception:
            pass
        return trains

    def get_seat_layout(self, train_id: str, date: str) -> dict:
        if not self.logged_in or not self.driver:
            return {"success": False, "message": "Not logged in"}

        try:
            self.driver.get(f"{self.SITE_URL}/seat-plan?train={train_id}&date={date}")
            time.sleep(5)

            result = {"classes": [], "seats": []}

            tabs = self.driver.find_elements(By.CSS_SELECTOR, "[role='tab'], .nav-tab")
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

    def get_train_list(self) -> dict:
        if not self.driver:
            return {"success": False, "message": "Browser not open"}
        try:
            self.driver.get(f"{self.SITE_URL}/home")
            time.sleep(3)
            self.trains = self._parse_trains()
            return {"success": True, "trains": self.trains}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def open_url(self, url: str):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            self.logged_in = False
