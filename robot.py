"""Leg-level control: angles in, calibrated pulse widths out."""

from machine import I2C, Pin

import config
from pca9685 import PCA9685


class Robot:
    def __init__(self):
        self.i2c = I2C(
            0,
            sda=Pin(config.I2C_SDA),
            scl=Pin(config.I2C_SCL),
            freq=config.I2C_FREQ,
        )
        self.pca = PCA9685(self.i2c, config.PCA_ADDR, config.PCA_OSC_HZ)
        self.pca.freq(config.SERVO_HZ)
        # Starting the oscillator leaves LEDn at the power-on value of 0, which
        # is on==off — an ambiguous state rather than a defined idle. Force the
        # full-off bit so no servo twitches until something commands a move.
        self.pca.release_all()
        self.legs = config.LEGS
        self.angles = {name: 0.0 for name in config.LEG_NAMES}

    # -- discovery ------------------------------------------------------------

    def scan(self):
        return [hex(a) for a in self.i2c.scan()]

    # -- movement -------------------------------------------------------------

    def set_angle(self, name, degrees):
        """Swing one leg `degrees` away from its neutral. Positive = forward."""
        leg = self.legs[name]

        limit = config.MAX_SWING_DEG
        if degrees > limit:
            degrees = limit
        elif degrees < -limit:
            degrees = -limit

        offset = degrees * config.US_PER_DEG
        if leg["invert"]:
            offset = -offset

        us = leg["center_us"] + offset
        if us < config.MIN_US:
            us = config.MIN_US
        elif us > config.MAX_US:
            us = config.MAX_US

        self.pca.us(leg["channel"], us)
        self.angles[name] = degrees

    def set_all(self, degrees_by_leg):
        for name, degrees in degrees_by_leg.items():
            self.set_angle(name, degrees)

    def center(self):
        """Put every leg at its calibrated neutral."""
        for name in config.LEG_NAMES:
            self.set_angle(name, 0)

    def relax(self):
        """Cut the pulse train. Servos go limp — safe to reposition by hand."""
        self.pca.release_all()

    # -- calibration helpers --------------------------------------------------

    def raw_us(self, name, microseconds):
        """Bypass calibration and drive one leg's servo to a raw pulse width.

        Use this to find each leg's true center: sweep until the leg is at
        mechanical neutral, then copy that number into config.LEGS.
        """
        if not config.MIN_US <= microseconds <= config.MAX_US:
            raise ValueError(
                "refusing %dus, outside [%d, %d]"
                % (microseconds, config.MIN_US, config.MAX_US)
            )
        self.pca.us(self.legs[name]["channel"], microseconds)

    def report(self):
        print("i2c devices:", self.scan())
        print("pwm freq:   %.1f Hz" % self.pca.freq())
        for name in config.LEG_NAMES:
            leg = self.legs[name]
            print(
                "  %s  ch%-2d center=%4dus invert=%-5s angle=%+.1f"
                % (name, leg["channel"], leg["center_us"], leg["invert"],
                   self.angles[name])
            )
