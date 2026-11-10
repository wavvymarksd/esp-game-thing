"""esp-game-thing: open Wi-Fi hotspot + captive portal + a tiny game server.

Join the "esp-game-thing" Wi-Fi and the game pops up (or browse to
http://games.local). The page polls /api/state for live readings from this
board, so everything the game shows is the real hardware.

    import game
    game.run()          # blocks; Ctrl-C to stop
"""

import asyncio
import gc
import json
import socket
import time

import esp32
import network
from machine import ADC, Pin

SSID = "esp-game-thing"
HOSTNAME = "games"  # -> http://games.local
IP = "192.168.4.1"
MAX_PLAYERS = 8

BOOT_PIN = 28  # BOOT button, pulls the pin to ground when pressed
LED_PIN = 27  # WS2812 RGB LED on the ESP32-C5 devkit; harmless if absent
PROBE_PINS = (1, 2, 3, 4, 5, 6)  # ADC1 inputs. 23/24 are left alone (robot I2C)

HTML = "game.html.gz"

state = {
    "t": 0,  # chip temperature, C
    "b": 0,  # 1 while BOOT is held
    "n": 0,  # BOOT presses since power-up
    "p": [[0, 0] for _ in PROBE_PINS],  # per probe pin: [mean mV, peak-to-peak mV]
    "led": "000000",
    "up": 0,
    "mem": 0,
    "pl": 0,  # devices joined to the hotspot
}
air = []  # networks heard at boot: [ssid, channel, rssi]

_ap = None
_np = None
_i2c_scan = None
_party = 0


def _listen():
    """Scan once, before the hotspot is up. A scan takes ~8s and would stall
    every player if it ran later."""
    global air
    sta = network.WLAN(network.STA_IF)
    try:
        sta.active(True)
        best = {}
        for ssid, _bssid, ch, rssi, *_ in sta.scan():
            try:
                name = ssid.decode()
            except Exception:
                name = ""
            key = (name, ch > 14)
            if key not in best or rssi > best[key][2]:
                best[key] = [name, ch, rssi]
        air = sorted(best.values(), key=lambda n: -n[2])[:12]
    except Exception as e:
        print("wifi scan failed:", e)
    finally:
        sta.active(False)


def _hotspot():
    global _ap
    try:
        network.hostname(HOSTNAME)
    except Exception:
        pass
    _ap = network.WLAN(network.AP_IF)
    _ap.active(True)
    _ap.config(essid=SSID, authmode=network.AUTH_OPEN)
    try:
        _ap.config(max_clients=MAX_PLAYERS)
    except Exception:
        pass
    # Hand ourselves out as the DNS server so every lookup lands on _dns().
    _ap.ifconfig((IP, "255.255.255.0", IP, IP))


def _led(r, g, b):
    global _np
    if _np is None:
        import neopixel

        _np = neopixel.NeoPixel(Pin(LED_PIN, Pin.OUT), 1)
    _np[0] = (r, g, b)
    _np.write()


def _wheel(i):
    i %= 255
    if i < 85:
        return (255 - i * 3, i * 3, 0)
    if i < 170:
        i -= 85
        return (0, 255 - i * 3, i * 3)
    i -= 170
    return (i * 3, 0, 255 - i * 3)


async def _sensors():
    global _party
    btn = Pin(BOOT_PIN, Pin.IN, Pin.PULL_UP)
    adcs = []
    for p in PROBE_PINS:
        a = ADC(Pin(p))
        a.atten(ADC.ATTN_11DB)
        # Pull-down after the ADC is set up: an untouched pin then reads a
        # steady 0V instead of floating noise.
        Pin(p, Pin.IN, Pin.PULL_DOWN)
        adcs.append(a)
    k = len(adcs)
    lo, hi, tot = [9999] * k, [0] * k, [0] * k
    last, n, slow = 1, 0, 0
    t0 = time.ticks_ms()
    while True:
        v = btn.value()
        if v != last:
            last = v
            if v == 0:
                state["n"] += 1
        state["b"] = 1 - v
        for i in range(k):
            mv = adcs[i].read_uv() // 1000
            if mv < lo[i]:
                lo[i] = mv
            if mv > hi[i]:
                hi[i] = mv
            tot[i] += mv
        n += 1
        if n >= 15:
            state["p"] = [[tot[i] // n, hi[i] - lo[i]] for i in range(k)]
            lo, hi, tot, n = [9999] * k, [0] * k, [0] * k, 0
            slow += 1
            if slow >= 5:
                slow = 0
                state["t"] = esp32.mcu_temperature()
                state["up"] = time.ticks_diff(time.ticks_ms(), t0) // 1000
                state["mem"] = gc.mem_free()
                try:
                    state["pl"] = len(_ap.status("stations"))
                except Exception:
                    pass
        if _party > 0:
            _party -= 1
            try:
                if _party:
                    _led(*[c // 6 for c in _wheel(_party * 6)])
                else:
                    c = state["led"]
                    _led(int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
            except Exception:
                _party = 0
        # 13ms, not 20: sampling at exactly mains frequency would hide hum.
        await asyncio.sleep_ms(13)


async def _dns():
    """Answer every DNS question with our own address (captive portal)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setblocking(False)
    s.bind(("0.0.0.0", 53))
    ip = bytes(int(x) for x in IP.split("."))
    while True:
        try:
            data, addr = s.recvfrom(512)
        except OSError:
            await asyncio.sleep_ms(30)
            continue
        try:
            if len(data) < 17:
                continue
            i = 12
            while i < len(data) and data[i]:
                i += data[i] + 1
            q = data[12 : i + 5]
            if data[i + 1 : i + 3] == b"\x00\x01":  # A record
                resp = (
                    data[:2] + b"\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00" + q
                    + b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04" + ip
                )
            else:  # AAAA etc: "no such record", so clients fall back to A
                resp = data[:2] + b"\x81\x80\x00\x01\x00\x00\x00\x00\x00\x00" + q
            s.sendto(resp, addr)
        except Exception:
            pass


async def _send(w, body, ctype="application/json", status="200 OK", extra=""):
    if isinstance(body, str):
        body = body.encode()
    w.write(
        "HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
        "Cache-Control: no-store\r\nConnection: close\r\n%s\r\n"
        % (status, ctype, len(body), extra)
    )
    w.write(body)
    await w.drain()


async def _http(r, w):
    global _party
    try:
        line = await asyncio.wait_for(r.readline(), 5)
        parts = line.split()
        if len(parts) < 2:
            return
        path = parts[1].decode()
        host = ""
        while True:
            h = await asyncio.wait_for(r.readline(), 5)
            if not h or h == b"\r\n":
                break
            if h[:5].lower() == b"host:":
                host = h[5:].strip().decode().lower().split(":")[0]
        path, _, qs = path.partition("?")

        if path == "/api/state":
            await _send(w, json.dumps(state))
        elif path == "/api/air":
            await _send(w, json.dumps(air))
        elif path == "/api/i2c":
            try:
                found = list(_i2c_scan()) if _i2c_scan else []
            except Exception:
                found = []
            await _send(w, json.dumps(found))
        elif path == "/api/led":
            c = qs.partition("c=")[2][:6]
            if c == "party":
                _party = 255
            elif len(c) == 6:
                rgb = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
                state["led"] = c
                _party = 0
                _led(*rgb)
            await _send(w, '{"ok":1}')
        elif host not in (IP, HOSTNAME, HOSTNAME + ".local"):
            # Phones probe a known URL after joining. Anything but the
            # expected reply makes them pop open the "sign in" page: us.
            await _send(w, "", "text/plain", "302 Found", "Location: http://%s/\r\n" % IP)
        elif path in ("/", "/index.html"):
            size = __import__("os").stat(HTML)[6]
            w.write(
                "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                "Content-Encoding: gzip\r\nContent-Length: %d\r\n"
                "Cache-Control: no-store\r\nConnection: close\r\n\r\n" % size
            )
            buf = bytearray(1024)
            with open(HTML, "rb") as f:
                while True:
                    n = f.readinto(buf)
                    if not n:
                        break
                    w.write(memoryview(buf)[:n])
                    await w.drain()
        else:
            await _send(w, "not found", "text/plain", "404 Not Found")
    except Exception:
        pass
    finally:
        try:
            w.close()
            await w.wait_closed()
        except Exception:
            pass


async def _main():
    asyncio.create_task(_sensors())
    asyncio.create_task(_dns())
    await asyncio.start_server(_http, "0.0.0.0", 80, backlog=8)
    while True:
        await asyncio.sleep(3600)


def run(i2c_scan=None):
    """Start the hotspot and serve the game. Blocks until Ctrl-C.

    i2c_scan: optional function returning the addresses found on the I2C bus
    (as hex strings); the game's "robot bus" station shows them.
    """
    global _i2c_scan
    _i2c_scan = i2c_scan
    print("listening for nearby wifi (takes a few seconds)...")
    _listen()
    _hotspot()
    print('game on: join wifi "%s" -> http://%s.local  (or http://%s)' % (SSID, HOSTNAME, IP))
    try:
        asyncio.run(_main())
    finally:
        asyncio.new_event_loop()
