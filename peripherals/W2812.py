'''
this is a modified version of https://github.com/seitomatsubara/Jetson-nano-WS2812-LED-/blob/master/W2812.py

it's modified so that 5 leds can be used which is what we have for our project
'''
import spidev
import sys
 
class SPItoWS():
    def __init__(self, ledc):
        self.led_count = ledc
        self.X = '' # X is signal of WS281x
        for i in range(self.led_count):
            self.X = self.X + "100100100100100100100100100100100100100100100100100100100100100100100100"
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 2400000

    def __del__(self):
        self.spi.close()
        
    def _Bytesto3Bytes(self, num, RGB): # num is number of signal, RGB is 8 bits (1 byte) str
        for i in range(8):
                base = num * 24 #3 colors x 8 bits
                self.X = self.X[:base + i * 3] + ('100' if RGB[i]=='0' else '110') + self.X[base + i * 3 + 3:]
    
    def _BytesToHex(self, Bytes):
        return ''.join(["0x%02X " % x for x in Bytes]).strip()
    
    def LED_show(self):
            Y = []
            for i in range(self.led_count * 9):
                Y.append(int(self.X[i*8:(i+1)*8],2))
            WS = self._BytesToHex(Y)
            self.spi.xfer3(Y, 2400000,0,8)

    def RGBto3Bytes(self, led_num, R, G, B):
        if (R > 255 or G > 255 or B > 255):
            print("Invalid Value: RGB is over 255\n")
            sys.exit(1)
        if (led_num > self.led_count - 1):
            print("Invalid Value: The number is over the number of LED")
            sys.exit(1)
        RR = format(R, '08b')
        GG = format(G, '08b')
        BB = format(B, '08b')
        self._Bytesto3Bytes(led_num * 3, GG)
        self._Bytesto3Bytes(led_num * 3 + 1, RR)
        self._Bytesto3Bytes(led_num * 3 + 2, BB)

    def LED_OFF_ALL(self):
        self.X = ''
        for i in range(self.led_count):
            self.X = self.X + "100100100100100100100100100100100100100100100100100100100100100100100100"
        self.LED_show()

if __name__ == "__main__":
    import time
    LED_COUNT = 5
    sig = SPItoWS(LED_COUNT)
    sig.RGBto3Bytes(0, 255, 0, 0)
    sig.RGBto3Bytes(1, 0, 255, 0)
    sig.RGBto3Bytes(2, 0, 0, 255)
    sig.RGBto3Bytes(3, 134, 75, 255)
    sig.RGBto3Bytes(4, 23, 1, 255)
    sig.LED_show()
    time.sleep(1)
    sig.LED_OFF_ALL()
