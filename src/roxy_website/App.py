import json  # For reading/writing JSON config files
import subprocess  # For running system shell commands (like curl)

import requests
from flask import (  # Flask web framework and helpers for web, templates, ajax/json
    Flask,
    jsonify,
    render_template,
    request,
)

app = Flask(__name__)  # Initialize the Flask app

JSON_PATH = "config.json"  # Path to the persistent local configuration file
REMOTE_SERVER_URL = "192.168.1.112:5000"  # URL/IP of the remote server (the Raspberry Pi)


def save_json(config) -> None:
    # Save the given config dictionary to the local config.json file.
    with open(JSON_PATH, "w") as f:
        json.dump(config, f, indent=4)


def load_json() -> dict:
    # Read the existing config.json file if it exists; otherwise return an empty dict.
    try:
        with open(JSON_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


@app.route("/")
def index() -> str:
    # Render the main control panel UI with any previously saved config values.
    config = load_json()
    return render_template("index.html", config=config)


# -----------DO NOT TOUCH THE ROUTES, they work with the remote server as is-------------#


@app.route("/start", methods=["POST"])
def start() -> dict:
    # Send start request to remote device.
    url = f"http://{REMOTE_SERVER_URL}/start_container"
    # Send the request using Python
    response = requests.post(url, timeout=5)
    # Check the HTTP status code
    if response.status_code == 200:
        result = {"status": "OK", "message": "Container started successfully."}
    else:
        result = {"status": "FAILED", "message": f"Server error: {response.status_code}"}
    return jsonify(result)


@app.route("/stop", methods=["POST"])
def stop() -> dict:
    # Send stop request to remote device.
    url = f"http://{REMOTE_SERVER_URL}/stop_container"
    response = requests.post(url, timeout=20)  # High because of delay from Docker

    if response.status_code == 200:
        result = {"status": "OK", "message": "Container stopped successfully."}
    else:
        result = {"status": "FAILED", "message": f"Server error: {response.status_code}"}
    return jsonify(result)


@app.route("/restart", methods=["POST"])
def restart() -> dict:
    # Send restart request to remote device.
    url = f"http://{REMOTE_SERVER_URL}/restart_container"
    response = requests.post(url, timeout=20)

    if response.status_code == 200:
        result = {"status": "OK", "message": "Container restarted successfully."}
    else:
        result = {"status": "FAILED", "message": f"Server error: {response.status_code}"}
    return jsonify(result)


@app.route("/lock", methods=["POST"])
def lock() -> dict:
    # Send lock request to remote device.
    url = f"http://{REMOTE_SERVER_URL}/lock"
    # Send the request using Python
    response = requests.post(url, timeout=20)

    # Check the HTTP status code
    if response.status_code == 200:
        result = {"status": "OK", "message": "Unlocked successfully."}
    elif response.status_code == 409:
        # 409 means Conflict (Docker is running)
        result = {"status": "Failed, Docker Running"}
    else:
        # Handle other errors (500, 404, etc)
        result = {"status": "Failed", "message": f"Server error: {response.status_code}"}
    return jsonify(result)


@app.route("/unlock", methods=["POST"])
def unlock() -> dict:
    # Send unlock request to remote device.
    url = f"http://{REMOTE_SERVER_URL}/unlock"
    # Send the request using Python
    response = requests.post(url, timeout=5)

    # Check the HTTP status code
    if response.status_code == 200:
        result = {"status": "OK", "message": "Unlocked successfully."}
    elif response.status_code == 409:
        # 409 means Conflict (Docker is running)
        result = {"status": "Failed, Docker Running"}
    else:
        # Handle other errors (500, 404, etc)
        result = {"status": "Failed", "message": f"Server error: {response.status_code}"}
    return jsonify(result)


@app.route("/update", methods=["POST"])
def update() -> dict:
    """Persist the posted configuration locally and push it to the remote Pi."""
    # Get values from form
    request.form.get("action")  # which button was pressed

    # Update local JSON
    config = {
        "simulate": False,
        "discord_webhook": request.form.get("Discord_webhook"),
        "lock_override": (request.form.get("lock_override")) == "true",
        "lock_state": request.form.get("lock_state"),
    }
    save_json(config)

    try:
        # Copy the updated JSON to the remote host so the running service picks it up.
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
    app.run(host="0.0.0.0", port=5000)  # noqa: S104 - Intentional bind to all interfaces for local network access
