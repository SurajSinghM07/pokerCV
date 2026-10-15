

from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from config import HUDConfig


@dataclass
class GameState:
    
    player_hand: List[str] = field(default_factory=list)
    community: List[str] = field(default_factory=list)
    phase: str = "waiting"
    changed: bool = False

    def all_known_cards(self) -> List[str]:
        
        return self.player_hand + self.community

    def __eq__(self, other):
        if not isinstance(other, GameState):
            return False
        return (
            sorted(self.player_hand) == sorted(other.player_hand)
            and sorted(self.community) == sorted(other.community)
        )


class StateTracker:
    

    def __init__(self, config: HUDConfig):
        self.config = config
        self.threshold = config.debounce.frame_threshold
        self._counters: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._stable_cards: Dict[str, Set[str]] = defaultdict(set)
        self._prev_state: Optional[GameState] = None

    def update(self, detections_by_zone: Dict[str, List[str]]) -> GameState:
        
        for zone_name in self.config.zones:
            detected_this_frame = set(detections_by_zone.get(zone_name, []))
            zone_counters = self._counters[zone_name]
            all_tracked = set(zone_counters.keys()) | detected_this_frame

            cards_to_remove = []

            for card in all_tracked:
                if card in detected_this_frame:
                    zone_counters[card] = min(zone_counters[card] + 1, self.threshold)
                else:
                    zone_counters[card] = max(zone_counters[card] - 1, 0)
                if zone_counters[card] >= self.threshold:
                    self._stable_cards[zone_name].add(card)
                elif zone_counters[card] <= 0:
                    self._stable_cards[zone_name].discard(card)
                    cards_to_remove.append(card)
            for card in cards_to_remove:
                del zone_counters[card]
        player_hand_set = set(self._stable_cards.get("player_hand", set()))
        community_set = set(self._stable_cards.get("community", set()))
        community_set -= player_hand_set

        player_hand = sorted(player_hand_set)
        community = sorted(community_set)
        phase = self._determine_phase(player_hand, community)
        current_state = GameState(
            player_hand=player_hand,
            community=community,
            phase=phase,
            changed=False,
        )

        changed = self._prev_state is None or current_state != self._prev_state
        current_state.changed = changed
        self._prev_state = GameState(
            player_hand=list(player_hand),
            community=list(community),
            phase=phase,
            changed=False,
        )

        return current_state

    def reset(self):
        
        self._counters.clear()
        self._stable_cards.clear()
        self._prev_state = None

    @staticmethod
    def _determine_phase(player_hand: List[str], community: List[str]) -> str:
        
        n_community = len(community)
        n_player = len(player_hand)

        if n_player == 0:
            return "waiting"
        elif n_community == 0 or n_community < 3:
            return "preflop"
        elif n_community == 3:
            return "flop"
        elif n_community == 4:
            return "turn"
        elif n_community >= 5:
            return "river"
        return "unknown"
