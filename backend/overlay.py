

import cv2
import numpy as np
from typing import List, Optional, Dict, Tuple

from config import HUDConfig, ZoneRect
from vision import CardDetection
from equity import EquityResult
from state_tracker import GameState
COLORS = {
    "bg_dark":       (20, 20, 25),
    "bg_panel":      (35, 35, 45),
    "accent_green":  (80, 220, 120),
    "accent_red":    (80, 80, 230),
    "accent_blue":   (230, 160, 60),
    "accent_yellow": (50, 220, 230),
    "text_white":    (240, 240, 245),
    "text_dim":      (140, 140, 150),
    "zone_player":   (80, 220, 120),
    "zone_community":(230, 160, 60),
    "bbox_card":     (50, 220, 230),
}
PHASE_DISPLAY = {
    "waiting":  ("WAITING FOR CARDS", COLORS["text_dim"]),
    "preflop":  ("● PRE-FLOP", COLORS["accent_yellow"]),
    "flop":     ("● FLOP", COLORS["accent_blue"]),
    "turn":     ("● TURN", COLORS["accent_green"]),
    "river":    ("● RIVER", COLORS["accent_red"]),
    "unknown":  ("UNKNOWN", COLORS["text_dim"]),
}


class OverlayRenderer:
    

    def __init__(self, config: HUDConfig):
        self.config = config
        self._font = cv2.FONT_HERSHEY_SIMPLEX
        self._font_small = cv2.FONT_HERSHEY_SIMPLEX

    def render(
        self,
        frame: np.ndarray,
        detections: List[CardDetection],
        game_state: GameState,
        equity_result: Optional[EquityResult],
    ) -> np.ndarray:
        
        overlay = frame.copy()

        self._draw_zones(overlay)
        self._draw_detections(overlay, detections)
        self._draw_phase_badge(overlay, game_state, is_bg=True)
        self._draw_equity_panel(overlay, equity_result, game_state, is_bg=True)
        
        cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)
        
        self._draw_phase_badge(frame, game_state, is_bg=False)
        self._draw_card_list(frame, game_state)
        self._draw_equity_panel(frame, equity_result, game_state, is_bg=False)

        return frame

    def _draw_zones(self, frame: np.ndarray):
        
        zone_colors = {
            "player_hand": COLORS["zone_player"],
            "community": COLORS["zone_community"],
        }
        zone_labels = {
            "player_hand": "YOUR HAND",
            "community": "COMMUNITY",
        }

        for zone_name, rect in self.config.zones.items():
            color = zone_colors.get(zone_name, COLORS["text_dim"])
            label = zone_labels.get(zone_name, zone_name.upper())
            sub = frame[rect.y:rect.y + rect.h, rect.x:rect.x + rect.w]
            if sub.size > 0:
                tint = np.full_like(sub, color)
                cv2.addWeighted(tint, 0.08, sub, 0.92, 0, sub)
            cv2.rectangle(frame, (rect.x, rect.y), (rect.x + rect.w, rect.y + rect.h),
                         color, 2, cv2.LINE_AA)
            cv2.putText(frame, label, (rect.x + 8, rect.y - 8),
                       self._font, 0.5, color, 1, cv2.LINE_AA)

    def _draw_detections(self, frame: np.ndarray, detections: List[CardDetection]):
        
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = COLORS["bbox_card"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
            label = f"{det.card_name} {det.confidence:.0%}"
            (tw, th), _ = cv2.getTextSize(label, self._font, 0.45, 1)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 8, y1), color, -1)
            cv2.putText(frame, label, (x1 + 4, y1 - 4),
                       self._font, 0.45, COLORS["bg_dark"], 1, cv2.LINE_AA)

    def _draw_phase_badge(self, frame: np.ndarray, state: GameState, is_bg: bool = True):
        
        h, w = frame.shape[:2]
        label, color = PHASE_DISPLAY.get(state.phase, PHASE_DISPLAY["unknown"])
        (tw, th), _ = cv2.getTextSize(label, self._font, 0.6, 2)
        bx, by = 15, 35
        
        if is_bg:
            cv2.rectangle(frame, (bx - 5, by - th - 8), (bx + tw + 10, by + 8),
                         COLORS["bg_panel"], -1)
            cv2.rectangle(frame, (bx - 5, by - th - 8), (bx + tw + 10, by + 8),
                         color, 1, cv2.LINE_AA)
        else:
            cv2.putText(frame, label, (bx, by), self._font, 0.6, color, 2, cv2.LINE_AA)

    def _draw_card_list(self, frame: np.ndarray, state: GameState):
        
        h, w = frame.shape[:2]
        y_offset = 75
        hand_text = "Hand: " + (", ".join(state.player_hand) if state.player_hand else "—")
        cv2.putText(frame, hand_text, (15, y_offset),
                   self._font, 0.5, COLORS["zone_player"], 1, cv2.LINE_AA)
        comm_text = "Board: " + (", ".join(state.community) if state.community else "—")
        cv2.putText(frame, comm_text, (15, y_offset + 25),
                   self._font, 0.5, COLORS["zone_community"], 1, cv2.LINE_AA)

    def _draw_equity_panel(
        self,
        frame: np.ndarray,
        equity: Optional[EquityResult],
        state: GameState,
        is_bg: bool = True
    ):
        
        h, w = frame.shape[:2]

        panel_w = 280
        panel_h = 130
        px = w - panel_w - 15
        py = 15
        
        if is_bg:
            cv2.rectangle(frame, (px, py), (px + panel_w, py + panel_h),
                         COLORS["bg_panel"], -1)
            cv2.rectangle(frame, (px, py), (px + panel_w, py + panel_h),
                         COLORS["text_dim"], 1, cv2.LINE_AA)
            return

        cv2.putText(frame, "EQUITY", (px + 10, py + 22),
                   self._font, 0.55, COLORS["text_white"], 1, cv2.LINE_AA)

        if equity is None or len(state.player_hand) < 2:
            cv2.putText(frame, "Waiting for hole cards...",
                       (px + 10, py + 55), self._font, 0.4, COLORS["text_dim"], 1, cv2.LINE_AA)
            return
        y = py + 48
        self._draw_pct_line(frame, px + 10, y, "WIN", equity.win_pct, COLORS["accent_green"])
        y += 22
        self._draw_pct_line(frame, px + 10, y, "TIE", equity.tie_pct, COLORS["accent_yellow"])
        y += 22
        self._draw_pct_line(frame, px + 10, y, "LOSE", equity.lose_pct, COLORS["accent_red"])
        bar_x = px + 10
        bar_y = y + 10
        bar_w = panel_w - 20
        bar_h = 12

        win_w = int(bar_w * equity.win_pct / 100)
        tie_w = int(bar_w * equity.tie_pct / 100)

        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h),
                     COLORS["accent_red"], -1)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + win_w + tie_w, bar_y + bar_h),
                     COLORS["accent_yellow"], -1)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + win_w, bar_y + bar_h),
                     COLORS["accent_green"], -1)
        if equity.hand_rank_str:
            cv2.putText(frame, equity.hand_rank_str,
                       (px + 10, py + panel_h - 8), self._font, 0.4,
                       COLORS["accent_blue"], 1, cv2.LINE_AA)
        sim_text = f"{equity.samples:,} sims • {equity.computation_time_ms:.0f}ms"
        cv2.putText(frame, sim_text,
                   (px + panel_w - 160, py + panel_h - 8), self._font, 0.35,
                   COLORS["text_dim"], 1, cv2.LINE_AA)

    def _draw_pct_line(
        self, frame: np.ndarray,
        x: int, y: int,
        label: str, pct: float,
        color: Tuple[int, int, int],
    ):
        
        cv2.putText(frame, f"{label:4s}", (x, y),
                   self._font, 0.45, COLORS["text_dim"], 1, cv2.LINE_AA)
        cv2.putText(frame, f"{pct:5.1f}%", (x + 55, y),
                   self._font, 0.5, color, 1, cv2.LINE_AA)
