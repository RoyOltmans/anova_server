## Anova Server

This project provides a server for controlling your Anova via rest json API's, building on the excellent work by [AlmogBaku](https://github.com/AlmogBaku/Anova4All/). AlmogBaku's original code is a great starting point, and this repository expands on it with enhancements to make deployment easier and more flexible. Also stabilized the code so the anova is always available.

### Installation

To get started with the server, follow these steps:

#### 1. Clone this repository:
   ```bash
   git clone https://github.com/RoyOltmans/anova_server.git
   cd anova_server

#### 2. Build the Docker image:

```bash
docker build -t anova-server .
```

#### 3. Run the Docker container, exposing ports 8000 and 8080:

```bash
docker run -p 8000:8000 -p 8080:8080 anova-server
```
#### 4. Access the server at http://localhost:8000 or http://localhost:8080.

## Docker Setup
This project is packaged with Docker to simplify the setup and ensure consistent environments. The Dockerfile allows you to build the necessary environment with all dependencies, making the setup process much easier. Once you've built the Docker image, you can run it with the necessary ports exposed for communication. Docker handles all the environment configurations, including dependencies for Python, making it easier to deploy anywhere.

#### Steps:
Build the Docker image with the command:

```bash
docker build -t anova-server .
```

#### Run the Docker container:
```bash
docker run -p 8000:8000 -p 8080:8080 anova-server
```

#### Manual Bluetooth Control
Currently, Bluetooth control functionality is not configured in the docker instance but it is implemented in the server code. There are some technical hurdles that need to be overcome to integrate Bluetooth via docker that wasnt my usecase. You will need to deploy the code (not the docker) on a RPI 4 from there you can start the process via the API and BLE and move the Anova to a server or stay on the RPI. This part is needed to move from a BLE supporting device to a server runnign docker.

Implementing Bluetooth control in docker is a planned feature for future releases via Dockercontainer (so it doesnt matter if you deploy on a RPI or X86). ##Contributions in this area are welcome if you have the necessary time.## Basiccaly it works but you need to deploy it on a RPI 4 via GIT clone and start the service there.

BEWARE this forces specific configuration on your system!!!!!
```bash
apt-get update && \
apt-get upgrade -y && \
apt-get install -y --no-install-recommends \
software-properties-common \
gpg-agent
add-apt-repository ppa:deadsnakes/ppa -y
apt-get install -y --no-install-recommends \    
python3.11 \
python3.11-venv \
python3.11-distutils \
python3-pip
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
update-alternatives --config python3	
python3.11 -m pip install --upgrade pip
pip install pyproject.toml bleak uvicorn fastapi pydantic-setting
```

From there the server should start:

```bash
uvicorn app.main:app --reload  --app-dir /anova/python --port 8000 --host 0.0.0.0 
```

Start by accessing the server at http://[yourserverip]:8000/docs

AGAIN BE AWERE "The support for the host BLE is not in the container code (I used the setup with a RPI to couple the anova to my docker server)"

The migration steps of the anova can be executed by accessing http://[yourserverip]:8000/docs here is a page for using the api's.
   - 1 make a new key for the anova
   - 2 push the server config
   - 3 install the wifi config

### Background
This repository started from the Python script created by AlmogBaku. Initially, I attempted to get the server working using Go, but after some challenges with dependencies and server setup, I shifted to Python and Docker for a smoother experience. The result is a more streamlined approach with working Docker support.

### License
This project is licensed under the MIT License. See [LICENSE](/LICENSE) for details.

### Disclaimer
Anova_server itself and the associated Python script are distributed under the MIT License. While every effort has been made to ensure the safety and security of this code, you use it at your own risk. Configure the script and card securely to avoid exposing sensitive data. Performance may vary depending on the size and structure of your filesystem.

### References

Thanks for @TheUbuntuGuy for the initial research on the Anova Wi-Fi protocol:

- https://www.youtube.com/watch?v=xDDPFHhY7ec
- https://gist.github.com/TheUbuntuGuy/225492a8dec816d49b70d9c21811e8b1

**Important**: This project is not affiliated with Anova or any other company. It's a community project that aims to
keep the device functional after the cloud services are shut down.

