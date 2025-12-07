import logging

import docker
from flask import Flask, jsonify

app = Flask("Docker_controller")
client = docker.from_env()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONTAINER_NAME = "motion-detector"


@app.route("/restart_container", methods=["POST"])
def restart_container() -> tuple:
    try:
        container = client.containers.get(CONTAINER_NAME)
        container.restart()
        return jsonify({"status": "success", "message": f"Container {CONTAINER_NAME} restarted."}), 200
    except docker.errors.NotFound:
        return jsonify({"status": "error", "message": f"Container {CONTAINER_NAME} not found."}), 404
    except Exception as e:
        logger.error(f"Error restarting container: {e!s}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/stop_container", methods=["POST"])
def stop_container() -> tuple:
    try:
        container = client.containers.get(CONTAINER_NAME)
        container.stop()
        return jsonify({"status": "success", "message": f"Container {CONTAINER_NAME} stopped."}), 200
    except docker.errors.NotFound:
        return jsonify({"status": "error", "message": f"Container {CONTAINER_NAME} not found."}), 404
    except Exception as e:
        logger.error(f"Error stopping container: {e!s}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/start_container", methods=["POST"])
def start_container() -> tuple:
    try:
        container = client.containers.get(CONTAINER_NAME)
        container.start()
        return jsonify({"status": "success", "message": f"Container {CONTAINER_NAME} started."}), 200
    except docker.errors.NotFound:
        return jsonify({"status": "error", "message": f"Container {CONTAINER_NAME} not found."}), 404
    except Exception as e:
        logger.error(f"Error starting container: {e!s}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)  # noqa: S104
