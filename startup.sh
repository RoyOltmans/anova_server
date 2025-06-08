docker run -dit --name anova_server -p 8000:8000 -p 8090:8080 -e BLE_PROXY_URL=http://rpi-ble-proxy.local.int:5000 anova-server
