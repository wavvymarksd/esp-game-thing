"""Runs on boot. Deliberately does NOT start walking by itself.

Everything defined here is available at the REPL, so after reset you can just
type `stand()` or `walk()`.
"""

import config
import gait
from robot import Robot

r = None


def connect():
    """(Re)open the I2C bus. Called at boot; call again after rewiring."""
    global r
    try:
        r = Robot()
    except Exception as e:
        r = None
        print("!! cannot reach the PCA9685 at", hex(config.PCA_ADDR), "->", e)
        print("   VCC->3V3  GND->G  SDA->%d  SCL->%d" % (config.I2C_SDA, config.I2C_SCL))
        print("   grounds must be common. fix the wiring, then run connect()")
        return False
    return True


def _need():
    if r is None:
        raise RuntimeError("no PCA9685 — fix wiring and run connect()")
    return r


def check():
    """Print bus state and calibration. Run this first."""
    if r is None:
        print("not connected. run connect()")
        return
    found = r.scan()
    print("i2c devices:", found or "NONE -- check SDA/SCL/VCC/GND")
    if hex(config.PCA_ADDR) not in found:
        print("!! PCA9685 not answering at", hex(config.PCA_ADDR))
        return
    r.report()


def stand():
    """Every leg to its calibrated neutral."""
    _need().center()


def relax():
    """Stop pulsing. Servos go limp — do this before handling the robot."""
    _need().relax()


def walk(gait_name="trot", swing=20, period_ms=900, cycles=None, turn=0, reverse=False):
    gait.walk(_need(), gait_name, swing, period_ms, cycles, turn, reverse)


def sweep(name, swing=20, cycles=3):
    gait.sweep(_need(), name, swing, cycles=cycles)


connect()

print()
print("quadruped ready.  SDA=%d SCL=%d" % (config.I2C_SDA, config.I2C_SCL))
print("  check()                 bus + calibration report")
print("  stand()                 all legs to neutral")
print("  relax()                 servos limp")
print("  sweep('FL')             rock one leg, check direction")
print("  r.raw_us('FL', 1500)    find a leg's true center")
print("  walk()                  trot forward, Ctrl-C to stop")
print("  walk('creep', swing=25, period_ms=1400)")
print("  gaits:", list(gait.GAITS))
print()

# --- esp-game-thing ----------------------------------------------------------
# Serves the Wi-Fi game until you press Ctrl-C; after that the REPL is yours
# and everything above (stand(), walk(), ...) works as before.
# Delete this block to go back to a plain robot boot.
import game


def _i2c_scan():
    from machine import I2C, Pin

    bus = r.i2c if r else I2C(
        0, sda=Pin(config.I2C_SDA), scl=Pin(config.I2C_SCL), freq=config.I2C_FREQ
    )
    return [hex(a) for a in bus.scan()]


try:
    game.run(i2c_scan=_i2c_scan)
except KeyboardInterrupt:
    print("game stopped. robot REPL ready; game.run(_i2c_scan) restarts it")
