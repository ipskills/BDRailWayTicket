import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)
RAILWAY_URL = "https://eticket.railway.gov.bd"


class RailwayAPI:
    def __init__(self):
        self.driver = None
        self.logged_in = False
        self.cities = []

    def _make_driver(self):
        opts = Options()
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
        svc = Service(ChromeDriverManager().install())
        drv = webdriver.Chrome(service=svc, options=opts)
        drv.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"})
        drv.implicitly_wait(5)
        return drv

    def login(self, mobile, password):
        try:
            self.driver = self._make_driver()
            self.driver.get(f"{RAILWAY_URL}/login")
            time.sleep(4)
            wait = WebDriverWait(self.driver, 20)

            mobile_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'],input[type='tel'],input[placeholder*='Mobile'],input[placeholder*='phone']")))
            mobile_el.clear()
            mobile_el.send_keys(mobile)

            pass_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']")))
            pass_el.clear()
            pass_el.send_keys(password)

            time.sleep(1)
            btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'],button.btn-primary")))
            btn.click()
            time.sleep(6)

            if "login" not in self.driver.current_url.lower():
                self.logged_in = True
                self._load_cities()
                return {"success": True, "message": "Login successful"}

            errors = []
            for e in self.driver.find_elements(By.CSS_SELECTOR, ".error,.alert-danger,[class*='error'],.toast-message"):
                t = e.text.strip()
                if t:
                    errors.append(t)
            return {"success": False, "message": " | ".join(errors) if errors else "Login failed. Check credentials."}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _load_cities(self):
        try:
            self.driver.get(f"{RAILWAY_URL}/home")
            time.sleep(3)
            self.cities = []
            for sel in self.driver.find_elements(By.CSS_SELECTOR, "select"):
                for opt in sel.find_elements(By.TAG_NAME, "option"):
                    val = opt.get_attribute("value")
                    txt = opt.text.strip()
                    if val and txt and len(txt) > 1 and txt.lower() not in ("select", "from", "to", "choose"):
                        self.cities.append({"name": txt, "code": val})
                if len(self.cities) > 5:
                    break
        except Exception:
            pass

    def search_trips(self, from_station, to_station, date):
        if not self.logged_in:
            return {"success": False, "message": "Not logged in"}
        try:
            self.driver.get(f"{RAILWAY_URL}/home")
            time.sleep(3)
            selects = self.driver.find_elements(By.CSS_SELECTOR, "select")
            if len(selects) >= 2:
                for opt in selects[0].find_elements(By.TAG_NAME, "option"):
                    if from_station.lower() in opt.text.lower():
                        self.driver.execute_script("arguments[0].value=arguments[1];arguments[0].dispatchEvent(new Event('change'))", selects[0], opt.get_attribute("value"))
                        break
                time.sleep(1)
                for opt in selects[1].find_elements(By.TAG_NAME, "option"):
                    if to_station.lower() in opt.text.lower():
                        self.driver.execute_script("arguments[0].value=arguments[1];arguments[0].dispatchEvent(new Event('change'))", selects[1], opt.get_attribute("value"))
                        break
            date_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='date']")
            if date_inputs:
                self.driver.execute_script("arguments[0].value=arguments[1];arguments[0].dispatchEvent(new Event('input'))", date_inputs[0], date)
            btns = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit'],button.btn-search")
            if btns:
                btns[0].click()
            time.sleep(5)
            trains = []
            for card in self.driver.find_elements(By.CSS_SELECTOR, ".train-list-item,.train-card,[class*='train'],.list-group-item,table tbody tr"):
                txt = card.text.strip()
                if txt:
                    lines = [l.strip() for l in txt.split("\n") if l.strip()]
                    trains.append({"name": lines[0], "info": " | ".join(lines[1:]) if len(lines) > 1 else "", "id": card.get_attribute("data-id") or str(len(trains))})
            return {"success": True, "trains": trains}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_seats(self, train_id, date):
        if not self.logged_in:
            return {"success": False, "message": "Not logged in"}
        try:
            self.driver.get(f"{RAILWAY_URL}/seat-plan?train={train_id}&date={date}")
            time.sleep(5)
            result = {"coaches": []}
            for tab in self.driver.find_elements(By.CSS_SELECTOR, "[role='tab'],.nav-tab,.mat-tab-label"):
                name = tab.text.strip()
                if not name:
                    continue
                try:
                    tab.click()
                    time.sleep(2)
                except Exception:
                    pass
                coach = {"name": name, "blank": [], "booked": []}
                for seat in self.driver.find_elements(By.CSS_SELECTOR, "[class*='seat']"):
                    stxt = seat.text.strip()
                    scls = seat.get_attribute("class") or ""
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
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            self.logged_in = False
