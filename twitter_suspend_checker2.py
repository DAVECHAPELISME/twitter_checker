import os
import time
import threading
from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

app = Flask(__name__)

results = []
lock = threading.Lock()


def check_account_status(username, chrome_options, driver_path, auth_token):
    status = "Unknown"
    url = f"https://x.com/{username}"
    driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)

    try:
        driver.get("https://x.com")  # Load base page to set the cookie
        driver.add_cookie({"name": "auth_token", "value": auth_token, "domain": ".x.com"})
        driver.get(url)

        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.TAG_NAME, "body")))
        time.sleep(2)

        if "Enter the characters you see below" in driver.page_source:
            status = "Blocked by CAPTCHA"
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

    except Exception as e:
        status = f"Error: {str(e)}"
    finally:
        driver.quit()
    return {"username": username, "status": status}


@app.route("/check_status", methods=["POST"])
def check_status():
    data = request.get_json()
    usernames = data.get("usernames", [])
    auth_token = data.get("auth_token", None)

    if not usernames or not auth_token:
        return jsonify({"error": "Missing usernames or auth_token"}), 400

    driver_path = os.environ.get("CHROMEDRIVER_PATH", "./chromedriver.exe")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument('--log-level=3')

    output = []

    threads = []

    def thread_task(username):
        result = check_account_status(username, chrome_optio    ns, driver_path, auth_token)
        with lock:
            output.append(result)

    for username in usernames:
        t = threading.Thread(target=thread_task, args=(username,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return jsonify({"results": output})


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Twitter Status Checker API is running."})


if __name__ == "__main__":
    app.run(debug=True)
