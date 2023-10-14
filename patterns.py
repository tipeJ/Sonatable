from neopixel import Neopixel
from machine import Pin
import uasyncio as asyncio
from color_utils import hsi2rgbw, RGBToRGBW, lerp

class NeopixelConfigurationInterface:
    def __init__(self):
        self.PIN = Pin(4)
        self.NUM_PIXELS = 0
        self.NP = Neopixel(self.NUM_PIXELS, 0, 0, "RGBW")

    @staticmethod
    def from_json(json):
        pass

    async def setup(self):
        pass

    async def terminate(self):
        pass

    async def loop(self):
        pass

    def fill(self, color):
        # If tuple has 4 elements, it's RGBW, so no need to convert. If 3, convert to RGBW.
        if len(color) == 3:
            color = RGBToRGBW(color[0], color[1], color[2])
        self.NP.fill(color)

    def set_pixel(self, index, color):
        # If tuple has 4 elements, it's RGBW, so no need to convert. If 3, convert to RGBW.
        if len(color) == 3:
            color = RGBToRGBW(color[0], color[1], color[2])
        self.NP.set_pixel(index, color)

    def set_pixel_line(self, start, end, color):
        # If tuple has 4 elements, it's RGBW, so no need to convert. If 3, convert to RGBW.
        if len(color) == 3:
            color = RGBToRGBW(color[0], color[1], color[2])
        self.NP.set_pixel_line(start, end, color)

class NeopixelSingleColorConfiguration(NeopixelConfigurationInterface):
    def __init__(self, color):
        self.color = color
        super().__init__()

    @staticmethod
    def from_json(json):
        return NeopixelSingleColorConfiguration(
            (json["color"][0], json["color"][1], json["color"][2])
        )

    async def setup(self):
        self.NP.fill(self.color)
        self.NP.show()
        await asyncio.sleep_ms(1000)

    async def loop(self):
        # Just keep the color on.
        while True:
            self.fill(self.color)
            self.NP.show()
            await asyncio.sleep_ms(1000)
    
    async def terminate(self):
        self.fill((0, 0, 0, 0))
        self.NP.show()
        await asyncio.sleep_ms(1000)

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
            (json["color1"][0], json["color1"][1], json["color1"][2]),
            (json["color2"][0], json["color2"][1], json["color2"][2]),
            json["steps"],
            json["wait_ms"],
        )

    async def setup(self):
        self.fill(self.color1)
        self.NP.show()
        await asyncio.sleep_ms(1000)

    async def terminate(self):
        self.fill((0, 0, 0, 0))
        self.NP.show()
        await asyncio.sleep_ms(1000)

    async def loop(self):
        # Color shift the fill to the other color, one step at a time. After the last step, start over.
        while True:
            for i in range(self.steps):
                self.fill(lerp(self.color1, self.color2, i / self.steps))
                self.NP.show()
                await asyncio.sleep_ms(self.wait_ms)
            for i in range(self.steps):
                self.fill(lerp(self.color2, self.color1, i / self.steps))
                self.NP.show()
                await asyncio.sleep_ms(self.wait_ms)