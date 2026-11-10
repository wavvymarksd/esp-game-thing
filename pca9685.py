"""Minimal PCA9685 16-channel PWM driver for MicroPython.

Servo-oriented: the useful entry point is `us(channel, microseconds)`, since
hobby servos are specified in pulse width, not duty counts.
"""

import struct
import time

MODE1 = 0x00
MODE2 = 0x01
PRESCALE = 0xFE
LED0_ON_L = 0x06
ALL_LED_ON_L = 0xFA

_SLEEP = 0x10
_RESTART = 0x80
_AUTOINC = 0x20
_ALLCALL = 0x01

FULL_OFF = 0x1000  # bit 12 of LEDn_OFF forces the output permanently low


class PCA9685:
    def __init__(self, i2c, address=0x40, osc_hz=25_000_000):
        self.i2c = i2c
        self.address = address
        self.osc_hz = osc_hz
        self._freq = 0
        self.reset()

    def _w8(self, reg, value):
        self.i2c.writeto_mem(self.address, reg, bytes([value]))

    def _r8(self, reg):
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]

    def reset(self):
        self._w8(MODE1, _ALLCALL)
        self._w8(MODE2, 0x04)  # totem-pole output, which is what servos need
        time.sleep_ms(1)

    def freq(self, hz=None):
        """Get or set the PWM frequency. Servos want 50 Hz."""
        if hz is None:
            prescale = self._r8(PRESCALE)
            return int(self.osc_hz / 4096.0 / (prescale + 1) + 0.5)

        prescale = int(self.osc_hz / 4096.0 / hz + 0.5) - 1
        if prescale < 3:
            prescale = 3
        elif prescale > 255:
            prescale = 255

        old = self._r8(MODE1)
        self._w8(MODE1, (old & ~_RESTART) | _SLEEP)  # PRESCALE is writable only in sleep
        self._w8(PRESCALE, prescale)
        self._w8(MODE1, old)
        time.sleep_ms(1)  # oscillator needs >500us to stabilise
        self._w8(MODE1, old | _RESTART | _AUTOINC)
        self._freq = self.osc_hz / 4096.0 / (prescale + 1)

    def pwm(self, channel, on, off):
        """Write the raw 12-bit on/off counts for one channel."""
        self.i2c.writeto_mem(
            self.address, LED0_ON_L + 4 * channel, struct.pack("<HH", on, off)
        )

    def us(self, channel, microseconds):
        """Drive `channel` with a pulse of `microseconds` width."""
        if not self._freq:
            raise RuntimeError("call freq() before us()")
        counts = int(microseconds * self._freq * 4096 / 1_000_000 + 0.5)
        if counts < 0:
            counts = 0
        elif counts > 4095:
            counts = 4095
        self.pwm(channel, 0, counts)

    def release(self, channel):
        """Stop pulsing one channel. The servo goes limp and stops drawing current."""
        self.pwm(channel, 0, FULL_OFF)

    def release_all(self):
        self.i2c.writeto_mem(self.address, ALL_LED_ON_L, struct.pack("<HH", 0, FULL_OFF))

    def sleep(self):
        self.release_all()
        self._w8(MODE1, self._r8(MODE1) | _SLEEP)
