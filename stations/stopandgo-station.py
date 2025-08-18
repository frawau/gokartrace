#!/usr/bin/env python3
import os
import asyncio
import mmap
import struct
import json
import logging
import argparse
import hmac
import hashlib
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import RPi.GPIO as GPIO
from smbus2_asyncio import SMBus2Asyncio

# Default GPIO Pin definitions (will be overridden by command line args)
DEFAULT_BUTTON_PIN = 18  # Physical pin 18 (GPIO24)
DEFAULT_SENSOR_PIN = 24  # Physical pin 24 (GPIO8)

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
            await self.handle.write_byte_data(self.address, 0, 0xFF)
        except Exception as e:
            logging.error(f"I2C relay on error: {e}")

    async def turn_off(self):
        try:
            if self.handle is None:
                await self.open()
            await self.handle.write_byte_data(self.address, 0, 0x00)
        except Exception as e:
            logging.error(f"I2C relay off error: {e}")

    def close(self):
        pass


class FramebufferDisplay:
    def __init__(self):
        self.fb_device = "/dev/fb0"
        self.get_screen_info()
        self.fb_fd = os.open(self.fb_device, os.O_RDWR)
        self.fb_map = mmap.mmap(self.fb_fd, self.screen_size)

        # Load font
        try:
            self.countdown_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                COUNTDOWN_FONT_SIZE,
            )
            self.team_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", TEAM_FONT_SIZE
            )
        except:
            self.countdown_font = ImageFont.load_default()
            self.team_font = ImageFont.load_default()

    def get_screen_info(self):
        # Try to detect from /sys/class/graphics/fb0/virtual_size first
        try:
            with open("/sys/class/graphics/fb0/virtual_size", "r") as f:
                size_str = f.read().strip()
                width, height = map(int, size_str.split(","))
                self.width = width
                self.height = height
                logging.info(f"Detected framebuffer size: {self.width}x{self.height}")
        except Exception as e:
            logging.warning(
                f"Framebuffer size detection failed ({e}), using fallback resolution"
            )
            self.width = 1920
            self.height = 1080

        self.bpp = 32
        self.screen_size = self.width * self.height * (self.bpp // 8)

    def fill_screen(self, color):
        pixel = struct.pack("BBBB", color[2], color[1], color[0], 255)
        data = pixel * (self.width * self.height)
        self.fb_map.seek(0)
        self.fb_map.write(data)
        self.fb_map.flush()

    def display_text(self, text, bg_color, text_color, font=None):
        if font is None:
            font = self.countdown_font

        img = Image.new("RGB", (self.width, self.height), bg_color)
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

        # Convert RGB to BGRA efficiently using numpy
        try:
            import numpy as np

            # Convert PIL image to numpy array
            rgb_array = np.array(img)

            # Create BGRA array
            bgra_array = np.zeros((self.height, self.width, 4), dtype=np.uint8)
            bgra_array[:, :, 0] = rgb_array[:, :, 2]  # B
            bgra_array[:, :, 1] = rgb_array[:, :, 1]  # G
            bgra_array[:, :, 2] = rgb_array[:, :, 0]  # R
            bgra_array[:, :, 3] = 255  # A

            data = bgra_array.tobytes()

        except ImportError:
            # Fallback: use PIL's built-in conversion (slower but works)
            logging.warning("NumPy not available, using slower conversion...")

            # Convert to RGBA first, then swap channels
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Get raw pixel data
            pixels = img.tobytes()

            # Convert RGBA to BGRA
            data = b""
            for i in range(0, len(pixels), 4):
                r, g, b, a = pixels[i : i + 4]
                data += struct.pack("BBBB", b, g, r, 255)

        self.fb_map.seek(0)
        self.fb_map.write(data)
        self.fb_map.flush()

    def close(self):
        self.fb_map.close()
        os.close(self.fb_fd)


class StopAndGoStation:
    def __init__(self, websocket_url, button_pin, sensor_pin, hmac_secret):
        self.websocket_url = websocket_url
        self.button_pin = button_pin
        self.sensor_pin = sensor_pin
        self.hmac_secret = hmac_secret.encode("utf-8")  # Convert to bytes
        self.display = FramebufferDisplay()
        self.relay = I2CRelay()
        self.current_team = None
        self.current_duration = None
        self.state = (
            "idle"  # idle, waiting_button, countdown, green, sensor_triggered, what_now
        )
        self.countdown_task = None
        self.websocket = None
        self.penalty_ack_received = False
        self.connected = False
        self.fence_enabled = True  # Default: fence function enabled

        # Setup GPIO
        GPIO.setmode(GPIO.BOARD)  # Use physical pin numbers
        GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.sensor_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Initial state - show connecting
        self.display.display_text("Connecting", (255, 255, 0), (0, 0, 0))

    async def websocket_handler(self):
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(self.websocket_url) as ws:
                        self.websocket = ws
                        self.connected = True
                        logging.info("WebSocket connected")

                        # Show race mode screen when connected
                        if self.state == "idle":
                            self.display.display_text(
                                "Race Mode", (0, 255, 0), (0, 0, 0)
                            )

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
                self.connected = False

                # Show connecting screen when disconnected
                if self.state == "idle":
                    self.display.display_text("Connecting", (255, 255, 0), (0, 0, 0))

                await asyncio.sleep(5)  # Wait before reconnecting

    def verify_hmac(self, message_data, provided_signature):
        """Verify HMAC signature for incoming message"""
        # Create message string from data (excluding signature)
        message_str = json.dumps(message_data, sort_keys=False, separators=(",", ":"))
        expected_signature = hmac.new(
            self.hmac_secret,
            message_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected_signature, provided_signature)

    def sign_message(self, message_data):
        """Sign outgoing message with HMAC"""
        message_str = json.dumps(message_data, sort_keys=False, separators=(",", ":"))
        signature = hmac.new(
            self.hmac_secret,
            message_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        message_data["hmac_signature"] = signature
        return message_data

    async def handle_message(self, data):
        # Verify HMAC signature for all incoming messages
        provided_signature = data.pop("hmac_signature", None)
        if not provided_signature:
            logging.warning("Received message without HMAC signature")
            return

        if not self.verify_hmac(data, provided_signature):
            logging.warning("HMAC verification failed - rejecting message")
            return

        logging.debug("HMAC verification successful")  # Use debug to reduce log spam

        # Only process messages marked as commands
        if data.get("type") != "command":
            return

        command = data.get("command")

        # Handle race command
        if command == "start_race" and "team" in data and "duration" in data:
            await self.handle_race_command(data)

        # Handle penalty acknowledgment
        elif command == "penalty_ack" and "team" in data:
            if data["team"] == self.current_team:
                self.penalty_ack_received = True
                logging.info(
                    f"Penalty acknowledgment received for team {self.current_team}"
                )

        # Handle fence enable/disable command
        elif command == "set_fence":
            self.fence_enabled = data.get("enabled", True)
            logging.info(
                f"Fence function {'enabled' if self.fence_enabled else 'disabled'}"
            )
            # Send response
            await self.send_response("fence_status", {"enabled": self.fence_enabled})

        # Handle fence status query
        elif command == "get_fence_status":
            await self.send_response("fence_status", {"enabled": self.fence_enabled})

        # Handle force penalty completion
        elif command == "force_complete":
            if self.state == "green" and self.current_team:
                logging.info(f"Force completing penalty for team {self.current_team}")
                await self.reset_to_idle()
                await self.send_response(
                    "penalty_completed", {"team": self.current_team}
                )

    async def send_response(self, response_type, data):
        """Send a response message via websocket with HMAC signature"""
        if self.websocket:
            try:
                message = {
                    "type": "response",
                    "response": response_type,
                    "timestamp": datetime.now().isoformat(),
                    **data,
                }
                # Sign the message
                signed_message = self.sign_message(message)
                await self.websocket.send_str(json.dumps(signed_message))
                logging.info(f"Sent signed response: {response_type}")
            except Exception as e:
                logging.error(f"Failed to send response: {e}")

    async def send_penalty_ok(self):
        """Send penalty ok message every 5 seconds until acknowledged"""
        while self.state == "green" and not self.penalty_ack_received:
            await self.send_response("penalty_served", {"team": self.current_team})
            await asyncio.sleep(5)

    async def handle_race_command(self, data):
        if "team" in data and "duration" in data:
            self.current_team = data["team"]
            self.current_duration = data["duration"]
            self.state = "waiting_button"
            self.penalty_ack_received = False  # Reset for new race

            # Turn on relay and show team number
            await self.relay.turn_on()
            self.display.display_text(
                str(self.current_team), (255, 165, 0), (0, 0, 0), self.display.team_font
            )
            logging.info(
                f"Race started for team {self.current_team}, duration {self.current_duration}s"
            )

    async def button_monitor(self):
        button_pressed = False
        while True:
            current_state = not GPIO.input(self.button_pin)  # Inverted because pull-up

            if current_state and not button_pressed:
                button_pressed = True
                if self.state == "waiting_button":
                    await self.start_countdown()
                elif self.state == "idle" and self.connected:
                    # Button pressed when no stop and go is active
                    await self.show_what_now()
            elif not current_state:
                button_pressed = False

            await asyncio.sleep(0.1)

    async def sensor_monitor(self):
        sensor_triggered = False
        while True:
            # Only monitor sensor if fence function is enabled
            if self.fence_enabled:
                current_state = not GPIO.input(
                    self.sensor_pin
                )  # Inverted because pull-up

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
            else:
                # If fence is disabled, reset sensor state
                sensor_triggered = False

            await asyncio.sleep(0.1)

    async def handle_sensor_triggered(self):
        if self.countdown_task:
            self.countdown_task.cancel()

        self.state = "sensor_triggered"
        self.display.display_text(
            str(self.current_team), (255, 0, 0), (255, 255, 0), self.display.team_font
        )
        logging.info("Sensor triggered - showing red screen")

    async def return_to_waiting(self):
        self.state = "waiting_button"
        self.display.display_text(
            str(self.current_team), (255, 165, 0), (0, 0, 0), self.display.team_font
        )
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
            self.display.display_text(
                str(i), (255, 165, 0), (0, 0, 0)
            )  # Uses countdown_font by default
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
        await self.relay.turn_off()

        # Show appropriate idle screen based on connection status
        if self.connected:
            self.display.display_text("Race Mode", (0, 255, 0), (0, 0, 0))
        else:
            self.display.display_text("Connecting", (255, 255, 0), (0, 0, 0))

        logging.info("Reset to idle state")

    async def show_what_now(self):
        """Show 'What Now?' screen for 3 seconds when button pressed in idle state"""
        self.state = "what_now"
        self.display.display_text(
            "What Now?", (0, 0, 255), (255, 255, 255)
        )  # Blue background, white text
        logging.info("Button pressed in idle state - showing 'What Now?' screen")

        await asyncio.sleep(3)

        # Return to appropriate idle screen
        if self.state == "what_now":  # Make sure we haven't changed state
            await self.reset_to_idle()

    async def run(self):
        tasks = [
            asyncio.create_task(self.websocket_handler()),
            asyncio.create_task(self.button_monitor()),
            asyncio.create_task(self.sensor_monitor()),
        ]

        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logging.info("Shutting down...")
        finally:
            self.display.close()
            self.relay.close()
            GPIO.cleanup()


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Stop and Go Station for Go-Kart Racing"
    )
    parser.add_argument(
        "-s",
        "--server",
        default="gokart.wautier.eu",
        help="Server hostname (default: gokart.wautier.eu)",
    )
    parser.add_argument(
        "-p", "--port", type=int, default=8000, help="Server port (default: 8000)"
    )
    parser.add_argument(
        "-b",
        "--button",
        type=int,
        default=DEFAULT_BUTTON_PIN,
        help=f"Physical button pin number (default: {DEFAULT_BUTTON_PIN})",
    )
    parser.add_argument(
        "-f",
        "--fence",
        type=int,
        default=DEFAULT_SENSOR_PIN,
        help=f"Physical fence sensor pin number (default: {DEFAULT_SENSOR_PIN})",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Set log level to DEBUG"
    )
    parser.add_argument(
        "-i", "--info", action="store_true", help="Set log level to INFO"
    )
    parser.add_argument(
        "--hmac-secret",
        default="race_control_hmac_key_2024",
        help="HMAC secret key for message authentication (default: race_control_hmac_key_2024)",
    )
    return parser.parse_args()


async def main():
    args = parse_arguments()

    # Set log level based on arguments
    log_level = logging.WARNING  # Default
    if args.debug:
        log_level = logging.DEBUG
    elif args.info:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Build WebSocket URL from arguments
    websocket_url = f"ws://{args.server}:{args.port}/ws/stopandgo/"
    logging.info(f"Connecting to: {websocket_url}")
    logging.info(f"Button pin: {args.button}, Fence sensor pin: {args.fence}")

    station = StopAndGoStation(websocket_url, args.button, args.fence, args.hmac_secret)
    await station.run()


if __name__ == "__main__":
    asyncio.run(main())
