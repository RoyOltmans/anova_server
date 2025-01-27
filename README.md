# Anova Server

This project provides a server for controlling your Anova, building on the excellent work by [AlmogBaku](https://github.com/AlmogBaku/Anova4All/). AlmogBaku's original code is a great starting point, and this repository expands on it with enhancements to make deployment easier and more flexible.

## Installation

To get started with the server, follow these steps:

### 1. Clone this repository:
   ```bash
   git clone https://github.com/RoyOltmans/anova_server.git
   cd anova_server

### 2. Build the Docker image:

```bash
docker build -t anova-server .
```

### 3. Run the Docker container, exposing ports 8000 and 8080:

```bash
docker run -p 8000:8000 -p 8080:8080 anova-server
```
### 4. Access the server at http://localhost:8000 or http://localhost:8080.

# Docker Setup
This project is packaged with Docker to simplify the setup and ensure consistent environments. The Dockerfile allows you to build the necessary environment with all dependencies, making the setup process much easier. Once you've built the Docker image, you can run it with the necessary ports exposed for communication. Docker handles all the environment configurations, including dependencies for Python, making it easier to deploy anywhere.

## Steps:
Build the Docker image with the command:

```bash
docker build -t anova-server .
```

## Run the Docker container:
```bash
docker run -p 8000:8000 -p 8080:8080 anova-server
```

# Missing Bluetooth Control
Currently, Bluetooth control functionality is not yet implemented in this server. While AlmogBaku's original script has great potential, there are some technical hurdles that need to be overcome to integrate Bluetooth management into the server. The current version focuses primarily on HTTP-based control and does not yet support direct Bluetooth communication for Anova.

## Why it's missing:
Technical Limitation: The Bluetooth integration requires additional hardware configurations (like a Bluetooth adapter) and software adjustments that have yet to be fully developed for this server.
Future Plans: Implementing Bluetooth control is a planned feature for future releases. Contributions in this area are welcome if you have the necessary expertise.
It works but you need to deploy it on a RPI 4 not in a container but as code (I used it to couple the anova to my docker server). You can do this by accessing http://[yourserverip]:8000/docs here is a page for using the api's.

## Background
This repository started from the Python script created by AlmogBaku. Initially, I attempted to get the server working using Go, but after some challenges with dependencies and server setup, I shifted to Python and Docker for a smoother experience. The result is a more streamlined approach with working Docker support.

## License
This project is licensed under the MIT License. See [LICENSE](/LICENSE) for details.

## Disclaimer
Anova_server itself and the associated Python script are distributed under the MIT License. While every effort has been made to ensure the safety and security of this code, you use it at your own risk. Configure the script and card securely to avoid exposing sensitive data. Performance may vary depending on the size and structure of your filesystem.

