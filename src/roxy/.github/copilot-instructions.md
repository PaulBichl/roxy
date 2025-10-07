This repository implements a small Raspberry-Pi-focused motion detector written in Python. The guidance below is tuned to help automated coding agents make useful, low-risk changes quickly.

Repository overview
- Purpose: lightweight motion detection and image upload to Discord; built to run on Pi Zero W2 or similar devices using Picamera2 (preferred) or OpenCV fallback.
- Key files:
  - `motion_gemini.py` — main, more modern/robust detector with environment-configured options, sunrise/sunset switching and Picamera2 fallback to cv2.VideoCapture.
  - `motion_discord.py` — earlier/simpler detector example (single-file script) useful for small fixes or quick reference.
  - `test.py` — small style/example file (not a test harness).
  - `__about__.py` / `__init__.py` — package metadata.

Architecture and design notes (what to preserve)
- Single-process, single-camera capture loop: both detectors read frames in a tight loop, downscale for motion processing and save a full-resolution grayscale image on motion. Avoid introducing background threads that change camera controls without coordinating with the capture loop.
- Picamera2 preferred but optional: `motion_gemini.py` detects `picamera2` at import time and falls back to `cv2.VideoCapture(0)` if unavailable. Keep this explicit fallback logic when editing camera initialization or capture code.
- Day/night mode logic is driven by either ambient brightness (in `motion_discord.py`) or sunrise/sunset checks (in `motion_gemini.py`). Changes that affect exposure, AWB, or gain must respect the existing mode-switch cadence (camera_setup / last change timers) to avoid flapping.
- Minimal-CPU target: this code is intended for Pi Zero W2. Favor small image sizes for motion detection (see `PROCESS_WIDTH` / `PROCESS_HEIGHT`) and low-frequency polling; avoid heavy ML libraries or large-kernel blurs unless gated by an environment switch.

Important runtime and developer workflows
- Run locally (desktop/dev without Pi camera): ensure Picamera2 is not importable (or set up a virtual environment without it) and the code will use cv2.VideoCapture fallback. Example quick run:
  - python -m roxy.motion_gemini
  - Add `--no-discord` to skip webhook uploads.
- Environment variables (used throughout `motion_gemini.py`):
  - `DISCORD_WEBHOOK` — webhook URL (default is hard-coded in repo; treat it as prod secret if you replace it).
  - `MOTION_THRESHOLD`, `PROCESS_WIDTH`, `PROCESS_HEIGHT`, `MIN_AREA`, `CAPTURE_INTERVAL`, `IMAGE_PATH`, `SUN_CHECK_INTERVAL` — tuning for motion sensitivity and performance.
  - `CAMERA_NOIR` — set to `1` for NoIR/IR-capable cameras; affects exposure/IR processing.
  - `LATITUDE`, `LONGITUDE` — used by `suntime` to compute sunrise/sunset times.

Testing and debugging patterns
- Logging: `motion_gemini.py` configures `logging` (logger name `motion_gemini`). Use this logger for new messages and follow the established levels (info/warning/debug).
- Safe edits: when adding new camera controls or exception handling, preserve the `finally:` block that stops `picam2` and releases `video_capture` to avoid leaving the camera locked.
- Local dev: use `--no-discord` or set `DISCORD_WEBHOOK=""` to prevent accidental uploads while testing. Unit tests are not present — prefer small runtime checks or local functions tested by short scripts.

Integration points and external dependencies
- Picamera2: optional hardware dependency. Any change touching `Picamera2` should include a fallback path and not assume the library is present at import time.
- OpenCV (`cv2`) and NumPy: required for image capture and processing.
- Requests: used to upload to Discord webhook. Network calls should include timeouts (existing code uses timeout params).
- suntime: computes sunrise/sunset — handle exceptions because network/time-zone or bad lat/long can throw.

Conventions and patterns specific to this repo
- Configuration via environment variables (not a config file). New features requiring configuration should prefer env overrides and sensible defaults.
- Minimal external state: saved images are written to `IMAGE_PATH` (default `/tmp/motion.jpg`). If changing file paths, keep portability in mind (Windows vs Linux) and respect environment overrides.
- Use RGB internally for frames when using cv2 fallback (the code converts BGR to RGB in `capture_frame()`); maintain consistent color order when adding processing steps.
- Camera control changes are grouped in `Camera_setup()` / `adjust_exposure()` style functions. Keep changes centralized to avoid duplicated control logic.

Examples to reference when implementing changes
- To add a CLI flag, follow `argparse` usage in `motion_gemini.py`'s `main()` (see `--no-discord`).
- To save a full-resolution grayscale image, see the block under `if motion_detected` in `motion_gemini.py` (convert `frame` to gray and call `cv2.imwrite(IMAGE_PATH, gray_full)`).
- To perform Picamera2 controls safely, follow existing `try/except` in `Camera_setup()` and maintain the `time.sleep()` used to allow settings to take effect.

Risk guidance for automated edits
- Do not commit changes that expose secrets (Discord webhook) in plaintext; keep them configurable via `DISCORD_WEBHOOK` env var.
- Avoid heavy refactors that change the capture loop concurrency model. Small focused changes (threshold tuning, extra logging, small helper functions) are preferred.

If you need more context
- Inspect `motion_gemini.py` and `motion_discord.py` for concrete examples of camera setup, capture loop, motion math and Discord upload.
- Ask for specifics about intended hardware (Pi Zero W2 vs desktop) if you need to tune performance or enable optional features.

If you change this file
- When updating guidance, keep examples current and reference the exact file paths shown above.
