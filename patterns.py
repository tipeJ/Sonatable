from neopixel import Neopixel
from machine import Pin
import uasyncio as asyncio
from micropython import const
from color_utils import hsi2rgbw, RGBToRGBW, RGB2RGBW, lerp, random_rgb, wheel

# Rough dimensions of the elements on the board
_MOUNTAIN_START = const(135)
_MOUNTAIN_END = const(30)
_DESERT_START = const(30)
_DESERT_END = const(60)
_SEA_START = const(60)
_SEA_END = const(110)
_JUNGLE_START = const(110)
_JUNGLE_END = const(135)

_TAVERNA = const(0)
_DRAGON = const(140)
_REED = const(70)
class NeopixelConfigurationInterface:
    def __init__(self):
        self.PIN = Pin(28)
        self.NUM_PIXELS = 7
        self.NP = Neopixel(self.NUM_PIXELS, 0, 28, "RGBW")
        # Set up mask for brightness. 0-255 value for each pixel
        self.brightness_mask = [255] * self.NUM_PIXELS

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
            color = RGB2RGBW(color[0], color[1], color[2])
        self.NP.fill(color)

    def set_pixel(self, index, color):
        index = self.get_board_pixel(index)
        # If tuple has 4 elements, it's RGBW, so no need to convert. If 3, convert to RGBW.
        if len(color) == 3:
            color = RGB2RGBW(color[0], color[1], color[2])
        self.NP.set_pixel(index, color, how_bright=self.brightness_mask[index])

    def set_pixel_line(self, start, end, color):
        # If tuple has 4 elements, it's RGBW, so no need to convert. If 3, convert to RGBW.
        if len(color) == 3:
            color = RGB2RGBW(color[0], color[1], color[2])
        self.NP.set_pixel_line(start, end, color)

    def get_board_pixel(self, index):
        # If index exceeds the number of pixels, return the remainder pixel from the start. If negative, return the remainder pixel from the end.
        if index >= self.NUM_PIXELS:
            index = index % self.NUM_PIXELS
        elif index < 0:
            index = self.NUM_PIXELS - (abs(index) % self.NUM_PIXELS)
        return index

    def get_board_pixel_range(self, i1, i2, clockwise=True):
        # Get corrected range
        if clockwise:
            # If the second value is less than the first, add the number of pixels to the second value.
            if i2 < i1:
                return range(i1, i2 + self.NUM_PIXELS)
            else:
                return range(i1, i2)
        else:
            # If the first value is less than the second, add the number of pixels to the first value.
            if i1 < i2:
                return range(i1 + self.NUM_PIXELS, i2, -1)
            else:
                return range(i1, i2, -1)

    def get_pixel_color(self, index):
        color = self.NP.get_pixel(self.get_board_pixel(index))
        # Convert to RGB

    # Draw a line of pixels with a feathered edge.
    def set_feather_pixel_line(self, start, end, color, feather):
        # If tuple has 4 elements, it's RGBW, so no need to convert. If 3, convert to RGBW.
        if len(color) == 3:
            color = RGB2RGBW(color[0], color[1], color[2])
        # Draw the solid line first, then the feathered edges.
        solid_line_start = self.get_board_pixel(start + feather)
        solid_line_end = self.get_board_pixel(end - feather)
        self.set_pixel_line(solid_line_start, solid_line_end, color)
        # Now draw the feathered edges.
        for i in range(feather):
            # Draw the left edge.
            left_edge_pixel_color = self.get_pixel_color(start + i)
            self.set_pixel(self.get_board_pixel(start + i), lerp(color, left_edge_pixel_color, i / feather))
            # Draw the right edge.
            right_edge_pixel_color = self.get_pixel_color(end - i)
            self.set_pixel(self.get_board_pixel(end - i), lerp(color, right_edge_pixel_color, i / feather))

    def show(self):
        self.NP.show()

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
        # Lerp to the color over 1 second.
        for i in range(100):
            self.fill(lerp((0, 0, 0), self.color, i / 100))
            self.NP.show()
            await asyncio.sleep_ms(10)

    async def loop(self):
        # Just keep the color on.
        while True:
            self.fill(self.color)
            self.NP.show()
            await asyncio.sleep_ms(1000)
    
    async def terminate(self):
        # Lerp to black over 1 second.
        for i in range(100):
            self.fill(lerp(self.color, (0, 0, 0), i / 100))
            self.NP.show()
            await asyncio.sleep_ms(10)

class NeopixelGradientPulseConfiguration(NeopixelConfigurationInterface):
    def __init__(self, color1, color2, steps=50, wait_ms=50):
        self.color1 = color1
        self.color2 = color2
        self.steps = steps
        self.wait_ms = wait_ms
        super().__init__()

    @staticmethod
    def from_json(json):
        return NeopixelGradientPulseConfiguration(
            (json["c1"][0], json["c1"][1], json["c1"][2]),
            (json["c2"][0], json["c2"][1], json["c2"][2]),
            json["steps"],
            json["wait_ms"],
        )

    async def setup(self):
        self.fill(self.color1)
        self.NP.show()
        await asyncio.sleep_ms(1)

    async def terminate(self):
        self.fill((0, 0, 0, 0))
        self.NP.show()
        await asyncio.sleep_ms(1)

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

class Rainbow(NeopixelConfigurationInterface):
    def __init__(self, wait_ms=50):
        self.wait_ms = wait_ms
        super().__init__()

    @staticmethod
    def from_json(json):
        return Rainbow(json["wait_ms"])

    async def setup(self):
        # Fill with black
        self.fill((0, 0, 0, 0))

    async def terminate(self):
        # Lerp to black over 1 second.
        self.fill((0, 0, 0, 0))

    async def loop(self):
        # Color shift the fill to the other color, one step at a time. After the last step, start over.
        j = 0
        while True:
            for i in range(self.NUM_PIXELS):
                self.set_pixel(i, wheel((((i * 255) // self.NUM_PIXELS) + j) & 255))
            self.show()
            j = (j + 1) % 256
            await asyncio.sleep_ms(self.wait_ms)

class PowerOn(NeopixelConfigurationInterface):
    def __init__(self):
        super().__init__()

    @staticmethod
    def from_json(json):
        return PowerOn()

    async def setup(self):
        # Fill with black
        self.fill((0, 0, 0, 0))
        self.show()
        # Then, start a flash of light moving from the REED to the TAVERNA in clockwise direction
        for i in self.get_board_pixel_range(_REED, _TAVERNA):
            self.fill((0, 0, 0, 0))
            self.set_pixel(i, (255, 255, 255, 255))
            self.show()
            await asyncio.sleep_ms(50)
        # Now, start drawing a feathered line from the TAVERNA through the DESERT
        line_length = 10
        line_feather = 4
        for i in self.get_board_pixel_range(_TAVERNA, _DESERT_END):
            self.set_feather_pixel_line(i, i + line_length, (255, 255, 255, 255), line_feather)
            self.show()
            await asyncio.sleep_ms(50)