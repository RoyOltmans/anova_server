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

# Custom Exceptions
class AnovaException(Exception):
    """Base exception for Anova-related errors."""


class AnovaConnectionError(AnovaException):
    """Raised when there's an issue connecting to the Anova device."""


class AnovaCommandError(AnovaException):
    """Raised when there's an error executing a command."""


class DeviceStatus(Enum):
    STARTED = "started"
    STOPPED = "stopped"

    @classmethod
    def decode(cls, response: str) -> 'DeviceStatus':
        try:
            # Attempt to match the first token of the response
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
            # Extract numeric part from the response
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
    device: Union[BLEDevice, str]

    def __init__(self, device: Union[BLEDevice, str]):
        self.command_lock = asyncio.Lock()
        self.device = device

    @staticmethod
    async def scan(timeout: float = 5.0) -> Tuple[Optional[BLEDevice], Optional[AdvertisementData]]:
        """
        Scan for Anova devices.

        :param timeout: Scan duration in seconds
        :return: BLEDevice and AdvertisementData of the device if found
        """
        logger.debug("Starting BLE scan for Anova devices.")
        devs = await BleakScanner.discover(timeout=timeout, return_adv=True)
        for dev, adv in devs.values():
            logger.debug(f"Found device: {adv.local_name}, UUIDs: {adv.service_uuids}")
            if adv.local_name == ANOVA_DEVICE_NAME:
                for uuid in adv.service_uuids:
                    if normalize_uuid_str(ANOVA_SERVICE_UUID) == uuid:
                        logger.info(f"Anova device found: {dev.name}")
                        return dev, adv

        logger.warning("No Anova devices found during scan.")
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
        """Ensure the device is ready before proceeding."""
        for attempt in range(3):
            if self.device.id_card != "idle":
                logger.info(f"Device ID resolved: {self.device.id_card}")
                return
            logger.warning("Device ID is not ready. Retrying...")
            await asyncio.sleep(1)
        raise ValueError("Device ID could not be resolved after retries.")

    @retry_async
    async def perform_handshake(self):
        """Perform the handshake with retry logic."""
        logger.info("Attempting handshake...")
        # Simulate handshake logic
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
