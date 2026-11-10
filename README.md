# esp-game-thing

A tiny game that lives on an ESP32-C5. Power the board, join its Wi-Fi, and a
game pops up on your phone where you wire sensors into a chip — and every
reading it shows comes from the real board in your hand.

The same board is also the brain of a four-legged servo robot. Both live here.

## Play

1. Power the board over USB. Give it about 10 seconds.
2. Join the Wi-Fi network **`esp-game-thing`** (no password).
3. The game should pop up by itself. If it doesn't, open
   **http://games.local** or **http://192.168.4.1**.

Your phone may warn that the network has no internet. That's expected: stay
connected. Up to 8 devices can join at once.

## The game

You are Sparky, a little spark on a circuit board. Grab the wire from each of
six sensors and plug it into the right pin on the big ESP32-C5 in the middle.
The pins shuffle every round, a wrong pin zaps you with a clue about what that
pin really does, and two roaming static sparks will knock the wire out of your
hand.

Once a sensor is wired it comes alive with live data from the board, plus a
bonus challenge you do on the real hardware:

| Sensor | Pin | What it shows | Bonus star |
|---|---|---|---|
| 🌡️ Thermometer | `TEMP` | Temperature inside the chip | Change it by 1°C |
| 🔘 Button | `IO28` | The BOOT button | Press it 5 times |
| ✋ Touch probe | `IO1`–`IO6` | Voltage on six analog pins | Bridge `3V3` to one with a wire or a damp finger |
| 💡 Light | `IO27` | RGB LED | Pick a colour |
| 📡 Antenna | `ANT` | Wi-Fi networks heard at boot | Tap the strongest |
| 🦿 Robot bus | `I2C` | Devices on the I2C bus | Run a scan |

For the touch probe, use the **3V3** pin only — never 5V.

## The board

| | |
|---|---|
| Chip | ESP32-C5 (ESP32-C5HF4, RISC-V, 240 MHz) |
| Radio | Dual-band Wi-Fi 6, Bluetooth 5 LE, 802.15.4 |
| Flash | 4 MB, built into the chip |
| USB | Built-in USB serial/JTAG (no separate USB chip) |
| Firmware | MicroPython v1.28.0 (`ESP32_GENERIC_C5`) |

Pins in use:

| Pin | Used for |
|---|---|
| `IO1`–`IO6` | Game: analog inputs, pulled down |
| `IO23` / `IO24` | Robot: I2C SDA / SCL to the PCA9685 servo driver |
| `IO27` | Game: RGB LED (where the official C5 dev board has one) |
| `IO28` | Game: BOOT button |

## Files

Everything in the top level of this repo is exactly what is on the board.

| File | What it is |
|---|---|
| `main.py` | Runs at boot. Sets up the robot, then starts the game |
| `game.py` | Wi-Fi hotspot, captive portal (DNS + redirects), web server, sensor sampling |
| `game.html` | The whole game: one page, no dependencies |
| `game.html.gz` | Compressed copy of `game.html`; this is what the board serves |
| `robot.py`, `gait.py`, `config.py`, `pca9685.py` | The quadruped robot |
| `boot.py` | MicroPython default |
| `backup/original-files/` | `main.py` and friends from before the game was added |

### How it works

- `game.py` starts an open access point and answers every DNS lookup with its
  own address. Phones check a known URL after joining; when that gets
  redirected, they open the "sign in to network" window, which is the game.
- The page asks `/api/state` for fresh readings about three times a second.
- Other endpoints: `/api/air` (Wi-Fi heard at boot), `/api/i2c` (bus scan),
  `/api/led?c=rrggbb` (set the light).
- Opening `game.html` straight from your computer runs it in demo mode with
  made-up readings, which is handy while changing the game.

## Using the robot

The game holds the MicroPython prompt while it runs. Connect over USB serial
and press **Ctrl-C** once to stop it; after that `check()`, `stand()`,
`walk()` and the rest work as usual. `game.run(_i2c_scan)` starts the game
again, as does a reset.

To boot straight into the robot with no game, delete the `esp-game-thing`
block at the end of `main.py`.

## Changing the game

No ESP toolchain is needed, only [`uv`](https://docs.astral.sh/uv/):

```sh
# after editing game.html
gzip -9 -k -f game.html

# copy to the board (adjust the port) and restart
uvx mpremote connect /dev/cu.usbmodem21201 \
  fs cp game.html.gz :game.html.gz + fs cp game.py :game.py + reset
```

Settings such as the network name and pin numbers are at the top of `game.py`.

## Good to know

- The network is open: anyone in range can join and play.
- The Antenna station shows the names of nearby Wi-Fi networks to players.
- The Wi-Fi scan happens once at boot, which is why start-up takes a few
  seconds.
