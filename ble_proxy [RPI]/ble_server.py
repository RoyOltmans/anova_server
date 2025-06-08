import asyncio
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from bleak import BleakClient, BleakScanner
from bleak.uuids import normalize_uuid_str

# Constants
ANOVA_SERVICE_UUID = "ffe0"
ANOVA_CHARACTERISTIC_UUID = "ffe1"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ble_proxy")

app = FastAPI()

class WriteRequest(BaseModel):
    address: str
    command: str  # Accept *any* string

@app.get("/scan")
async def scan_ble():
    logger.info("Scanning for BLE devices...")
    devices = await BleakScanner.discover(timeout=5, return_adv=True)
    result = []
    for d, adv in devices.values():
        info = {
            "address": d.address,
            "name": getattr(d, "name", None),
            "rssi": getattr(adv, "rssi", None),
            "service_uuids": getattr(adv, "service_uuids", []),
        }
        result.append(info)
        logger.info(f"Scan found: {info}")  # NEW: log each device with all info
    return result

@app.post("/write")
async def ble_write(req: WriteRequest):
    # Log the incoming request
    logger.info(f"BLE PROXY /write POST: address={req.address!r}, command={req.command!r}")

    try:
        async with BleakClient(req.address) as client:
            logger.info(f"Connected to BLE device: {req.address}")

            # Prepare notification queue
            q: asyncio.Queue[bytes] = asyncio.Queue()

            def notification_handler(sender, data):
                logger.info(f"Notification from {sender}: {data!r}")
                q.put_nowait(data)

            await client.start_notify(normalize_uuid_str(ANOVA_CHARACTERISTIC_UUID), notification_handler)

            command_data = f"{req.command}\r".encode()
            await client.write_gatt_char(normalize_uuid_str(ANOVA_CHARACTERISTIC_UUID), command_data, response=True)
            logger.info(f"Wrote to characteristic: {command_data!r}")

            # Wait for BLE response with a timeout
            response = bytearray()
            try:
                while True:
                    chunk = await asyncio.wait_for(q.get(), timeout=5)
                    response.extend(chunk)
                    if b"\r" in chunk:
                        break
            except asyncio.TimeoutError:
                logger.warning("BLE notification response timed out.")

            await client.stop_notify(normalize_uuid_str(ANOVA_CHARACTERISTIC_UUID))

            # Decode and log the BLE response
            result_str = response.decode(errors="ignore").strip()
            logger.info(f"BLE result for address={req.address}, command={req.command!r}: {result_str!r}")
            return {"result": result_str}
    except Exception as e:
        logger.error(f"BLE write failed: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.get("/")
def root():
    return {"message": "BLE Proxy API running"}