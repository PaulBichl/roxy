import os

import gdown
from ultralytics import YOLO

# download nano classification model
file_id = "1XBHIwLef2uT6u4mAxOi03UeHbfI8uEOU"
url = f"https://drive.google.com/uc?id={file_id}"
os.makedirs("./tmp/models", exist_ok=True)
output = "./tmp/models/model.pt"
gdown.download(url, output, quiet=False)

# convert model into NCNN format for edge deployment, TODO this should not be done on raspberry pi
model = YOLO("./tmp/models/model.pt")
# Export the model to NCNN format
model.export(format="ncnn")  # creates '/yolo11n_ncnn_model'
