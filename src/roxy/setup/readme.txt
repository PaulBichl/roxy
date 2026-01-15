____________________________________________________________________________________
Prerequisits:
        - Using Raspberry Pi with camera
        - Docker installed locally
            This guide can be used: https://pimylifeup.com/raspberry-pi-docker/
____________________________________________________________________________________
Steps to run the application:
1. get config.json
2. docker build -t p5-camera .
3. chmod +x run.sh
4. ./run.sh
____________________________________________________________________________________
check logs:
docker logs -t motion-detector
