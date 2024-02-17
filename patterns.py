from neopixel import Neopixel
from machine import Pin
import time
from main import LEDSTRIP_PIN
import uasyncio as asyncio
from micropython import const
from color_utils import hsi2rgbw, RGBToRGBW, RGB2RGBW, lerp, random_rgb, wheel, beatsin88, beatsin16, beatsin8, beat16, sin16, scale16, getAverageLightness

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
        self.NUM_PIXELS = 151
        self.NP = Neopixel(self.NUM_PIXELS, 0, LEDSTRIP_PIN, "RGBW")
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
        return (color[0], color[1], color[2])

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
        # If given color is RGB, convert to RGBW.
        if len(color) == 3:
            color = RGB2RGBW(color[0], color[1], color[2])
        self.color = color
        super().__init__()

    @staticmethod
    def from_json(json):
        # Check whether the colors are RGB or RGBW.
        if len(json["color"]) == 3:
            return NeopixelSingleColorConfiguration(
                RGB2RGBW(json["color"][0], json["color"][1], json["color"][2])
            )
        else:
            return NeopixelSingleColorConfiguration(
                (json["color"][0], json["color"][1], json["color"][2], json["color"][3])
            )

    async def setup(self):
        # Lerp to the color over 1 second.
        for i in range(100):
            self.fill(lerp((0, 0, 0, 0), self.color, i / 100))
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
            self.fill(lerp(self.color, (0, 0, 0, 0), i / 100))
            self.NP.show()
            await asyncio.sleep_ms(10)

    # ? Live modification functions (Mainly for static color modification with physical buttons)
    def increase_color_for_channel(self, channel, amount):
        # Increase the color for the given channel by the given amount. Loop back to 0 if it exceeds 255.
        self.color = list(self.color)
        self.color[channel] = (self.color[channel] + amount) % 256
        self.color = tuple(self.color)

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

class Pacifica(NeopixelConfigurationInterface):
    # By https://gist.github.com/kriegsman/36a1e277f5b4084258d9af1eae29bac4
    # Converted to Python by me :)
    def __init__(self, wait_ms=50, palettes=[]):
        self.wait_ms = wait_ms
        self.palettes = palettes
        self.sCIStart1, self.sCIStart2, self.sCIStart3, self.sCIStart4 = 0, 0, 0, 0
        self.sLastms = 0
        super().__init__()

    @staticmethod
    def from_json(json):
        return Pacifica(json["wait_ms"], json["palettes"])
    
    async def setup(self):
        self.fill((0, 0, 0, 0))
        self.NP.show()
        await asyncio.sleep_ms(1)

    async def terminate(self):
        self.fill((0, 0, 0, 0))
        self.NP.show()
        await asyncio.sleep_ms(1)

    @staticmethod
    async def loop(self):
        # Color shift the fill to the other color, one step at a time. After the last step, start over.
        while True:
            await asyncio.sleep_ms(self.wait_ms)
            self.pacifica_loop()
            self.NP.show()

    def pacifica_loop(self):
        ms = time.ticks_ms()
        deltams = time.ticks_diff(ms, self.sLastms)
        self.lastms = ms
        
        speedfactor1 = beatsin16(3, 179, 269)
        speedfactor2 = beatsin16(4, 179, 269)
        deltams1 = (deltams * speedfactor1) // 256
        deltams2 = (deltams * speedfactor2) // 256
        deltams21 = (deltams1 + deltams2) // 2
        self.sCIStart1 += (deltams1 * beatsin88(1011, 10, 13))
        self.sCIStart2 += (deltams21 * beatsin88(777, 8, 11))
        self.sCIStart3 += (deltams1 * beatsin88(501, 5, 7))
        self.sCIStart4 += (deltams2 * beatsin88(257, 4, 6))

        # Clear out the LED array to a dim background blue-green
        self.fill((0, 0, 1, 1))

        # Render each of four layers of waves, with different scales and speeds, that vary over time
        self.one_layer_of_pacifica(self.palettes[0], self.sCIStart1,  beatsin16(3, 11 * 256, 14 * 256), beatsin8(10, 70, 130), 0-beat16(301))
        self.one_layer_of_pacifica(self.palettes[1], self.sCIStart2,  beatsin16(4,  6 * 256, 9 * 256), beatsin8(17, 40, 80), beat16(401))
        self.one_layer_of_pacifica(self.palettes[2], self.sCIStart3,  6 * 256, beatsin8(9, 10, 38), 0-beat16(503))
        self.one_layer_of_pacifica(self.palettes[3], self.sCIStart4,  5 * 256, beatsin8(8, 10, 28), beat16(601))


    def one_layer_of_pacifica(self, palette, cistart, wavescale, bri, ioff):

        wavescale_half = wavescale // 2 + 20
        waveangle = ioff
        ci = cistart
        for i in range(0, self.NUM_PIXELS):
            waveangle += 250
            s16 = sin16(waveangle) + 32768
            cs = scale16(s16, wavescale_half) + wavescale_half
            ci += cs
            sindex16 = sin16(ci) + 32768
            sindex8 = scale16(sindex16, 240)
            color = palette[sindex8]
            self.set_pixel(i, hsi2rgbw(color, 255, bri, 255))

    def add_whitecaps(self):
        basethreshold = beatsin8(9, 55, 65)
        wave = beat16(7)

        for i in range(0, self.NUM_PIXELS):
            threshold = scale16(sin16(wave), 20) + basethreshold
            wave += 300
            l = self.get_pixel_color(i)
            li = getAverageLightness(l)
            if li > threshold:
                overage = li - threshold
                overage2 = min(overage + overage, 255)
                self.set_pixel(i, (overage, overage2, min(overage2 + overage2, 255), 0))

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
        return
        for i in range(100):
            for i in range(self.NUM_PIXELS):
                self.set_pixel(i, lerp(self.get_pixel_color(i), (0, 0, 0, 0), i / 100))
            self.show()
            await asyncio.sleep_ms(10)

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