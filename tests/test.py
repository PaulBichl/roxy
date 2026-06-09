from roxy import Roxy

roxy = Roxy()
roxy.load_config("tests/config.json")
# roxy.initialize_model("./tmp/models/model.pt")
roxy.initialize_model("src/roxy/models/model.pt")
roxy.start_up()
print("Roxy initialized for testing with simulation mode.")

frame = roxy.capture_frame()
label, conf = roxy.classify_frame(frame)
print(f"Test classification result: {label} with confidence {conf:.2f}")

roxy.send_to_discord("./test.jpg", label, conf, is_startup=False)
