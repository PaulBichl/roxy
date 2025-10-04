from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
from pathlib import Path # 1. Import the Path object

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Get the content length
            content_length = int(self.headers.get('Content-Length', 0))
            # Read the posted data
            post_data = self.rfile.read(content_length)

            # 2. Construct the full path in the home directory 🏠
            file_path = Path.home() / "received_image.jpg"

            # Save image to the specified path
            with open("/tmp/received_image.jpg", "wb") as f:
                f.write(post_data)

            # Send response
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Image received successfully")
            logging.info(f"Saved {content_length} bytes to {file_path}")

        except Exception as e:
            logging.exception("Error processing POST")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler):
    logging.basicConfig(level=logging.INFO)
    server_address = ('', 7860)
    httpd = server_class(server_address, handler_class)
    logging.info("Starting httpd...")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
