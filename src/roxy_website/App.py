from flask import Flask, render_template, request, jsonify  # Flask web framework and helpers for web, templates, ajax/json
import json  # For reading/writing JSON config files
import requests  # For making HTTP requests to the remote server
import subprocess  # For running system shell commands (like curl)
import os  # For working with file paths, file I/O

app = Flask(__name__)  # Initialize the Flask app

JSON_PATH = "config.json"  # Path to the persistent local configuration file
REMOTE_SERVER_URL = "192.168.1.112:5000"  # URL/IP of the remote server (the Raspberry Pi)


def save_json(config):
    """Persist the posted configuration dictionary to config.json."""
    with open(JSON_PATH, "w") as f:
        json.dump(config, f, indent=4)


def load_json():
    """Read the existing config.json file if it exists; otherwise return an empty dict."""
    try:
        with open(JSON_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


@app.route("/")
def index():
    """Render the main control panel UI with any previously saved config values."""
    config = load_json()
    return render_template("index.html", config=config)

@app.route("/start", methods=["POST"])
def start():
    """Placeholder for a remote 'start' action; HTTP request code is commented out on purpose."""
    # The actual remote call is commented out because the endpoint and payload still need to be finalized.
    # If you want this button to work, uncomment and adjust the request logic below.
    """ try:
        r = requests.put(REMOTE_SERVER_URL, start, timeout=5)
        result = {"status": "OK", "remote_response": r.text}
    except Exception as e:
        result = {"status": "FAILED", "error": str(e)} """

    # return jsonify(result)

@app.route("/stop", methods=["POST"])
def stop():
    """Placeholder for a remote 'stop' action; request code is still commented out."""
    # See comments in start(): this needs real request details before it can be enabled.
    """ try:
        r = requests.put(REMOTE_SERVER_URL, stop, timeout=5)
        result = {"status": "OK", "remote_response": r.text}
    except Exception as e:
        result = {"status": "FAILED", "error": str(e)} """
    
@app.route("/restart", methods=["POST"])
def restart():
    """Call the remote endpoint that restarts the container running on the Pi."""
    curll_command = ["curl", "-X", "POST", f"http://{REMOTE_SERVER_URL}/restart_container"]
    try:
        subprocess.run(curll_command, check=True)
        result = {"status": "OK", "message": "Container restarted successfully."}
    except subprocess.CalledProcessError as e:
        result = {"status": "FAILED", "error": str(e)}
    return jsonify(result)

@app.route("/get_lock_state", methods=["GET"])
def get_lock_state():
    """Read the lock state from the remote device and return it to the UI."""
    curl_command = ["curl", "-X", "GET", f"http://{REMOTE_SERVER_URL}/get_lock_state"]
    try:
        response = subprocess.run(curl_command, check=True, capture_output=True, text=True)
        lock_state = response.stdout.strip()
        result = {"status": "OK", "lock_state": lock_state}
    except subprocess.CalledProcessError as e:
        result = {"status": "FAILED", "error": str(e)}
    return jsonify(result)

@app.route("/toggle_lock", methods=["POST"])
def toggle_lock():
    """Ask the remote device to flip the current lock state."""
    curl_command = ["curl", "-X", "POST", f"http://{REMOTE_SERVER_URL}/toggle_lock"]
    try:
        subprocess.run(curl_command, check=True)
        result = {"status": "OK", "message": "Lock toggled successfully."}
    except subprocess.CalledProcessError as e:
        result = {"status": "FAILED", "error": str(e)}
    return jsonify(result)

@app.route("/update", methods=["POST"])
def update():
    """Persist the posted configuration locally and push it to the remote Pi."""
    # Get values from form
    action = request.form.get("action")  # which button was pressed

    # Update local JSON
    config = {
        "Discord_webhook": request.form.get("Discord_webhook"),
        "conf_threshold": request.form.get("conf_threshold"),
        "lock_state": request.form.get("lock_state"),
        "lock_override": request.form.get("lock_override"),
        "last_action": action
        }
    save_json(config)

    try:
        # Copy the updated JSON to the remote host so the running service picks it up.
        subprocess.run([
            "scp", JSON_PATH, "p5@192.168.1.112:~/roxy/src/roxy/config.json"
        ], check=True)
        print("config.json copied successfully.")
    except Exception as e:
        app.logger.error("Failed to copy config.json: %s", e)

    return jsonify({"status": "OK"})
    #return jsonify(result)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
