from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import threading
import time
from queue import Queue

app = Flask(__name__)
lock = threading.Lock()


def check_account_status(queue, chrome_options, driver_path, auth_token, results):
    while not queue.empty():
        username = queue.get()
        url = f"https://x.com/{username}"
        driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)

        try:
            driver.get("https://x.com")
            driver.add_cookie({"name": "auth_token", "value": auth_token, "domain": ".x.com"})
            driver.get(url)

            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2)

            if "Enter the characters you see below" in driver.page_source:
                status = "CAPTCHA"
            elif "Account suspended" in driver.page_source:
                status = "Suspended"
            elif "This account is temporarily restricted" in driver.page_source:
                status = "Locked"
            else:
                try:
                    WebDriverWait(driver, 5).until(
                        EC.any_of(
                            EC.visibility_of_element_located((By.XPATH, "//img[contains(@src, 'profile_images')]")),
                            EC.visibility_of_element_located((By.XPATH, "//div[@data-testid='UserDescription']//span")),
                            EC.visibility_of_element_located((By.XPATH, "//a[contains(@href, '/followers')]"))
                        )
                    )
                    status = "Active"
                except (TimeoutException, NoSuchElementException):
                    status = "Unknown"

            with lock:
                results.append({"username": username, "status": status})
            print(f"{username}: {status}")

        except Exception as e:
            print(f"Error checking {username}: {e}")
            with lock:
                results.append({"username": username, "status": "Error"})
        finally:
            driver.quit()
            queue.task_done()


@app.route("/check_status", methods=["POST"])
def check_status():
    data = request.get_json()
    usernames = data.get("usernames", [])
    auth_token = data.get("auth_token", "")
    driver_path = "./chromedriver.exe"  # Ensure correct path on server

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument('--log-level=3')

    results = []
    queue = Queue()
    for username in usernames:
        queue.put(username)

    threads = []
    for _ in range(min(5, len(usernames))):
        t = threading.Thread(target=check_account_status, args=(queue, chrome_options, driver_path, auth_token, results))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True)
