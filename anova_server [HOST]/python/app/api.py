import asyncio
import os
import random
import socket
import string
from functools import cache
from typing import List, Optional, AsyncIterator, Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Body, Security
from fastapi.responses import StreamingResponse
import httpx

from anova_ble.client import AnovaBluetoothClient
from anova_wifi.device import DeviceState, AnovaDevice
from anova_wifi.manager import AnovaManager
from commands import SetWifiCredentials, SetServerInfo, GetIDCard, GetVersion, GetTemperatureUnit, GetSpeakerStatus, \
    SetSecretKey, SetTemperatureUnit, SetTargetTemperature, GetCurrentTemperature, SetTimer, StopTimer, ClearAlarm, \
    GetTimerStatus, GetTargetTemperature, TemperatureUnit, StartTimer
from .deps import get_device_manager, get_sse_manager, get_authenticated_device, get_settings, admin_auth
from .models import DeviceInfo, SetTemperatureResponse, SetTimerResponse, UnitResponse, SpeakerStatusResponse, \
    TimerResponse, BLEDevice, OkResponse, GetTargetTemperatureResponse, TemperatureResponse, NewSecretResponse, \
    BLEDeviceInfo, SSEEvent, SSEEventType, ServerInfo
from .settings import Settings
from .sse import SSEManager, event_stream

import logging

logger = logging.getLogger("anova_api")
logging.basicConfig(level=logging.INFO)

router = APIRouter()

# ----------- Normal Anova WiFi endpoints -----------
@router.get("/devices")
async def get_devices(
        manager: Annotated[AnovaManager, Depends(get_device_manager)],
        admin: Annotated[Optional[bool], Security(admin_auth)],
) -> List[DeviceInfo]:
    logger.info("Listing all devices")
    devices = manager.get_devices()
    return [
        DeviceInfo(
            id=device.id_card,
            version=device.version,
        )
        for device in devices if device.id_card
    ]


@router.get("/devices/{device_id}/state")
async def get_device_state(device: Annotated[AnovaDevice, Security(get_authenticated_device)]) -> DeviceState:
    logger.info(f"Get state for device {device.id_card}")
    return device.state


@router.post("/devices/{device_id}/target_temperature")
async def set_temperature(temperature: Annotated[float, Body(embed=True)],
                          device: Annotated[AnovaDevice, Security(get_authenticated_device)]) -> SetTemperatureResponse:
    logger.info(f"Set target temperature {temperature} for device {device.id_card}")
    resp = await device.send_command(SetTargetTemperature(temperature, device.state.unit))
    return SetTemperatureResponse(changed_to=resp)


@router.post("/devices/{device_id}/start")
async def start_cooking(device: Annotated[AnovaDevice, Security(get_authenticated_device)]) -> OkResponse:
    logger.info(f"Start cooking on device {device.id_card}")
    if not await device.start_cooking():
        logger.error("Failed to start cooking")
        raise ValueError("Failed to start cooking")
    return "ok"


@router.post("/devices/{device_id}/stop")
async def stop_cooking(device: Annotated[AnovaDevice, Security(get_authenticated_device)]) -> OkResponse:
    logger.info(f"Stop cooking on device {device.id_card}")
    if not await device.stop_cooking():
        logger.error("Failed to stop cooking")
        raise ValueError("Failed to stop cooking")
    return "ok"


@router.post("/devices/{device_id}/timer")
async def set_timer(minutes: Annotated[int, Body(embed=True)],
                    device: Annotated[AnovaDevice, Security(get_authenticated_device)]) -> SetTimerResponse:
    logger.info(f"Set timer {minutes} min for device {device.id_card}")
    return SetTimerResponse(message="Timer set successfully", minutes=await device.send_command(SetTimer(minutes)))


@router.post("/devices/{device_id}/timer/start")
async def start_timer(device: Annotated[AnovaDevice, Security(get_authenticated_device)]) -> OkResponse:
    logger.info(f"Start timer on device {device.id_card}")
    if not await device.send_command(StartTimer()):
        logger.error("Failed to start timer")
        raise ValueError("Failed to start timer")
    return "ok"


@router.post("/devices/{device_id}/timer/stop")
async def stop_timer(device: Annotated[AnovaDevice, Security(get_authenticated_device)]) -> OkResponse:
    logger.info(f"Stop timer on device {device.id_card}")
    if not await device.send_command(StopTimer()):
        logger.error("Failed to stop timer")
        raise ValueError("Failed to stop timer")
    return "ok"


@router.post("/devices/{device_id}/alarm/clear")
async def clear_alarm(device: Annotated[AnovaDevice, Security(get_authenticated_device)]) -> OkResponse:
    logger.info(f"Clear alarm on device {device.id_card}")
    if not await device.send_command(ClearAlarm()):
        logger.error("Failed to clear alarm")
        raise ValueError("Failed to clear alarm")
    return "ok"


@router.get("/devices/{device_id}/temperature")
async def get_temperature(device: Annotated[AnovaDevice, Security(get_authenticated_device)],
                          from_state: bool = True) -> TemperatureResponse:
    logger.info(f"Get temperature for device {device.id_card}")
    if from_state:
        return TemperatureResponse(temperature=device.state.current_temperature)
    return TemperatureResponse(temperature=await device.send_command(GetCurrentTemperature()))


@router.get("/devices/{device_id}/target_temperature")
async def get_target_temperature(device: Annotated[AnovaDevice, Security(get_authenticated_device)],
                                 from_state: bool = True) -> GetTargetTemperatureResponse:
    logger.info(f"Get target temperature for device {device.id_card}")
    if from_state:
        return GetTargetTemperatureResponse(temperature=device.state.target_temperature)
    return GetTargetTemperatureResponse(temperature=await device.send_command(GetTargetTemperature()))


@router.get("/devices/{device_id}/unit")
async def get_unit(device: Annotated[AnovaDevice, Security(get_authenticated_device)],
                   from_state: bool = True) -> UnitResponse:
    logger.info(f"Get unit for device {device.id_card}")
    if from_state:
        return UnitResponse(unit=device.state.unit)
    return UnitResponse(unit=await device.send_command(GetTemperatureUnit()))


@router.post("/devices/{device_id}/unit")
async def set_unit(unit: Annotated[TemperatureUnit, Body(embed=True)],
                   device: Annotated[AnovaDevice, Security(get_authenticated_device)]) -> OkResponse:
    logger.info(f"Set unit {unit} for device {device.id_card}")
    await device.send_command(SetTemperatureUnit(unit))
    return "ok"


@router.get("/devices/{device_id}/timer")
async def get_timer(device: Annotated[AnovaDevice, Security(get_authenticated_device)],
                    from_state: bool = True) -> TimerResponse:
    logger.info(f"Get timer for device {device.id_card}")
    if from_state:
        return TimerResponse(timer=device.state.timer_value)
    return TimerResponse(timer=await device.send_command(GetTimerStatus()))


@router.get("/devices/{device_id}/speaker_status")
async def get_speaker_status(device: Annotated[AnovaDevice, Security(get_authenticated_device)],
                             from_state: bool = True) -> SpeakerStatusResponse:
    logger.info(f"Get speaker status for device {device.id_card}")
    return SpeakerStatusResponse(speaker_status=await device.send_command(GetSpeakerStatus()))


@router.get("/devices/{device_id}/sse", response_model=SSEEvent, response_class=StreamingResponse)
async def sse_endpoint(
        request: Request,
        device: Annotated[AnovaDevice, Security(get_authenticated_device)],
        sse_manager: Annotated[SSEManager, Depends(get_sse_manager)],
) -> StreamingResponse:
    listener_id, queue = await sse_manager.connect(device.id_card)  # type: ignore

    async def event_generator() -> AsyncIterator[SSEEvent]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    async with asyncio.timeout(1.0):
                        event = await queue.get()
                        yield event
                except asyncio.TimeoutError:
                    yield SSEEvent(event_type=SSEEventType.ping)
        finally:
            await sse_manager.disconnect(device.id_card, listener_id)  # type: ignore

    logger.info(f"SSE started for device {device.id_card}")
    return StreamingResponse(event_stream(event_generator()), media_type="text/event-stream")


@cache
def get_local_host() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('10.255.255.255', 1))
    host = s.getsockname()[0]
    s.close()
    return host


@router.get("/server_info")
async def get_server_info(
        manager: Annotated[AnovaManager, Depends(get_device_manager)],
        settings: Annotated[Settings, Depends(get_settings)],
) -> ServerInfo:
    logger.info("Get server info endpoint hit")
    host = settings.server_host or get_local_host()
    port = manager.server.port
    return ServerInfo(host=host, port=port)

# ---- BLE PROXY ADAPTER ----

def get_ble_proxy_url():
    base = os.environ.get("BLE_PROXY_URL", "http://localhost:5000")
    url = base.rstrip("/")
    if not url.endswith("/scan"):
        url += "/scan"
    return url

def get_ble_proxy_write_url():
    base = os.environ.get("BLE_PROXY_URL", "http://localhost:5000")
    url = base.rstrip("/")
    if not url.endswith("/write"):
        url += "/write"
    return url

async def proxy_ble_scan():
    url = get_ble_proxy_url()
    logger.info(f"Scanning BLE proxy: {url}")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
            if not data:
                logger.error("No BLE device found in proxy BLE scan.")
                return None, None
            dev = type('BLEDev', (), {})()
            adv = type('BLEAdv', (), {})()
            dev.address = data[0].get("address")
            adv.local_name = data[0].get("name")
            logger.info(f"Found BLE device at {dev.address} ({adv.local_name})")
            return dev, adv
    except Exception as e:
        logger.error(f"BLE-proxy not reachable: {e}")
        raise HTTPException(status_code=503, detail=f"BLE-proxy niet bereikbaar: {str(e)}")

async def proxy_ble_write(address, command) -> str:
    url = get_ble_proxy_write_url()
    logger.info(f"Proxy BLE write: address={address}, command={command!r}, url={url}")
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json={
                "address": address,
                "command": command
            }, timeout=15)
            r.raise_for_status()
            data = r.json()
            logger.info(f"Proxy BLE write result: {data}")
            return data.get("result") or data.get("response", "")
    except Exception as e:
        logger.error(f"BLE-proxy write failed: {e}")
        raise HTTPException(status_code=503, detail=f"BLE-proxy write failed: {str(e)}")

async def _ble_proxy_command(dev, command):
    try:
        if hasattr(command, "encode"):
            command_str = command.encode()
        elif isinstance(command, str):
            command_str = command
        else:
            logger.error("Unsupported command type for BLE proxy")
            raise HTTPException(status_code=500, detail="Unsupported command type for BLE proxy")
        logger.info(f"BLE proxy command: device={getattr(dev, 'address', None)}, command={command_str!r}")
        response = await proxy_ble_write(dev.address, command_str)
        logger.info(f"BLE proxy command response: {response!r}")
        return response.strip()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal BLE proxy error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal BLE proxy error: {str(e)}")

# BLE endpoints via BLE proxy

@router.get("/ble/device")
async def get_ble_device(admin: Annotated[Optional[bool], Security(admin_auth)]) -> BLEDevice:
    dev, adv = await proxy_ble_scan()
    if not dev or not adv or not dev.address:
        logger.error("No BLE device found (get_ble_device)")
        raise HTTPException(status_code=404, detail="No BLE device found")
    return BLEDevice(address=dev.address, name=getattr(adv, "local_name", None))

@router.post("/ble/connect_wifi")
async def ble_connect_wifi(
        ssid: Annotated[str, Body(embed=True)],
        password: Annotated[str, Body(embed=True)]
) -> OkResponse:
    dev, adv = await proxy_ble_scan()
    if not dev or not dev.address:
        logger.error("No BLE device found (connect_wifi)")
        raise HTTPException(status_code=404, detail="No BLE device found")
    await _ble_proxy_command(dev, SetWifiCredentials(ssid, password))
    return 'ok'

@router.post("/ble/config_wifi_server")
async def patch_ble_device(
        admin: Annotated[Optional[bool], Security(admin_auth)],
        manager: Annotated[AnovaManager, Depends(get_device_manager)],
        settings: Annotated[Settings, Depends(get_settings)],
        host: Annotated[Optional[str], Body(
            embed=True,
            description="The IP address of the server."
                        "If not provided, the local IP address will be determined automatically"
        )] = None,
        port: Annotated[Optional[int], Body(
            embed=True,
            description="The port of the server. If not provided, port of the server will be used"
        )] = None
) -> OkResponse:
    dev, adv = await proxy_ble_scan()
    if not dev or not dev.address:
        logger.error("No BLE device found (config_wifi_server)")
        raise HTTPException(status_code=404, detail="No BLE device found")
    host = host or settings.server_host or get_local_host()
    port = port or manager.server.port
    logger.info(f"Configuring BLE wifi server: host={host}, port={port}")
    await _ble_proxy_command(dev, SetServerInfo(host, port))
    return 'ok'

@router.post("/ble/restore_wifi_server")
async def restore_ble_device(admin: Annotated[Optional[bool], Security(admin_auth)]) -> OkResponse:
    dev, adv = await proxy_ble_scan()
    if not dev or not dev.address:
        logger.error("No BLE device found (restore_wifi_server)")
        raise HTTPException(status_code=404, detail="No BLE device found")
    await _ble_proxy_command(dev, SetServerInfo())
    return 'ok'

@router.get("/ble/")
async def ble_get_info(admin: Annotated[Optional[bool], Security(admin_auth)]) -> BLEDeviceInfo:
    dev, adv = await proxy_ble_scan()
    if not dev or not dev.address:
        logger.error("No BLE device found (ble_get_info)")
        raise HTTPException(status_code=404, detail="No BLE device found")
    id_card = await _ble_proxy_command(dev, GetIDCard())
    ver = await _ble_proxy_command(dev, GetVersion())
    unit = await _ble_proxy_command(dev, GetTemperatureUnit())
    speaker = await _ble_proxy_command(dev, GetSpeakerStatus())
    return BLEDeviceInfo(
        ble_address=dev.address,
        ble_name=getattr(adv, "local_name", None),
        version=ver,
        id_card=id_card,
        temperature_unit=unit,
        speaker_status=speaker
    )

@router.post("/ble/secret_key")
async def ble_new_secret_key(admin: Annotated[Optional[bool], Security(admin_auth)]) -> NewSecretResponse:
    dev, adv = await proxy_ble_scan()
    if not dev or not dev.address:
        logger.error("No BLE device found (secret_key)")
        raise HTTPException(status_code=404, detail="No BLE device found")
    characters = string.ascii_lowercase + string.digits
    secret_key = ''.join(random.choice(characters) for _ in range(10))
    logger.info(f"Setting new BLE secret key: {secret_key}")
    await _ble_proxy_command(dev, SetSecretKey(secret_key))
    return NewSecretResponse(secret_key=secret_key)
