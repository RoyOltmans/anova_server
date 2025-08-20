# Anova Server

A Python and Docker-based server for controlling your Anova Precision Cooker via REST API, based on and expanded from [AlmogBaku/Anova4All](https://github.com/AlmogBaku/Anova4All). This project lets you operate your Anova independently of cloud services, integrates easily with Home Assistant, and provides both WiFi and Bluetooth (BLE) connectivity.

---

## 📝 Change List

- **Added environment variables for BLE proxy on Raspberry Pi:**  
  - `BLE_ADAPTER` for selecting the BLE adapter (e.g. `hci0`)
  - `BLE_PROXY_PORT` to select the proxy's HTTP port (optional, default: 5000)
- **Documented `-e BLE_PROXY_URL=http://[your ble server]:5000`** for Docker container usage when bridging WiFi <-> BLE
- **Added example systemd service to run the BLE proxy as a background service**
- Clarified Docker, native, and proxy usage instructions
- General documentation improvements and clarifications

---

## BugFixes 

August 2025
 - Removed DockerFile in root (not correctly linked with the anova server), mixup accured because of adding BLE features
 - Markup fixes in DockerFIle
 - You need to build the docker in the anova_server folder

---

## Features

- Control and monitor Anova via RESTful API
- Integrates with Home Assistant via REST sensors and commands
- Supports both WiFi and Bluetooth (BLE) devices
- Dockerized for portability and easy deployment
- Flexible: use on x86 or Raspberry Pi
- BLE <-> WiFi Proxy support for moving devices from BLE to WiFi

---

## Quick Start

### 1. Clone and Build Anova Server

```bash
git clone https://github.com/RoyOltmans/anova_server.git
cd anova_server/anova_server
docker build -t anova-server .
```

### 2. Run the Docker Container

If you want to connect the server (running in Docker) to a BLE proxy running on another device (e.g. a Raspberry Pi), set the `BLE_PROXY_URL` environment variable when running the container:

```bash
docker run -p 8000:8000 -p 8080:8080 \
  -e BLE_PROXY_URL=http://[your ble server]:5000 \
  anova-server
```

- Replace `[your ble server]` with the hostname or IP address of your BLE proxy server.

Visit [http://localhost:8000/docs#/default/get_devices_api_devices_get](http://localhost:8000/docs#/default/get_devices_api_devices_get) or [http://localhost:8080/docs#/default/get_devices_api_devices_get](http://localhost:8080/docs#/default/get_devices_api_devices_get).

Be aware, if you are debugging via a console, you will see error's this is can be because your Anova is not powered on (this will register as an error). This can mean that the server is running according and it will function if your Anova registers itself via the network.

---

## BLE (Bluetooth) Proxy on Raspberry Pi

The project includes a lightweight BLE proxy (in `ble_proxy/ble_server.py`) for bridging BLE-only Anova devices to WiFi.  
**This is run natively on a BLE-capable Raspberry Pi, not in Docker.**

### BLE Proxy Environment Variables

To use the BLE proxy you **must** set the environment variable `BLE_ADAPTER` to specify which Bluetooth adapter to use (such as `hci0`).  
You may also set `BLE_PROXY_PORT` to define the HTTP port (default: 5000).

**Example usage:**

```bash
export BLE_ADAPTER=hci0
export BLE_PROXY_PORT=5000  # Optional, defaults to 5000
python3 ble_server.py
```

- `BLE_ADAPTER`: (Required) Your Bluetooth adapter, usually `hci0`
- `BLE_PROXY_PORT`: (Optional) Port to run the proxy (default: 5000)

The proxy will expose an HTTP API so the main Anova server (Docker or host) can communicate with BLE devices via the Pi.

---

## Manual RPi Host Setup (for BLE, native Python)

If you want to run the server **natively** on a Raspberry Pi with BLE (not in Docker):

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y --no-install-recommends \
    software-properties-common gpg-agent python3.11 python3.11-venv python3.11-distutils python3-pip
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --config python3
python3.11 -m pip install --upgrade pip
pip install pyproject.toml bleak uvicorn fastapi pydantic-settings
```

Start the API server:

```bash
uvicorn app.main:app --reload --app-dir ./anova_server/python --port 5000 --host 0.0.0.0
```

---

### Running the BLE Proxy as a systemd Service

You can run the BLE proxy as a background service so it starts on boot and is managed by `systemctl`.

**1. Create a file `/etc/systemd/system/ble-uvicorn.service` with the following content:**

```ini
[Unit]
Description=BLE Proxy Uvicorn Service
After=network.target

[Service]
# Working directory (where ble_server.py is located)
WorkingDirectory=/opt/ble_proxy

# Command to run. Use the full path to uvicorn if needed.
ExecStart=/home/USERNAME/.local/bin/uvicorn ble_server:app --host 0.0.0.0 --port 5000

# If using a Python virtual environment:
# ExecStart=/opt/ble_proxy/venv/bin/uvicorn ble_server:app --host 0.0.0.0 --port 5000

# The user to run as (change to your own user or 'pi')
User=USERNAME
Group=USERNAME

Restart=always

[Install]
WantedBy=multi-user.target
```

**2. Reload systemd and enable/start the service:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable ble-uvicorn.service
sudo systemctl start ble-uvicorn.service
sudo systemctl status ble-uvicorn.service
```

**Notes:**
- Replace `USERNAME` with your actual Linux user (commonly `pi` on Raspberry Pi).
- Set `WorkingDirectory` and `ExecStart` to your actual paths.
- If you use a Python virtual environment, point `ExecStart` to its `uvicorn`.

---

## Manual Bluetooth Control

Currently, Bluetooth control is **not** supported in Docker.  
If you need BLE, use the instructions above to run on a Raspberry Pi natively, setting the `BLE_ADAPTER` environment variable.

---

## Home Assistant Integration

1. See API docs at `/docs` (OpenAPI/Swagger).
2. Add REST sensors and commands to `configuration.yaml` (see examples below):

### Example (replace placeholders):

```yaml
sensor:
  - platform: rest
    name: "Anova Temperature"
    resource: "http://YOUR_ANOVA_API_URL/api/devices/YOUR_DEVICE_ID/temperature"
    headers:
      Authorization: "Bearer YOUR_SECRET_KEY"
    value_template: "{{ value_json.temperature }}"
    unit_of_measurement: "°C"
    scan_interval: 60
```

```yaml
rest_command:
  set_anova_temperature:
    url: "http://YOUR_ANOVA_API_URL/api/devices/YOUR_DEVICE_ID/target_temperature"
    method: "post"
    headers:
      Authorization: "Bearer YOUR_SECRET_KEY"
      Content-Type: "application/json"
    payload: '{"temperature": {{ temperature }} }'
```

---

## BLE Setup & WiFi Migration

1. **Pair Anova over BLE:**  
   Use `/api/ble/secret_key` and save the key and device name.
2. **Push server config:**  
   `/api/ble/config_wifi_server` — Add the server IP/host and port.
3. **Install WiFi config:**  
   Add your WiFi SSID and password via the API.

---

## Troubleshooting

- Ensure your `BLE_ADAPTER` variable matches your hardware (`hci0` is common for internal Pi BLE).
- If using Docker and a remote BLE proxy, **set** `-e BLE_PROXY_URL=http://[your ble server]:5000` (replace host as needed).
- Docker does **not** support BLE directly yet. For BLE, use the native install on RPi and the proper env vars.
- Ensure Home Assistant and the server are on the same network.

---

## License

MIT License — See [LICENSE](LICENSE).

---

## References

Thanks to [@TheUbuntuGuy](https://gist.github.com/TheUbuntuGuy/225492a8dec816d49b70d9c21811e8b1) for original Anova Wi-Fi protocol research.  
Not affiliated with Anova Culinary. Community-maintained.




