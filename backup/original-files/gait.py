"""Gait engine.

Every leg has a single degree of freedom, so a gait here is just four phase-
shifted sweeps of the same sinusoid. What separates the gaits is *which* legs
move together.

Phases are fractions of one cycle, 0.0 to 1.0.

        FL   FR
          [ ]
        RL   RR
"""

import math
import time

import config

GAITS = {
    # Diagonal pairs move together. Most stable at speed; the usual default.
    "trot": {"FL": 0.00, "RR": 0.00, "FR": 0.50, "RL": 0.50},
    # One leg at a time, three always planted. Slowest and most stable.
    "creep": {"FL": 0.00, "RR": 0.25, "FR": 0.50, "RL": 0.75},
    # Same-side pairs together. Rolls the body side to side — useful when the
    # legs need a body tilt to unweight a foot.
    "pace": {"FL": 0.00, "RL": 0.00, "FR": 0.50, "RR": 0.50},
    # Front pair, then rear pair. Pitches the body fore and aft.
    "bound": {"FL": 0.00, "FR": 0.00, "RL": 0.50, "RR": 0.50},
}

UPDATE_MS = 20  # 50 Hz, matched to the servo frame rate


def _clamp(value, low, high):
    return low if value < low else (high if value > high else value)


def angles_at(phase, gait="trot", swing=20.0, turn=0.0, reverse=False):
    """Leg angles at a point in the cycle. Pure maths — drives no hardware."""
    offsets = GAITS[gait]
    swing = _clamp(swing, 0.0, config.MAX_SWING_DEG)
    turn = _clamp(turn, -1.0, 1.0)
    direction = -1.0 if reverse else 1.0

    out = {}
    for name in config.LEG_NAMES:
        # Turning shortens the stride on the inside of the turn. turn > 0 is a
        # right turn, so the right legs give up travel.
        is_right = name[1] == "R"
        scale = 1.0 - abs(turn) if (turn > 0) == is_right and turn != 0 else 1.0
        theta = 2.0 * math.pi * (phase + offsets[name])
        out[name] = direction * scale * swing * math.sin(theta)
    return out


def walk(robot, gait="trot", swing=20.0, period_ms=900, cycles=None,
         turn=0.0, reverse=False):
    """Walk until `cycles` have elapsed, or forever until Ctrl-C.

    swing      degrees either side of neutral
    period_ms  duration of one full gait cycle
    turn       -1.0 hard left .. 0 straight .. +1.0 hard right
    """
    if gait not in GAITS:
        raise ValueError("unknown gait %r, try one of %s" % (gait, list(GAITS)))

    start = time.ticks_ms()
    limit_ms = None if cycles is None else int(cycles * period_ms)

    try:
        while True:
            elapsed = time.ticks_diff(time.ticks_ms(), start)
            if limit_ms is not None and elapsed >= limit_ms:
                break
            phase = (elapsed % period_ms) / period_ms
            robot.set_all(angles_at(phase, gait, swing, turn, reverse))
            time.sleep_ms(UPDATE_MS)
    except KeyboardInterrupt:
        pass

    robot.center()


def sweep(robot, name, swing=20.0, period_ms=1500, cycles=3):
    """Rock one leg back and forth. For checking direction and travel limits."""
    start = time.ticks_ms()
    limit_ms = int(cycles * period_ms)
    try:
        while time.ticks_diff(time.ticks_ms(), start) < limit_ms:
            phase = (time.ticks_diff(time.ticks_ms(), start) % period_ms) / period_ms
            robot.set_angle(name, swing * math.sin(2.0 * math.pi * phase))
            time.sleep_ms(UPDATE_MS)
    except KeyboardInterrupt:
        pass
    robot.set_angle(name, 0)
