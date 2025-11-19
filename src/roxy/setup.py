import os

import gdown

# download nano classification model
file_id = "1XBHIwLef2uT6u4mAxOi03UeHbfI8uEOU"
url = f"https://drive.google.com/uc?id={file_id}"
os.makedirs("./tmp/models", exist_ok=True)
output = "./tmp/models/model.pt"
gdown.download(url, output, quiet=False)
