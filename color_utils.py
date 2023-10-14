import math
import random

def hsi2rgbw(H, S, I):
    rgbw = [0, 0, 0, 0]
    cos_h, cos_1047_h = 0.0, 0.0
    H = H % 360  # Cycle H around to 0-360 degrees
    H = 3.14159 * H / 180  # Convert to radians.
    S = S if 0 < S < 1 else 1 if S >= 1 else 0  # Clamp S to the interval [0,1]
    I = I if 0 < I < 1 else 1 if I >= 1 else 0  # Clamp I to the interval [0,1]

    if H < 2.09439:
        cos_h = math.cos(H)
        cos_1047_h = math.cos(1.047196667 - H)
        r = round(S * 255 * I / 3 * (1 + cos_h / cos_1047_h))
        g = round(S * 255 * I / 3 * (1 + (1 - cos_h / cos_1047_h)))
        b = 0
        w = round(255 * (1 - S) * I)
    elif H < 4.188787:
        H = H - 2.09439
        cos_h = math.cos(H)
        cos_1047_h = math.cos(1.047196667 - H)
        g = round(S * 255 * I / 3 * (1 + cos_h / cos_1047_h))
        b = round(S * 255 * I / 3 * (1 + (1 - cos_h / cos_1047_h)))
        r = 0
        w = round(255 * (1 - S) * I)
    else:
        H = H - 4.188787
        cos_h = math.cos(H)
        cos_1047_h = math.cos(1.047196667 - H)
        b = round(S * 255 * I / 3 * (1 + cos_h / cos_1047_h))
        r = round(S * 255 * I / 3 * (1 + (1 - cos_h / cos_1047_h)))
        g = 0
        w = round(255 * (1 - S) * I)

    rgbw[0] = r
    rgbw[1] = g
    rgbw[2] = b
    rgbw[3] = w

    return rgbw

def RGBToRGBW(r, g, b, blueCorrectionEnabled=False):
    # Source: https://github.com/BertanT/Arduino-RGBWConverter/blob/main/src/RGBWConverter.cpp
    # Converted to Python by me :)
    _wTempRed = 255.0
    _wTempGreen = 255.0
    _wTempBlue = 255.0
    
    # Calculate all of the color's white values corrected taking into account the white color temperature.
    wRed = r * (255 / _wTempRed)
    wGreen = g * (255 / _wTempGreen)
    wBlue = b * (255 / _wTempBlue)

    # Determine the smallest white value from above.
    wMin = round(min(wRed, min(wGreen, wBlue)))

    # Make the color with the smallest white value to be the output white value
    if wMin == wRed:
        wOut = r
    elif wMin == wGreen:
        wOut = g
    else:
        wOut = b

    # Calculate the output red, green, and blue values, taking into account the white color temperature.
    rOut = round(r - wOut * (_wTempRed / 255))
    gOut = round(g - wOut * (_wTempGreen / 255))
    bOut = round(b - wOut * (_wTempBlue / 255))

    # Apply the blue correction if enabled.
    # This is required on some RGBW NeoPixels which have a little bit of blue mixed into the blue color.
    if blueCorrectionEnabled:
        wOut -= bOut * 0.2

    # Return the output values.
    return (rOut, gOut, bOut, wOut)

def random_rgb():
    return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

# Takes value of hue between 0 and 255. Transition r -> g -> b -> r.
def wheel(wheel_pos):
    if wheel_pos < 85:
        return (wheel_pos * 3, 255 - wheel_pos * 3, 0)
    elif wheel_pos < 170:
        wheel_pos -= 85
        return (255 - wheel_pos * 3, 0, wheel_pos * 3)
    else:
        wheel_pos -= 170
        return (0, wheel_pos * 3, 255 - wheel_pos * 3)

def lerp(color1, color2, t):
    return (color1[0] + (color2[0] - color1[0]) * t, color1[1] + (color2[1] - color1[1]) * t, color1[2] + (color2[2] - color1[2]) * t)