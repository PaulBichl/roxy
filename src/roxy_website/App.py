import json
import subprocess

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

JSON_PATH = "config.json"
REMOTE_SERVER_URL = "192.168.1.112:5000"


def save_json(config) -> None:
    with open(JSON_PATH, "w") as f:
        json.dump(config, f, indent=4)


def load_json() -> dict:
    try:
        with open(JSON_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


@app.route("/")
def index() -> str:
    config = load_json()
    return render_template("index.html", config=config)


@app.route("/start", methods=["POST"])
def start() -> None:
    # Send JSON to remote server via HTTP PUT
    try:
        requests.put(REMOTE_SERVER_URL, start, timeout=5)
    except Exception as e:
        {"status": "FAILED", "error": str(e)}

    # return jsonify(result)


@app.route("/stop", methods=["POST"])
def stop() -> None:
    # Send JSON to remote server via HTTP PUT
    try:
        requests.put(REMOTE_SERVER_URL, stop, timeout=5)
    except Exception as e:
        {"status": "FAILED", "error": str(e)}


@app.route("/restart", methods=["POST"])
def restart():  # noqa: ANN201 -> Response, idk what this is
    curll_command = ["curl", "-X", "POST", f"http://{REMOTE_SERVER_URL}/restart_container"]
    try:
        subprocess.run(curll_command, check=True)
        result = {"status": "OK", "message": "Container restarted successfully."}
    except subprocess.CalledProcessError as e:
        result = {"status": "FAILED", "error": str(e)}
    return jsonify(result)


@app.route("/get_lock_state", methods=["GET"])
def get_lock_state():  # noqa: ANN201 -> Response, idk what this is
    curl_command = ["curl", "-X", "GET", f"http://{REMOTE_SERVER_URL}/get_lock_state"]
    try:
        response = subprocess.run(curl_command, check=True, capture_output=True, text=True)
        lock_state = response.stdout.strip()
        result = {"status": "OK", "lock_state": lock_state}
    except subprocess.CalledProcessError as e:
        result = {"status": "FAILED", "error": str(e)}
    return jsonify(result)


@app.route("/toggle_lock", methods=["POST"])
def toggle_lock():  # noqa: ANN201 -> Response, idk what this is
    curl_command = ["curl", "-X", "POST", f"http://{REMOTE_SERVER_URL}/toggle_lock"]
    try:
        subprocess.run(curl_command, check=True)
        result = {"status": "OK", "message": "Lock toggled successfully."}
    except subprocess.CalledProcessError as e:
        result = {"status": "FAILED", "error": str(e)}
    return jsonify(result)


@app.route("/update", methods=["POST"])
def update():  # noqa: ANN201 -> Response, idk what this is
    # Get values from form
    action = request.form.get("action")  # which button was pressed

    # Update local JSON
    config = {
        "Discord_webhook": request.form.get("Discord_webhook"),
        "conf_threshold": request.form.get("conf_threshold"),
        "lock_state": request.form.get("lock_state"),
        "lock_override": request.form.get("lock_override"),
        "last_action": action,
    }
    save_json(config)

    try:
        subprocess.run(
            [
                "scp",
                JSON_PATH,
                "p5@192.168.1.112:~/roxy/src/roxy/config.json",
            ],
            check=True,
        )
        print("config.json copied successfully.")
    except Exception as e:
        app.logger.error("Failed to copy config.json: %s", e)

    return jsonify({"status": "OK"})
    # return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)  # noqa: S104
