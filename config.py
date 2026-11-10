"""Wiring and per-servo calibration. This is the file you edit while tuning."""

# --- I2C bus -----------------------------------------------------------------
# ESP32-C5. GPIO23/24 are general-purpose (not strapping, not USB, not flash).
I2C_SDA = 23
I2C_SCL = 24
I2C_FREQ = 400_000

PCA_ADDR = 0x40  # all address jumpers open

# If measured pulse widths come out wrong on a clone board, the on-board
# oscillator is off spec. Scale this until a commanded 1500us really is 1500us.
PCA_OSC_HZ = 25_000_000

SERVO_HZ = 50


# --- Servo travel ------------------------------------------------------------
# Hard limits. Nothing below ever commands a pulse outside this window, so a bad
# calibration number stalls the gait instead of stalling (and cooking) a servo.
MIN_US = 700
MAX_US = 2300

# Pulse width change per degree. 1000us per 90deg is the common SG90/MG90S spec.
US_PER_DEG = 1000.0 / 90.0


# --- Legs --------------------------------------------------------------------
# One servo per leg, four total.
#
#   center_us : pulse width at which THIS leg sits at its mechanical neutral.
#               Start at 1500 and trim per leg once you see it standing.
#   invert    : left and right legs are mirrored, so +1 on the servo swings the
#               leg forward on one side and backward on the other. Flip this
#               until a positive angle swings every leg toward the robot's nose.
#   channel   : PCA9685 output header number.
#
# Body layout, viewed from above, nose at the top:
#
#        FL   FR
#          [ ]
#        RL   RR

LEGS = {
    "FL": {"channel": 0, "center_us": 1500, "invert": False},
    "FR": {"channel": 1, "center_us": 1500, "invert": True},
    "RL": {"channel": 2, "center_us": 1500, "invert": False},
    "RR": {"channel": 3, "center_us": 1500, "invert": True},
}

# Order used for display and for indexed access.
LEG_NAMES = ("FL", "FR", "RL", "RR")

# Largest swing away from center any gait is allowed to command, in degrees.
MAX_SWING_DEG = 35
