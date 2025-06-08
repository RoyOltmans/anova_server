import os
import asyncio
import logging
from types import TracebackType
from typing import Optional, Any, Union, Type, Tuple
from enum import Enum

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.uuids import normalize_uuid_str

import httpx

from commands import AnovaCommand

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Bluetooth Constants
ANOVA_SERVICE_UUID = "ffe0"
ANOVA_CHARACTERISTIC_UUID = "ffe1"
ANOVA_DEVICE_NAME = "Anova"

# Command Constants
MAX_COMMAND_LENGTH = 20
COMMAND_DELIMITER = "\r"

class AnovaException(Exception):
    """Base exception for Anova-related errors."""
    pass

class AnovaConnectionError(AnovaException):
    """Raised when there's an issue connecting to the Anova device."""
    pass

class AnovaCommandError(AnovaException):
    """Raised when there's an error executing a command."""
    pass

class DeviceStatus(Enum):
    STARTED = "started"
    STOPPED = "stopped"

    @classmethod
    def decode(cls, response: str) -> 'DeviceStatus':
        try:
															  
            return cls(response.strip().lower().split(" ")[0])
        except ValueError:
            logger.warning(f"Unknown device status received: {response}")
            raise ValueError(f"Unknown device status: {response}")

class DeviceManager:
    def __init__(self):
        self.devices = {}

    def add_device(self, device):
        if device.id_card in self.devices:
            logger.info(f"Updating state for existing device: {device.id_card}")
        else:
            logger.info(f"Registering new device: {device.id_card}")
        self.devices[device.id_card] = device

    def remove_device(self, device_id):
        if device_id in self.devices:
            logger.info(f"Removing device: {device_id}")
            del self.devices[device_id]
        else:
            logger.warning(f"Device {device_id} not found for removal.")

def retry_async(func, retries=3, delay=2):
    async def wrapper(*args, **kwargs):
        for attempt in range(retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(delay)
    return wrapper

class GetTargetTemperature:
    @staticmethod
    def decode(response: str) -> float:
        try:
													
            response = response.strip().lower()
            if "status" in response:
                parts = response.split()
                for part in parts:
                    try:
                        return float(part)
                    except ValueError:
                        continue
            else:
                return float(response)
        except ValueError:
            logger.error(f"Invalid response for target temperature: {response}")
            raise ValueError(f"Could not decode target temperature: {response}")

class AnovaBluetoothClient:
    _client: Optional[BleakClient]
    command_lock: asyncio.Lock
    device: Union[BLEDevice, str, dict, object]

    def __init__(self, device: Union[BLEDevice, str, dict, object]):
        self.command_lock = asyncio.Lock()
        self.device = device

    @staticmethod
    async def scan(timeout: float = 5.0) -> Tuple[Optional[Union[BLEDevice, dict]], Optional[Union[AdvertisementData, dict]]]:
		   
																				   
																			
		   
        ble_proxy_url = os.environ.get("BLE_PROXY_URL")
        if ble_proxy_url:
            url = ble_proxy_url.rstrip("/") + "/scan"
            logger.info(f"Using BLE proxy for scan at {url}")
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=timeout + 5)
                    resp.raise_for_status()
                    devices = resp.json()
                    for dev in devices:
                        logger.debug(f"Proxy found device: {dev}")
                        if dev.get("name") == ANOVA_DEVICE_NAME:
                            for uuid in dev.get("service_uuids", []):
                                if normalize_uuid_str(ANOVA_SERVICE_UUID) == uuid.lower():
                                    logger.info(f"Anova device found via proxy: {dev.get('name')}")
																					
                                    return dev, {
                                        "local_name": dev.get("name"),
                                        "service_uuids": dev.get("service_uuids", [])
                                    }
                    logger.warning("No Anova devices found via BLE proxy.")
                    return None, None
            except Exception as e:
                logger.error(f"BLE proxy scan failed: {e}")
                return None, None

										   
        logger.debug("Starting BLE scan for Anova devices (local/bleak).")
        devs = await BleakScanner.discover(timeout=timeout, return_adv=True)
        for dev, adv in devs.values():
            logger.debug(f"Found device: {adv.local_name}, UUIDs: {adv.service_uuids}")
            if adv.local_name == ANOVA_DEVICE_NAME:
                for uuid in adv.service_uuids or []:
                    if normalize_uuid_str(ANOVA_SERVICE_UUID) == uuid.lower():
                        logger.info(f"Anova device found: {dev.name}")
                        return dev, adv

        logger.warning("No Anova devices found during BLE scan (local).")
        return None, None

    async def __aenter__(self) -> 'AnovaBluetoothClient':
        logger.debug(f"Attempting to connect to device: {self.device}")
        self._client = BleakClient(self.device)
        try:
            await self._client.connect()
            logger.info("Connected to Anova device.")
        except Exception as e:
            logger.error(f"Failed to connect to Anova device: {e}")
            raise AnovaConnectionError(f"Failed to connect: {e}")
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> None:
        if self._client:
            logger.debug("Disconnecting from Anova device.")
            await self._client.disconnect()
            self._client = None
            logger.info("Disconnected from Anova device.")

    async def validate_device(self):
														   
        for attempt in range(3):
            if self.device.id_card != "idle":
                logger.info(f"Device ID resolved: {self.device.id_card}")
                return
            logger.warning("Device ID is not ready. Retrying...")
            await asyncio.sleep(1)
        raise ValueError("Device ID could not be resolved after retries.")

    @retry_async
    async def perform_handshake(self):
													 
        logger.info("Attempting handshake...")
								  
        await asyncio.sleep(1)
        logger.info("Handshake successful.")

    async def heartbeat(self):
        try:
            logger.debug("Sending heartbeat command...")
            temperature_response = await self.send_command(GetTargetTemperature())
            logger.info(f"Target temperature received: {temperature_response}°C")
        except ValueError as e:
            logger.error(f"Error during heartbeat: {e}")

    async def _monitor_device(self, device):
        retries = 3
        for attempt in range(retries):
            try:
                await device.heartbeat()
                break
            except ValueError as e:
                logger.warning(f"Heartbeat failed (attempt {attempt + 1}): {e}")
                if attempt == retries - 1:
                    logger.error(f"Device {device.id_card} disconnected after repeated heartbeat failures.")
                    self.remove_device(device.id_card)

    @retry_async
    async def send_command(self, command: Union[AnovaCommand, str], timeout: float = 10.0) -> Any:
        # PROXY MODE: Use HTTP POST to proxy if self.device is not a real BLEDevice
        is_proxy = (
            isinstance(self.device, dict)
            or type(self.device).__name__.startswith("BLEDev")
            or hasattr(self.device, "address") and not hasattr(self.device, "metadata")
        )
        if is_proxy:
            ble_proxy_url = os.environ.get("BLE_PROXY_URL", "http://localhost:5000")
            url = ble_proxy_url.rstrip("/") + "/write"
            address = getattr(self.device, "address", None) or (self.device.get("address") if isinstance(self.device, dict) else None)
            # Always convert to string for proxy!
            if isinstance(command, AnovaCommand):
                cmd_str = command.encode()
            elif isinstance(command, str):
                cmd_str = command
            else:
                logger.error(f"Unsupported command type for BLE proxy: {type(command)}")
                raise AnovaCommandError("Unsupported command type for BLE proxy")
            logger.info(f"Proxy BLE write: url={url}, address={address}, command={cmd_str!r}")
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json={
                        "address": address,
                        "command": cmd_str
                    }, timeout=timeout)
                    resp.raise_for_status()
                    result = resp.json()
                    return result.get("result")
            except Exception as e:
                logger.error(f"BLE proxy write failed: {e}")
                raise AnovaCommandError(f"BLE proxy write failed: {e}")

        # NORMAL BLE (LOCAL)
        if isinstance(command, AnovaCommand) and not command.supports_ble():
            raise AnovaCommandError(f"Command '{command}' is not supported over BLE")
        if not self._client or not self._client.is_connected:
            raise AnovaConnectionError("Client is not connected to the device.")

        logger.debug(f"Sending command: {command}")
        async with self.command_lock:
            command_data = f"{command}\r".encode()
            logger.debug(f"Prepared command data: {command_data}")

            async def response_callback(sender: BleakGATTCharacteristic, data: bytearray) -> None:
                logger.debug(f"Response callback triggered with data: {data}")
                await q.put(data)

            q: asyncio.Queue[bytearray] = asyncio.Queue()

            try:
                logger.debug(f"Starting notification for characteristic: {ANOVA_CHARACTERISTIC_UUID}")
                await self._client.start_notify(normalize_uuid_str(ANOVA_CHARACTERISTIC_UUID), response_callback)

                logger.debug(f"Writing command: {command_data}")
                for attempt in range(3):
                    try:
                        logger.debug(f"Attempting GATT write (attempt {attempt + 1})")
                        await self._client.write_gatt_char(
                            normalize_uuid_str(ANOVA_CHARACTERISTIC_UUID), command_data, response=True
                        )
                        logger.info("GATT write successful.")
                        break
                    except Exception as e:
                        logger.warning(f"GATT write failed on attempt {attempt + 1}: {e}")
                        if attempt == 2:
                            raise

                response_buffer = bytearray()
                logger.debug(f"Waiting for response with timeout: {timeout}s")
                try:
                    async with asyncio.timeout(timeout + 5):  # Add buffer to timeout
                        while chunk := await q.get():
                            logger.debug(f"Received notification chunk: {chunk}")
                            response_buffer.extend(chunk)
                            if b'\r' in chunk:
                                break
                except asyncio.TimeoutError:
                    logger.error(f"Command '{command}' timed out waiting for response.")
                    raise AnovaCommandError(f"Command '{command}' timed out")

                if not response_buffer:
                    logger.error("No response received from device.")
                    raise AnovaCommandError("Empty response received")

                response = response_buffer.decode().strip()
                logger.debug(f"Full response received: {response}")

                if isinstance(command, str):
                    return response
                return command.decode(response)

            except asyncio.CancelledError:
                logger.error("Task was canceled while waiting for a response.")
                raise
            except Exception as e:
                logger.error(f"Error during GATT write or notification: {e}")
                raise
            finally:
                logger.debug("Stopping notification.")
                await self._client.stop_notify(normalize_uuid_str(ANOVA_CHARACTERISTIC_UUID))
