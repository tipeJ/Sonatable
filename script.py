import sys
from neopixel import Neopixel
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
from machine import Pin, Timer
from debounce import DebouncedSwitch

class NeopixelConfigurationInterface:
    def __init__(self):
        self.PIN = Pin(4)
        self.NUM_PIXELS = 0
        self.NP = NeoPixel(self.NUM_PIXELS, 0, 0, "RGBW")

    @staticmethod
    def from_json(json):
        pass

    def setup(self):
        pass

    async def loop(self):
        pass

class NeopixelSingleColorConfiguration(NeopixelConfigurationInterface):
    def __init__(self, color):
        self.color = color
        super().__init__()

    @staticmethod
    def from_json(json):
        return NeopixelSingleColorConfiguration(
            (json["color"][0], json["color"][1], json["color"][2], json["color"][3])
        )

    def setup(self):
        self.NP.fill(self.color)
        self.NP.write()

class NeopixelGradientConfiguration(NeopixelConfigurationInterface):
    def __init__(self, color1, color2, steps=50, wait_ms=50):
        self.color1 = color1
        self.color2 = color2
        self.steps = steps
        self.wait_ms = wait_ms
        super().__init__()

    @staticmethod
    def from_json(json):
        return NeopixelGradientConfiguration(
            neopixel.Color(json["color1"][0], json["color1"][1], json["color1"][2]),
            neopixel.Color(json["color2"][0], json["color2"][1], json["color2"][2]),
            json["steps"],
            json["wait_ms"],
        )

    def setup(self):
        self.NP.fill(self.color1)
        self.NP.write()

    async def loop(self):
        # Color shift the fill to the other color, one step at a time. After the last step, start over.
        while True:
            for i in range(self.steps):
                self.NP.fill(self.color1.lerp(self.color2, i / self.steps))
                self.NP.write()
                await asyncio.sleep_ms(self.wait_ms)
            for i in range(self.steps):
                self.NP.fill(self.color2.lerp(self.color1, i / self.steps))
                self.NP.write()
                await asyncio.sleep_ms(self.wait_ms)

_MODE_SERVICE_UUID = bluetooth.UUID('f7d9c9d1-9c3d-4c9e-9c8d-9c8d9c8d9c8d')
_MODE_CHAR_UUID = bluetooth.UUID('f7d9c9d2-9c3d-4c9e-9c8d-9c8d9c8d9c8d')
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

_GENERIC = bluetooth.UUID(0x1848)
_BLE_APPEARANCE_GENERIC_REMOTE_CONTROL = const(384)

_NOTIFY_ENABLE = const(1)
_INDICATE_ENABLE = const(2)

ble = bluetooth.BLE()

# How frequently to send advertising beacons.
_ADV_INTERVAL_MS = 250_000

# Modes for the buttons.
KUUNAPPI_MODE_SOUNDBOARD = const(0)
KUUNAPPI_MODE_LIGHT = const(1)

current_kuunappi_mode = KUUNAPPI_MODE_SOUNDBOARD
current_neopixel_mode = None
current_neopixel_identifier = None
led = Pin(14, Pin.OUT)
led2 = Pin(15, Pin.OUT)
phototransistor = Pin(7, Pin.OUT)
is_connected = False
bt_connection = None


# Register service
mode_service = aioble.Service(_MODE_SERVICE_UUID)
mode_characteristic = aioble.Characteristic(
    mode_service, _MODE_CHAR_UUID, write=True, read=True, notify=True)
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
    
aioble.register_services(mode_service, neopixel_service, buttons_service)

# ! Neopixel stuff
async def neopixel_task(connection):
    global current_neopixel_mode, is_connected, current_neopixel_identifier
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
        if (light_class == "solid"):
            current_neopixel_mode = NeopixelSingleColorConfiguration.from_json(new_mode)
        else:
            current_neopixel_mode = NeopixelGradientConfiguration.from_json(new_mode)
        print("Mode changed to", new_mode)


# ! Moon Mode stuff
# Encode the mode message from int to bytes
def _encode_mode(mode):
    return mode.to_bytes(4, "little")

def decode_mode(data):
    # Decode bytes to int
    return int.from_bytes(data, "little")

# Read the ch
async def mode_task(connection):
    global current_kuunappi_mode, is_connected, current_neopixel_identifier, current_neopixel_mode
    if not is_connected:
        await asyncio.sleep_ms(1000)
        return
    # Check if the mode has changed.
    new_mode = mode_characteristic.read()
    new_mode = decode_mode(new_mode)
    if new_mode != current_kuunappi_mode:
        current_kuunappi_mode = new_mode
        led.toggle()
        print("Mode changed to", new_mode)

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
    
# Looping task
async def conn_task(connection):
    global current_kuunappi_mode, is_connected
    if is_connected:
        # Initial write
        mode_characteristic.write(_encode_mode(current_kuunappi_mode))
    while True:
        await mode_task(connection)
        await neopixel_task(connection)
        await asyncio.sleep_ms(20)

# Serially wait for connections. Don't advertise while a central is
# connected.
async def peripheral_task():
    global is_connected, bt_connection
    while True:
        async with await aioble.advertise(
            _ADV_INTERVAL_MS,
            name="Sonatable",
            services=[_MODE_SERVICE_UUID],
            appearance=_BLE_APPEARANCE_GENERIC_REMOTE_CONTROL,
        ) as connection:
            print("Connection from", connection.device)
            # Override BLE MTU
            aioble.config(mtu=256)
            bt_connection = connection
            # Print out all the descriptors for the button characteristics
            for characteristic in button_characteristics:
                print(characteristic)
            connection.exchange_mtu(256)
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
    await peripheral_task()


asyncio.run(main())