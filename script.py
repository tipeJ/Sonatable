import sys
sys.path.append("")
from micropython import const
import micropython as mipy
import uasyncio as asyncio
import aioble
import bluetooth
import random
import struct
import json
import machine
from machine import Pin, PWM
from debounce import DebouncedSwitch
from patterns import NeopixelConfigurationInterface, NeopixelSingleColorConfiguration, NeopixelGradientPulseConfiguration, Rainbow


NEOPIXEL_SERVICE_UUID = bluetooth.UUID("f7d9c9d3-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
NEOPIXEL_COLOR_CHAR_UUID = bluetooth.UUID("f7d9c9d4-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
BUTTONS_SERVICE_UUID = bluetooth.UUID("f7d9c9d5-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
BUTTONS_1_CHAR_UUID = bluetooth.UUID("f7d9c9d6-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
BUTTONS_2_CHAR_UUID = bluetooth.UUID("f7d9c9d7-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
BUTTONS_3_CHAR_UUID = bluetooth.UUID("f7d9c9d8-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
BUTTONS_4_CHAR_UUID = bluetooth.UUID("f7d9c9d9-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
BUTTONS_5_CHAR_UUID = bluetooth.UUID("f7d9c9da-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
BUTTONS_6_CHAR_UUID = bluetooth.UUID("f7d9c9db-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
BUTTONS_7_CHAR_UUID = bluetooth.UUID("f7d9c9dc-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
CONTROLS_SERVICE_UUID = bluetooth.UUID("f7d9c9dd-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
CONTROLS_MODE_CHAR_UUID = bluetooth.UUID('f7d9c9d2-9c3d-4c9e-9c8d-9c8d9c8d9c8d')
CONTROLS_POWERBUTTON_CHAR_UUID = bluetooth.UUID("f7d9c9de-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
CONTROLS_BRIGHTNESS_CHANGE_CHAR = bluetooth.UUID("f7d9c9df-9c3d-4c9e-9c8d-9c8d9c8d9c8d")

_GENERIC = bluetooth.UUID(0x1848)
_BLE_APPEARANCE_GENERIC_REMOTE_CONTROL = const(384)

SCREEN_BUITTON_FREQUENCY = const(1000)
SCREEN_IS_POWERED_ON = False
BRIGHTNESS_LEVELS = const(15)
POWERBUTTON_PIN = Pin(22)
BRIGHT_UP_PIN = Pin(26)
BRIGHT_DOWN_PIN = Pin(27)
POWERBUTTON_PVM = PWM(POWERBUTTON_PIN, SCREEN_BUITTON_FREQUENCY)
BRIGHT_UP_PVM = PWM(BRIGHT_UP_PIN, SCREEN_BUITTON_FREQUENCY)
BRIGHT_DOWN_PVM = PWM(BRIGHT_DOWN_PIN, SCREEN_BUITTON_FREQUENCY)

REED_PIN = Pin(4, Pin.IN, Pin.PULL_UP)

ble = bluetooth.BLE()

# How frequently to send advertising beacons.
_ADV_INTERVAL_MS = 250_000

# Modes for the buttons.
KUUNAPPI_MODE_SOUNDBOARD = const(0)
KUUNAPPI_MODE_LIGHT = const(1)

current_kuunappi_mode = KUUNAPPI_MODE_SOUNDBOARD
current_neopixel_pattern = None
current_neopixel_identifier = None
led = Pin(14, Pin.OUT)
led2 = Pin(15, Pin.OUT)
phototransistor = Pin(7, Pin.OUT)
is_connected = False
bt_connection = None


# Register service
controls_service = aioble.Service(CONTROLS_SERVICE_UUID)
controls_powerbutton_characteristic = aioble.Characteristic(controls_service, CONTROLS_POWERBUTTON_CHAR_UUID, write=True, read=True)
controls_brightness_change_characteristic = aioble.Characteristic(controls_service, CONTROLS_BRIGHTNESS_CHANGE_CHAR, write=True, read=True)
mode_characteristic = aioble.Characteristic(
    controls_service, CONTROLS_MODE_CHAR_UUID, write=True, read=True, notify=True)
neopixel_service = aioble.Service(NEOPIXEL_SERVICE_UUID)
neopixel_setting_characteristic = aioble.Characteristic(neopixel_service, NEOPIXEL_COLOR_CHAR_UUID, write=True, read=True)
buttons_service = aioble.Service(BUTTONS_SERVICE_UUID)
buttons_1_characteristic = aioble.Characteristic(buttons_service, BUTTONS_1_CHAR_UUID, notify=True)
buttons_2_characteristic = aioble.Characteristic(buttons_service, BUTTONS_2_CHAR_UUID, notify=True)
buttons_3_characteristic = aioble.Characteristic(buttons_service, BUTTONS_3_CHAR_UUID, notify=True)
buttons_4_characteristic = aioble.Characteristic(buttons_service, BUTTONS_4_CHAR_UUID, notify=True)
buttons_5_characteristic = aioble.Characteristic(buttons_service, BUTTONS_5_CHAR_UUID, notify=True)
buttons_6_characteristic = aioble.Characteristic(buttons_service, BUTTONS_6_CHAR_UUID, notify=True)
buttons_7_characteristic = aioble.Characteristic(buttons_service, BUTTONS_7_CHAR_UUID, notify=True)
button_characteristics = [buttons_1_characteristic, buttons_2_characteristic, buttons_3_characteristic, buttons_4_characteristic, buttons_5_characteristic, buttons_6_characteristic, buttons_7_characteristic]

# Write a 256 byte buffer to the characteristic.
sample = bytearray(256)
for i in range(256):
    sample[i] = i
neopixel_setting_characteristic.write(sample)
neopixel_loop_task = None # asyncio task
    
aioble.register_services(neopixel_service, controls_service, buttons_service)

# ! Generic utilities

async def create_pvm_short_pulse(pwm, duration):
    pwm.duty(512)
    await asyncio.sleep_ms(duration)
    pwm.duty(0)

def get_neopixel_config_from_json(json) -> NeopixelConfigurationInterface:
    light_class = json["mode"]
    if (light_class == "solid"):
        return NeopixelSingleColorConfiguration.from_json(json)
    elif (light_class == 'rainbow'):
        return Rainbow.from_json(json)
    else:
        return NeopixelGradientPulseConfiguration.from_json(json)

# ! Neopixel stuff
async def neopixel_task(connection):
    global current_neopixel_pattern, is_connected, current_neopixel_identifier, neopixel_loop_task
    if not is_connected:
        await asyncio.sleep_ms(1000)
        return
    # Check if the mode has changed.
    new_mode = neopixel_setting_characteristic.read()
    if current_neopixel_identifier is None:
        current_neopixel_identifier = new_mode
    elif new_mode != current_neopixel_identifier:
        print(new_mode)
        current_neopixel_identifier = new_mode
        # Decode bytes to json
        new_mode = new_mode.decode("utf-8")
        new_mode = json.loads(new_mode)
        # Parse the class from the json parameter "mode"
        light_class = new_mode["mode"]
        new_neopixel_pattern = get_neopixel_config_from_json(new_mode)
        print("Mode changed to", new_mode)
        # If neoixel loop task is running, cancel it.
        if neopixel_loop_task is not None:
            neopixel_loop_task.cancel()
            if current_neopixel_pattern is not None:
                # Activate the final state of the neopixel mode
                await current_neopixel_pattern.terminate()
        # Start the new task in the event loop
        current_neopixel_pattern = new_neopixel_pattern
        await current_neopixel_pattern.setup()
        loop = asyncio.get_event_loop()
        neopixel_loop_task = loop.create_task(current_neopixel_pattern.loop())

# ! Buttons stuff
def button_clicked(index):
    global led, phototransistor, bt_connection
    print("Button clicked", index)
    # Get the characteristic
    characteristic = button_characteristics[index]
    # Notify the characteristic, with current timestamp
    current_time = machine.RTC().datetime()
    # Take the second to last value, which is the seconds
    current_time = current_time[6]
    # Encode the time to bytes
    current_time = current_time.to_bytes(4, "little")
    print(bt_connection)
    characteristic.notify(bt_connection, str(current_time))
    
    return
    if (index == 1):
        led2.toggle()
        # phototransistor.toggle()
    else:
            led.toggle()

# ! Controls stuff
# Set the screen brightness. If max/min, increase/decrease for all possible levels. If +1/-1, increase/decrease by one level.
async def handle_brightness_change(connection, value):
    value = value.decode("utf-8")
    if (value == "+1"):
        await create_pvm_short_pulse(BRIGHT_UP_PVM, 100)
    elif (value == "-1"):
        await create_pvm_short_pulse(BRIGHT_DOWN_PVM, 100)
    elif (value == "max"):
        for i in range(BRIGHTNESS_LEVELS):
            await create_pvm_short_pulse(BRIGHT_UP_PVM, 100)
    elif (value == "min"):
        for i in range(BRIGHTNESS_LEVELS):
            await create_pvm_short_pulse(BRIGHT_DOWN_PVM, 100)

async def handle_powerbutton_click():
    global SCREEN_IS_POWERED_ON
    SCREEN_IS_POWERED_ON = not SCREEN_IS_POWERED_ON
    await create_pvm_short_pulse(POWERBUTTON_PVM, 100)

# Encode the mode message from int to bytes
def _encode_mode(mode):
    return mode.to_bytes(4, "little")

def decode_mode(data):
    # Decode bytes to int
    return int.from_bytes(data, "little")

# ! REED poweron
async def handle_reed_trigger():
    global SCREEN_IS_POWERED_ON
    # Is the device already on..?
    if not SCREEN_IS_POWERED_ON:
        await handle_powerbutton_click()

async def controls_task():
    global current_kuunappi_mode, is_connected, current_neopixel_identifier, current_neopixel_pattern
    if not is_connected:
        return
    # Listen to the controls powerbutton and brightness up/down characteristics.
    powerbutton = controls_powerbutton_characteristic.read()
    if powerbutton == b'\x01':
        print("Powerbutton pressed")
        # Reset the powerbutton state to 0 again
        controls_powerbutton_characteristic.write(b'\x00')
        await handle_powerbutton_click()
    brightness_change = controls_brightness_change_characteristic.read()
    if brightness_change != b'\x00' and brightness_change != b'':
        # Reset the brightness change state to 0 again
        controls_brightness_change_characteristic.write(b'\x00')
        #Decode the brightness change value string
        brightness_change = brightness_change.decode("utf-8")
        # Create a task to handle the brightness change
        loop = asyncio.get_event_loop()
        loop.create_task(handle_brightness_change(bt_connection, brightness_change))
    new_mode = mode_characteristic.read()
    new_mode = decode_mode(new_mode)
    if new_mode != current_kuunappi_mode:
        current_kuunappi_mode = new_mode
        led.toggle()
        print("Mode changed to", new_mode)
    
# Looping task
async def conn_task(connection):
    global current_kuunappi_mode, is_connected
    if is_connected:
        # Initial write
        mode_characteristic.write(_encode_mode(current_kuunappi_mode))
    while True:
        await neopixel_task(connection)
        await controls_task()
        await asyncio.sleep_ms(20)

# Serially wait for connections. Don't advertise while a central is
# connected.
async def peripheral_task():
    global is_connected, bt_connection
    while True:
        async with await aioble.advertise(
            _ADV_INTERVAL_MS,
            name="Sonatable",
            services=[CONTROLS_SERVICE_UUID],
            appearance=_BLE_APPEARANCE_GENERIC_REMOTE_CONTROL,
        ) as connection:
            print("Connection from", connection.device)
            # Override BLE MTU
            aioble.config(mtu=256)
            bt_connection = connection
            connection.exchange_mtu(512)
            is_connected = True
            loop = asyncio.get_event_loop()
            loop.create_task(conn_task(connection))
            loop.run_forever()
            await connection.disconnected()
            print("Disconnected")


# Run both tasks.
async def main():
    interrupt_test_pin = Pin(0, Pin.IN, Pin.PULL_UP)
    interrupt_test_pin2 = Pin(2, Pin.IN, Pin.PULL_UP)
    button_sw_1 = DebouncedSwitch(interrupt_test_pin, button_clicked, 0, 150)
    button_sw_2 = DebouncedSwitch(interrupt_test_pin2, button_clicked, 1, 150)
    reed_sw = DebouncedSwitch(REED_PIN, handle_reed_trigger, delay=150)
    await peripheral_task()


asyncio.run(main())