from dataclasses import dataclass, field
from typing import Dict, Tuple, List


@dataclass
class ZoneRect:
    x: int
    y: int
    w: int
    h: int

    def contains(self, cx: float, cy: float) -> bool:
        return self.x <= cx <= self.x + self.w and self.y <= cy <= self.y + self.h

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)


@dataclass
class CameraConfig:
    device_index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30


@dataclass
class YOLOConfig:
    model_path: str = "best.pt"
    confidence_threshold: float = 0.5
    iou_threshold: float = 0.45
    device: str = ""


@dataclass
class DebounceConfig:
    frame_threshold: int = 15


@dataclass
class EquityConfig:
    num_simulations: int = 10000
    timeout_seconds: float = 2.0


RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["c", "d", "h", "s"]

DEFAULT_CLASS_MAP: Dict[int, str] = {}
_idx = 0
for _suit in SUITS:
    for _rank in RANKS:
        DEFAULT_CLASS_MAP[_idx] = f"{_rank}{_suit}"
        _idx += 1


@dataclass
class HUDConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    yolo: YOLOConfig = field(default_factory=YOLOConfig)
    debounce: DebounceConfig = field(default_factory=DebounceConfig)
    equity: EquityConfig = field(default_factory=EquityConfig)

    zones: Dict[str, ZoneRect] = field(default_factory=lambda: {
        "player_hand": ZoneRect(x=340, y=520, w=600, h=190),
        "community":   ZoneRect(x=140, y=200, w=1000, h=290),
    })

    class_map: Dict[int, str] = field(default_factory=lambda: dict(DEFAULT_CLASS_MAP))

    ws_host: str = "127.0.0.1"
    ws_port: int = 8765

    def get_zone_for_point(self, cx: float, cy: float) -> str | None:
        for zone_name, rect in self.zones.items():
            if rect.contains(cx, cy):
                return zone_name
        return None
