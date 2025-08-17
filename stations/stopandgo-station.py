#!/usr/bin/env python3
import os
import asyncio
import mmap
import struct
import json
import logging
from PIL import Image, ImageDraw, ImageFont
import pyedid
import aiohttp
import RPi.GPIO as GPIO
from smbus2_asyncio import SMBus2Asyncio

# GPIO Pin definitions
BUTTON_PIN = 18
SENSOR_PIN = 24

# I2C settings
I2C_BUS = 1
RELAY_ADDRESS = 0x10  # Adjust based on your relay board

# Font sizes
COUNTDOWN_FONT_SIZE = 200
TEAM_FONT_SIZE = 150

class I2CRelay:
    def __init__(self, bus=I2C_BUS, address=RELAY_ADDRESS):
        self.bus_num = bus
        self.address = address
        self.handle = None

    async def open(self):
        self.handle = SMBus2Asyncio(self.bus_num)
        await self.handle.open()

    async def turn_on(self):
        try:
            if self.handle is None:
                await self.open()
            await self.handle.write_byte(self.address, 0xFF)
        except Exception as e:
            logging.error(f"I2C relay on error: {e}")

    async def turn_off(self):
        try:
            if self.handle is None:
                await self.open()
            await self.handle.write_byte(self.address, 0x00)
        except Exception as e:
            logging.error(f"I2C relay off error: {e}")

    def close(self):
        pass

class FramebufferDisplay:
    def __init__(self):
        self.fb_device = '/dev/fb0'
        self.get_screen_info()
        self.fb_fd = os.open(self.fb_device, os.O_RDWR)
        self.fb_map = mmap.mmap(self.fb_fd, self.screen_size)

        # Load font
        try:
            self.countdown_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', COUNTDOWN_FONT_SIZE)
            self.team_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', TEAM_FONT_SIZE)
        except:
            self.countdown_font = ImageFont.load_default()
            self.team_font = ImageFont.load_default()

    def get_screen_info(self):
        try:
            # Try to get EDID data
            edid_data = self.read_edid()
            if edid_data:
                edid = pyedid.parse_edid(edid_data)
                if hasattr(edid, 'detailed_timings') and edid.detailed_timings:
                    timing = edid.detailed_timings[0]
                    self.width = timing.horizontal_active
                    self.height = timing.vertical_active
                    logging.info(f"EDID resolution: {self.width}x{self.height}")
                else:
                    raise ValueError("No detailed timings in EDID")
            else:
                raise ValueError("No EDID data")
        except Exception as e:
            logging.warning(f"EDID detection failed ({e}), using fallback resolution")
            self.width = 1920
            self.height = 1080

        self.bpp = 32
        self.screen_size = self.width * self.height * (self.bpp // 8)

    def read_edid(self):
        edid_paths = [
            '/sys/class/drm/card0-HDMI-A-1/edid',
            '/sys/class/drm/card0-HDMI-A-2/edid',
            '/sys/class/drm/card1-HDMI-A-1/edid',
            '/sys/devices/platform/gpu/drm/card0/card0-HDMI-A-1/edid'
        ]

        for path in edid_paths:
            try:
                if os.path.exists(path):
                    with open(path, 'rb') as f:
                        data = f.read()
                        if len(data) >= 128:
                            return data
            except Exception:
                continue
        return None

    def fill_screen(self, color):
        pixel = struct.pack('BBBB', color[2], color[1], color[0], 255)
        data = pixel * (self.width * self.height)
        self.fb_map.seek(0)
        self.fb_map.write(data)
        self.fb_map.flush()

    def display_text(self, text, bg_color, text_color, font=None):
        if font is None:
            font = self.countdown_font

        img = Image.new('RGB', (self.width, self.height), bg_color)
        draw = ImageDraw.Draw(img)

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (self.width - text_width) // 2
        y = (self.height - text_height) // 2

        draw.text((x, y), text, fill=text_color, font=font)
        self.display_image(img)

    def display_image(self, img):
        if img.size != (self.width, self.height):
            img = img.resize((self.width, self.height))

        data = b''
        for pixel in img.getdata():
            data += struct.pack('BBBB', pixel[2], pixel[1], pixel[0], 255)

        self.fb_map.seek(0)
        self.fb_map.write(data)
        self.fb_map.flush()

    def close(self):
        self.fb_map.close()
        os.close(self.fb_fd)

class StopAndGoStation:
    def __init__(self, websocket_url):
        self.websocket_url = websocket_url
        self.display = FramebufferDisplay()
        self.relay = I2CRelay()
        self.current_team = None
        self.current_duration = None
        self.state = "idle"  # idle, waiting_button, countdown, green, sensor_triggered
        self.countdown_task = None
        self.websocket = None
        self.penalty_ack_received = False

        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Initial state
        self.display.fill_screen((0, 0, 0))  # Black screen

    async def websocket_handler(self):
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(self.websocket_url) as ws:
                        self.websocket = ws
                        logging.info("WebSocket connected")
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    data = json.loads(msg.data)
                                    await self.handle_message(data)
                                except json.JSONDecodeError:
                                    logging.error("Invalid JSON received")
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                logging.error(f"WebSocket error: {ws.exception()}")
                                break
            except Exception as e:
                logging.error(f"WebSocket connection failed: {e}")
                self.websocket = None
                await asyncio.sleep(5)  # Wait before reconnecting

    async def handle_message(self, data):
        # Handle race command
        if "team" in data and "duration" in data:
            await self.handle_race_command(data)

        # Handle penalty acknowledgment
        if "team" in data and "served" in data and data["served"] == "ok":
            if data["team"] == self.current_team:
                self.penalty_ack_received = True
                logging.info(f"Penalty acknowledgment received for team {self.current_team}")

    async def send_penalty_ok(self):
        """Send penalty ok message every 5 seconds until acknowledged"""
        while self.state == "green" and not self.penalty_ack_received:
            if self.websocket:
                try:
                    message = {"team": self.current_team, "penalty": "ok"}
                    await self.websocket.send_str(json.dumps(message))
                    logging.info(f"Sent penalty ok for team {self.current_team}")
                except Exception as e:
                    logging.error(f"Failed to send penalty ok: {e}")
            await asyncio.sleep(5)

    async def handle_race_command(self, data):
        if "team" in data and "duration" in data:
            self.current_team = data["team"]
            self.current_duration = data["duration"]
            self.state = "waiting_button"
            self.penalty_ack_received = False  # Reset for new race

            # Turn on relay and show team number
            await self.relay.turn_on()
            self.display.display_text(str(self.current_team), (255, 165, 0), (0, 0, 0), self.display.team_font)
            logging.info(f"Race started for team {self.current_team}, duration {self.current_duration}s")

    async def button_monitor(self):
        button_pressed = False
        while True:
            current_state = not GPIO.input(BUTTON_PIN)  # Inverted because pull-up

            if current_state and not button_pressed and self.state == "waiting_button":
                button_pressed = True
                await self.start_countdown()
            elif not current_state:
                button_pressed = False

            await asyncio.sleep(0.1)

    async def sensor_monitor(self):
        sensor_triggered = False
        while True:
            current_state = not GPIO.input(SENSOR_PIN)  # Inverted because pull-up

            if current_state and not sensor_triggered:
                sensor_triggered = True
                if self.state in ["waiting_button", "countdown"]:
                    await self.handle_sensor_triggered()
                elif self.state == "green":
                    # Wait for sensor to go from triggered to not triggered
                    pass
            elif not current_state and sensor_triggered:
                sensor_triggered = False
                if self.state == "sensor_triggered":
                    await self.return_to_waiting()
                elif self.state == "green":
                    # Only reset if penalty was acknowledged
                    if self.penalty_ack_received:
                        await self.reset_to_idle()

            await asyncio.sleep(0.1)

    async def handle_sensor_triggered(self):
        if self.countdown_task:
            self.countdown_task.cancel()

        self.state = "sensor_triggered"
        self.display.display_text(str(self.current_team), (255, 0, 0), (255, 255, 0), self.display.team_font)
        logging.info("Sensor triggered - showing red screen")

    async def return_to_waiting(self):
        self.state = "waiting_button"
        self.display.display_text(str(self.current_team), (255, 165, 0), (0, 0, 0), self.display.team_font)
        logging.info("Sensor cleared - returning to orange screen")

    async def start_countdown(self):
        self.state = "countdown"
        await self.relay.turn_off()

        # Start countdown
        self.countdown_task = asyncio.create_task(self.countdown())
        try:
            await self.countdown_task
        except asyncio.CancelledError:
            pass

    async def countdown(self):
        for i in range(self.current_duration, 0, -1):
            if self.state != "countdown":
                return
            self.display.display_text(str(i), (255, 165, 0), (0, 0, 0))  # Uses countdown_font by default
            await asyncio.sleep(1)

        # Countdown finished
        self.state = "green"
        self.display.fill_screen((0, 255, 0))  # Green screen
        logging.info("Countdown finished - showing green screen")

        # Start sending penalty ok messages
        asyncio.create_task(self.send_penalty_ok())

    async def reset_to_idle(self):
        self.state = "idle"
        self.current_team = None
        self.current_duration = None
        self.display.fill_screen((0, 0, 0))  # Black screen
        await self.relay.turn_off()
        logging.info("Reset to idle state")

    async def run(self):
        tasks = [
            asyncio.create_task(self.websocket_handler()),
            asyncio.create_task(self.button_monitor()),
            asyncio.create_task(self.sensor_monitor())
        ]

        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logging.info("Shutting down...")
        finally:
            self.display.close()
            self.relay.close()
            GPIO.cleanup()

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Replace with your WebSocket URL
    websocket_url = "ws://race-control-server:8080/ws/stopandgo/"

    station = StopAndGoStation(websocket_url)
    await station.run()

if __name__ == "__main__":
    asyncio.run(main())
