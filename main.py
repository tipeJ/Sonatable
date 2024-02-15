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
import ds18x20 as ds # Temperature sensor
import onewire
from machine import Pin
from debounce import DebouncedSwitch
from patterns import NeopixelConfigurationInterface, NeopixelSingleColorConfiguration, NeopixelGradientPulseConfiguration, Rainbow


NEOPIXEL_SERVICE_UUID = bluetooth.UUID("f7d9c9d3-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
NEOPIXEL_COLOR_CHAR_UUID = bluetooth.UUID("f7d9c9d4-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
BUTTONS_SERVICE_UUID = bluetooth.UUID("f7d9c9d5-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
BUTTONS_1_CHAR_UUID = bluetooth.UUID("f7d9c9d6-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
TEMPERATURE_CHAR_UUID = bluetooth.UUID("f7d9c9d7-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
TEMPERATURE_SERVICE_UUID = bluetooth.UUID("f7d9c9d8-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
# BUTTONS_4_CHAR_UUID = bluetooth.UUID("f7d9c9d9-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
# BUTTONS_5_CHAR_UUID = bluetooth.UUID("f7d9c9da-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
# BUTTONS_6_CHAR_UUID = bluetooth.UUID("f7d9c9db-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
# BUTTONS_7_CHAR_UUID = bluetooth.UUID("f7d9c9dc-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
CONTROLS_SERVICE_UUID = bluetooth.UUID("f7d9c9dd-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
CONTROLS_MODE_CHAR_UUID = bluetooth.UUID('f7d9c9d2-9c3d-4c9e-9c8d-9c8d9c8d9c8d')
CONTROLS_POWERBUTTON_CHAR_UUID = bluetooth.UUID("f7d9c9de-9c3d-4c9e-9c8d-9c8d9c8d9c8d")
CONTROLS_BRIGHTNESS_CHANGE_CHAR = bluetooth.UUID("f7d9c9df-9c3d-4c9e-9c8d-9c8d9c8d9c8d")

_GENERIC = bluetooth.UUID(0x1848)
_BLE_APPEARANCE_GENERIC_REMOTE_CONTROL = const(384)

SCREEN_BUITTON_FREQUENCY = const(1000)
SCREEN_LATEST_BOOT_TIME = machine.RTC().datetime()
SCREEN_MIN_DELAY_BETWEEN_BOOT = const(5)
SCREEN_IS_POWERED_ON = False
BRIGHTNESS_LEVELS = const(25)
POWERBUTTON_PIN = Pin(15, mode=Pin.OUT, value=0, pull=Pin.PULL_UP)
BRIGHT_UP_PIN = Pin(26, mode=Pin.OUT, value=0, pull=Pin.PULL_UP)
BRIGHT_DOWN_PIN = Pin(27, mode=Pin.OUT, value=0, pull=Pin.PULL_UP)
LEDSTRIP_PIN = const(22)

# Moon Buttons
MOON_BUTTON_1_PIN = Pin(2, mode=Pin.IN, pull=Pin.PULL_UP)
MOON_BUTTON_2_PIN = Pin(3, mode=Pin.IN, pull=Pin.PULL_UP)
MOON_BUTTON_3_PIN = Pin(4, mode=Pin.IN, pull=Pin.PULL_UP)
MOON_BUTTON_4_PIN = Pin(5, mode=Pin.IN, pull=Pin.PULL_UP)
MOON_BUTTON_5_PIN = Pin(6, mode=Pin.IN, pull=Pin.PULL_UP)
MOON_BUTTON_6_PIN = Pin(7, mode=Pin.IN, pull=Pin.PULL_UP)
MOON_BUTTON_7_PIN = Pin(8, mode=Pin.IN, pull=Pin.PULL_UP)

REED_PIN = Pin(0, mode=Pin.IN, value=1, pull=Pin.PULL_UP)
THERMOMETER_PIN = Pin(10)
THERMOMETER_SENSOR = ds.DS18X20(onewire.OneWire(THERMOMETER_PIN))
THERMOMETER_ROMS = THERMOMETER_SENSOR.scan()

ble = bluetooth.BLE()

# How frequently to send advertising beacons.
_ADV_INTERVAL_MS = 250_000

# Modes for the buttons.
KUUNAPPI_MODE_SOUNDBOARD = const(0)
KUUNAPPI_MODE_CONTROLS_AND_LED = const(1)

current_kuunappi_mode = KUUNAPPI_MODE_CONTROLS_AND_LED


current_neopixel_pattern = None
current_neopixel_identifier = None
latest_neopixel_ble_update = None
static_board_neopixel_pattern = NeopixelSingleColorConfiguration((255, 0, 0, 0))
led = Pin(1, Pin.OUT)
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
buttons_characteristic = aioble.Characteristic(buttons_service, BUTTONS_1_CHAR_UUID, notify=True)
temperature_service = aioble.Service(TEMPERATURE_SERVICE_UUID)
temperature_characteristic = aioble.Characteristic(temperature_service, TEMPERATURE_CHAR_UUID, notify=True)

# Write a 256 byte buffer to the characteristic.
sample = bytearray(256)
for i in range(256):
    sample[i] = i
neopixel_setting_characteristic.write(sample)
neopixel_loop_task = None # asyncio task
    
aioble.register_services(neopixel_service, controls_service, buttons_service, temperature_service)

# ! Generic utilities
async def create_short_pin_pulse(pin, duration):
    pin.value(1)
    await asyncio.sleep_ms(duration)
    pin.value(0)

def get_neopixel_config_from_json(json) -> NeopixelConfigurationInterface:
    light_class = json["mode"]
    if (light_class == "solid"):
        return NeopixelSingleColorConfiguration.from_json(json)
    elif (light_class == 'rainbow'):
        return Rainbow.from_json(json)
    else:
        return NeopixelGradientPulseConfiguration.from_json(json)

# ! Neopixel stuff
async def neopixel_task():
    global current_neopixel_pattern, current_neopixel_identifier, neopixel_loop_task
    previous_neopixel_identifier = None
    while True:
        if current_neopixel_identifier != previous_neopixel_identifier:
            # Update
            previous_neopixel_identifier = current_neopixel_identifier
            if current_neopixel_identifier is not None:
                # Start the loop, terminate the previous one if it exists.
                if neopixel_loop_task is not None:
                    neopixel_loop_task.cancel()
                    if current_neopixel_pattern is not None:
                        await current_neopixel_pattern.terminate()
                if current_neopixel_identifier == 'STATIC':
                    await static_board_neopixel_pattern.setup()
                    loop = asyncio.get_event_loop()
                    neopixel_loop_task = loop.create_task(static_board_neopixel_pattern.loop())
                else:
                    try:
                        current_neopixel_pattern = get_neopixel_config_from_json(current_neopixel_identifier)
                        await current_neopixel_pattern.setup()
                        loop = asyncio.get_event_loop()
                        neopixel_loop_task = loop.create_task(current_neopixel_pattern.loop())
                    except Exception as e:
                        print("Error:", e)
                        return
        await asyncio.sleep_ms(200)

async def neopixel_task_BLE(connection):
    global current_neopixel_pattern, is_connected, current_neopixel_identifier, latest_neopixel_ble_update
    if not is_connected:
        await asyncio.sleep_ms(1000)
        return
    # Check if the mode has changed.
    new_mode = neopixel_setting_characteristic.read()
    if latest_neopixel_ble_update is None or new_mode != latest_neopixel_ble_update:
        latest_neopixel_ble_update = new_mode
        try:
            # Check if valid JSON
            new_mode = json.loads(new_mode)
        except Exception as e:
            print("BLE Error:", e)
            await asyncio.sleep_ms(1000)
            return
        current_neopixel_identifier = new_mode

# ! Buttons stuff
def button_clicked(index):
    global led, bt_connection, current_kuunappi_mode, static_board_neopixel_pattern, current_neopixel_identifier
    print("Button clicked", index)
    if (current_kuunappi_mode == KUUNAPPI_MODE_CONTROLS_AND_LED): # If the mode is controls and led, no need for BT connection.
        # Buttons 1-3 are for screen buttons, 4-7 are for RGBW switching for static colors.
        if (index == 0): # Powerbutton
            asyncio.create_task(handle_powerbutton_click())
        elif (index == 1): # Brightness down
            asyncio.create_task(create_short_pin_pulse(BRIGHT_DOWN_PIN, 100))
        elif (index == 2): # Brightness up
            asyncio.create_task(create_short_pin_pulse(BRIGHT_UP_PIN, 100))
        elif (index == 3): # LEDS: RED
            # Increase the brightness of the red LEDs by 25
            static_board_neopixel_pattern.increase_color_for_channel(0, 25)
            current_neopixel_identifier = 'STATIC'
        elif (index == 4): # LEDS: GREEN
            # Increase the brightness of the green LEDs by 25
            static_board_neopixel_pattern.increase_color_for_channel(1, 25)
            current_neopixel_identifier = 'STATIC'
        elif (index == 5): # LEDS: BLUE
            # Increase the brightness of the blue LEDs by 25
            static_board_neopixel_pattern.increase_color_for_channel(2, 25)
            current_neopixel_identifier = 'STATIC'
        elif (index == 6): # LEDS: WHITE
            # Increase the brightness of the white LEDs by 25
            static_board_neopixel_pattern.increase_color_for_channel(3, 25)
            current_neopixel_identifier = 'STATIC'
    else: # Send the button click to the device
        # Get the characteristic
        characteristic = buttons_characteristic
        characteristic.notify(bt_connection, str(index))

# ! Controls stuff
# Set the screen brightness. If max/min, increase/decrease for all possible levels. If +1/-1, increase/decrease by one level.
async def handle_brightness_change(connection, value):
    if (value == "+1"):
        await create_short_pin_pulse(BRIGHT_UP_PIN, 100)
    elif (value == "-1"):
        await create_short_pin_pulse(BRIGHT_DOWN_PIN, 100)
    elif (value == "max"):
        for i in range(BRIGHTNESS_LEVELS):
            await create_short_pin_pulse(BRIGHT_UP_PIN, 100)
    elif (value == "min"):
        for i in range(BRIGHTNESS_LEVELS):
            await create_short_pin_pulse(BRIGHT_DOWN_PIN, 100)

async def handle_powerbutton_click():
    global SCREEN_IS_POWERED_ON, SCREEN_LATEST_BOOT_TIME, SCREEN_MIN_DELAY_BETWEEN_BOOT
    # Check if the screen has been booted recently, if so, ignore the powerbutton click.
    current_time = machine.RTC().datetime()
    # Take the second to last value, which is the seconds
    current_time = current_time[6]
    # If the difference between the current time and the latest boot time is less than the minimum delay, ignore the powerbutton click.
    # if (current_time - SCREEN_LATEST_BOOT_TIME) < SCREEN_MIN_DELAY_BETWEEN_BOOT:
    #     return
    SCREEN_IS_POWERED_ON = not SCREEN_IS_POWERED_ON
    SCREEN_LATEST_BOOT_TIME = current_time
    # Toggle the powerbutton
    await create_short_pin_pulse(POWERBUTTON_PIN, 100)

# Encode the mode message from int to bytes
def _encode_mode(mode):
    return mode.to_bytes(4, "little")

def decode_mode(data):
    # Decode bytes to int
    return int.from_bytes(data, "little")

# ! REED poweron
def handle_reed_trigger(*args, **kwargs):
    print("Reed triggered", led.value())
    # Is the device already on..?
    # Turn led on/off
    led.value(not led.value())


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
        await neopixel_task_BLE(connection)
        await controls_task()
        await asyncio.sleep_ms(20)

async def thermometer_task():
    global is_connected, bt_connection
    while True:
        await asyncio.sleep_ms(1000)
        if is_connected:
            try:
                for rom in THERMOMETER_ROMS:
                    THERMOMETER_SENSOR.convert_temp()
                    await asyncio.sleep_ms(100)
                    temperature = THERMOMETER_SENSOR.read_temp(rom)
                    print("Temperature:", temperature)
                    # Send the temperature to the central
                    temperature_characteristic.notify(bt_connection, str(temperature))
            except Exception as e:
                print("Error handling thermometer data:", e)

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
            conn_t = loop.create_task(conn_task(connection))
            therm_t = loop.create_task(thermometer_task())
            await connection.disconnected()
            print("Disconnected")
            is_connected = False
            # Remove tasks
            try:
                conn_t.cancel()
                therm_t.cancel()
            except Exception as e:
                print("Error cancelling tasks:", e)


# Run both tasks.
async def main():
    button_sw_1 = DebouncedSwitch(MOON_BUTTON_1_PIN, button_clicked, 0, 150)
    button_sw_2 = DebouncedSwitch(MOON_BUTTON_2_PIN, button_clicked, 1, 150)
    button_sw_3 = DebouncedSwitch(MOON_BUTTON_3_PIN, button_clicked, 2, 150)
    button_sw_4 = DebouncedSwitch(MOON_BUTTON_4_PIN, button_clicked, 3, 150)
    button_sw_5 = DebouncedSwitch(MOON_BUTTON_5_PIN, button_clicked, 4, 150)
    button_sw_6 = DebouncedSwitch(MOON_BUTTON_6_PIN, button_clicked, 5, 150)
    button_sw_7 = DebouncedSwitch(MOON_BUTTON_7_PIN, button_clicked, 6, 150)
    reed_sw = DebouncedSwitch(REED_PIN, handle_reed_trigger, delay=200)
    asyncio.get_event_loop().create_task(neopixel_task())
    asyncio.get_event_loop().create_task(peripheral_task())
    asyncio.get_event_loop().run_forever()


asyncio.run(main()) 