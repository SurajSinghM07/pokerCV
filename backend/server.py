

import asyncio
import base64
import json
import signal
import sys
import threading
import time
from collections import defaultdict
from typing import Optional, Set

import cv2
import numpy as np
import websockets
try:
    from websockets.asyncio.server import serve, ServerConnection
    WSConnection = ServerConnection
except ImportError:
    from websockets.server import serve
    WSConnection = websockets.WebSocketServerProtocol

from config import HUDConfig, ZoneRect
from vision import VisionEngine, CardDetection
from state_tracker import StateTracker, GameState
from equity import EquityEngine, EquityResult
from overlay import OverlayRenderer


class JsonEncoder(json.JSONEncoder):
    
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class PokerHUDServer:
    

    def __init__(self, config: Optional[HUDConfig] = None):
        self.config = config or HUDConfig()
        self.vision = VisionEngine(self.config)
        self.tracker = StateTracker(self.config)
        self.equity = EquityEngine(self.config)
        self.overlay = OverlayRenderer(self.config)

        self._clients: Set[WSConnection] = set()
        self._running = False
        self._latest_state: Optional[GameState] = None
        self._latest_equity: Optional[EquityResult] = None
        self._frame_count = 0
        self._skip_counter = 0
        self._fps = 0.0
        self._fps_timer = time.time()

    async def _handle_client(self, websocket: WSConnection):
        
        self._clients.add(websocket)
        client_addr = websocket.remote_address
        print(f"[Server] Client connected: {client_addr}")

        cameras = await asyncio.to_thread(self.vision.list_cameras)
        await websocket.send(json.dumps({
            "type": "camera_list",
            "cameras": cameras,
            "active": self.config.camera.device_index,
        }))

        try:
            async for message in websocket:
                await self._handle_message(websocket, message)
        except websockets.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            print(f"[Server] Client disconnected: {client_addr}")

    async def _handle_message(self, websocket, message: str):
        
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "update_zones":
                zones = data.get("zones", {})
                for zone_name, rect_data in zones.items():
                    self.config.zones[zone_name] = ZoneRect(
                        x=int(rect_data["x"]),
                        y=int(rect_data["y"]),
                        w=int(rect_data["w"]),
                        h=int(rect_data["h"]),
                    )
                self.tracker.reset()
                print(f"[Server] Zones updated: {self.config.zones}")

            elif msg_type == "update_config":
                if "confidence" in data:
                    self.config.yolo.confidence_threshold = float(data["confidence"])
                if "debounce_frames" in data:
                    self.config.debounce.frame_threshold = int(data["debounce_frames"])
                    self.tracker.threshold = self.config.debounce.frame_threshold
                if "num_simulations" in data:
                    self.config.equity.num_simulations = int(data["num_simulations"])
                print(f"[Server] Config updated")

            elif msg_type == "reset":
                self.tracker.reset()
                self._latest_equity = None
                print("[Server] State reset")

            elif msg_type == "toggle_camera":
                enabled = data.get("enabled", True)
                if enabled:
                    print("[Server] Starting camera...")
                    self.vision.start()
                else:
                    print("[Server] Stopping camera...")
                    self.vision.stop()

            elif msg_type == "list_cameras":
                cameras = await asyncio.to_thread(self.vision.list_cameras)
                await websocket.send(json.dumps({
                    "type": "camera_list",
                    "cameras": cameras,
                    "active": self.config.camera.device_index,
                }))

            elif msg_type == "switch_camera":
                device_index = int(data.get("device_index", 0))
                print(f"[Server] Switching camera to index {device_index}")
                success = await asyncio.to_thread(self.vision.set_camera, device_index)
                if not success:
                    print(f"[Server] Failed to switch to camera {device_index}")
                self.tracker.reset()

            elif msg_type == "ping":
                await websocket.send(json.dumps({"type": "pong"}))

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"[Server] Invalid message: {e}")

    async def _broadcast(self, message: str):
        
        if not self._clients:
            return
            
        async def send_to(client):
            try:
                await client.send(message)
            except websockets.ConnectionClosed:
                return client
            return None

        results = await asyncio.gather(*(send_to(client) for client in self._clients))
        disconnected = {client for client in results if client is not None}
        self._clients -= disconnected

    def _pipeline_step(self) -> Optional[str]:
        
        frame = self.vision.read_frame()
        if frame is None:
            return None
        self._skip_counter += 1
        if self._skip_counter % 3 == 0 or getattr(self, '_last_detections', None) is None:
            self._last_detections = self.vision.detect_cards(frame)
        detections = self._last_detections
        detections_by_zone = defaultdict(list)
        for det in detections:
            if det.zone:
                detections_by_zone[det.zone].append(det.card_name)
        game_state = self.tracker.update(dict(detections_by_zone))
        self._latest_state = game_state
        if game_state.changed and len(game_state.player_hand) == 2:
            self.equity.compute_async(game_state.player_hand, game_state.community)
        equity_result = self.equity.get_result()
        if equity_result is not None:
            self._latest_equity = equity_result
        frame = self.overlay.render(frame, detections, game_state, self._latest_equity)
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_b64 = base64.b64encode(buffer).decode('utf-8')
        self._frame_count += 1
        now = time.time()
        elapsed = now - self._fps_timer
        if elapsed >= 1.0:
            self._fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_timer = now

        return frame_b64

    def _build_state_json(self) -> str:
        
        state = self._latest_state
        equity = self._latest_equity

        payload = {
            "type": "state",
            "fps": round(self._fps, 1),
            "game_state": {
                "player_hand": state.player_hand if state else [],
                "community": state.community if state else [],
                "phase": state.phase if state else "waiting",
                "changed": state.changed if state else False,
            },
            "equity": None,
            "zones": {
                name: {"x": r.x, "y": r.y, "w": r.w, "h": r.h}
                for name, r in self.config.zones.items()
            },
        }

        if equity and state and len(state.player_hand) == 2:
            if equity.player_hand == state.player_hand and equity.community == state.community:
                payload["equity"] = {
                    "win": equity.win_pct,
                    "tie": equity.tie_pct,
                    "lose": equity.lose_pct,
                    "samples": equity.samples,
                    "hand_rank": equity.hand_rank_str,
                    "recommendation": equity.recommendation,
                    "computation_ms": equity.computation_time_ms,
                }

        return json.dumps(payload, cls=JsonEncoder)

    async def _main_loop(self):
        
        print("[Server] Starting pipeline...")

        if not self.vision.start():
            print("[Server] Failed to start vision engine. Exiting.")
            return

        self._running = True
        frame_interval = 1.0 / self.config.camera.fps

        try:
            while self._running:
                loop_start = time.time()
                frame_b64 = self._pipeline_step()

                if frame_b64 and self._clients:
                    frame_msg = json.dumps({
                        "type": "frame",
                        "data": frame_b64,
                    })
                    await self._broadcast(frame_msg)
                    if self._frame_count % 3 == 0 or (self._latest_state and self._latest_state.changed):
                        state_msg = self._build_state_json()
                        await self._broadcast(state_msg)
                elapsed = time.time() - loop_start
                sleep_time = max(0, frame_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0.001)

        finally:
            self.vision.stop()
            print("[Server] Pipeline stopped")

    async def run(self):
        
        host = self.config.ws_host
        port = self.config.ws_port

        print(f"[Server] Starting WebSocket server on ws://{host}:{port}")

        async with serve(
            self._handle_client,
            host,
            port,
            max_size=10 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=60,
        ):
            await self._main_loop()

    def stop(self):
        
        self._running = False


def main():
    
    config = HUDConfig()
    import argparse
    parser = argparse.ArgumentParser(description="pokerCV Backend Server")
    parser.add_argument("--camera", type=int, default=0, help="Camera device index")
    parser.add_argument("--model", type=str, default="best.pt", help="YOLO model path")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port")
    parser.add_argument("--confidence", type=float, default=0.5, help="YOLO confidence threshold")
    parser.add_argument("--simulations", type=int, default=10000, help="Monte Carlo simulations")
    parser.add_argument("--width", type=int, default=1280, help="Camera width")
    parser.add_argument("--height", type=int, default=720, help="Camera height")
    args = parser.parse_args()

    config.camera.device_index = args.camera
    config.camera.width = args.width
    config.camera.height = args.height
    config.yolo.model_path = args.model
    config.yolo.confidence_threshold = args.confidence
    config.equity.num_simulations = args.simulations
    config.ws_port = args.port

    server = PokerHUDServer(config)
    def signal_handler(sig, frame):
        print("\n[Server] Shutting down...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 60)
    print("  pokerCV — Backend Server")
    print("=" * 60)
    print(f"  Camera:      {config.camera.device_index} ({config.camera.width}x{config.camera.height})")
    print(f"  YOLO Model:  {config.yolo.model_path}")
    print(f"  Confidence:  {config.yolo.confidence_threshold}")
    print(f"  Debounce:    {config.debounce.frame_threshold} frames")
    print(f"  Simulations: {config.equity.num_simulations}")
    print(f"  WebSocket:   ws://{config.ws_host}:{config.ws_port}")
    print("=" * 60)

    asyncio.run(server.run())


if __name__ == "__main__":
    main()
