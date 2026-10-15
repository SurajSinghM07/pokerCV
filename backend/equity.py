

import itertools
import random
import threading
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from treys import Card, Evaluator, Deck

from config import HUDConfig


@dataclass
class EquityResult:
    
    win_pct: float = 0.0
    tie_pct: float = 0.0
    lose_pct: float = 0.0
    samples: int = 0
    player_hand: List[str] = field(default_factory=list)
    community: List[str] = field(default_factory=list)
    hand_rank_str: str = ""
    recommendation: str = ""
    computation_time_ms: float = 0.0


class EquityEngine:
    

    def __init__(self, config: HUDConfig):
        self.config = config
        self._evaluator = Evaluator()
        self._lock = threading.Lock()
        self._current_result: Optional[EquityResult] = None
        self._computing = False
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def _card_str_to_treys(card_str: str) -> int:
        
        return Card.new(card_str)

    @staticmethod
    def _build_remaining_deck(known_cards: List[int]) -> List[int]:
        
        full_deck = Deck.GetFullDeck()
        known_set = set(known_cards)
        return [c for c in full_deck if c not in known_set]

    def compute_equity(
        self,
        player_hand: List[str],
        community: List[str],
    ) -> Optional[EquityResult]:
        
        if len(player_hand) != 2:
            return None

        if len(community) > 5:
            return None

        start_time = time.perf_counter()

        try:
            player_treys = [self._card_str_to_treys(c) for c in player_hand]
            community_treys = [self._card_str_to_treys(c) for c in community]
        except (KeyError, ValueError) as e:
            print(f"[EquityEngine] Invalid card: {e}")
            return None

        known = player_treys + community_treys
        remaining = self._build_remaining_deck(known)
        community_needed = 5 - len(community_treys)

        wins = 0
        ties = 0
        losses = 0

        if community_needed == 0:
            opp_hands = list(itertools.combinations(remaining, 2))
            n_sims = len(opp_hands)
            
            player_score = self._evaluator.evaluate(community_treys, player_treys)
            for opp_hand in opp_hands:
                opp_score = self._evaluator.evaluate(community_treys, list(opp_hand))
                if player_score < opp_score:
                    wins += 1
                elif player_score == opp_score:
                    ties += 1
                else:
                    losses += 1
        else:
            n_sims = self.config.equity.num_simulations
            timeout = self.config.equity.timeout_seconds

            for i in range(n_sims):
                if i > 0 and i % 1000 == 0:
                    elapsed = time.perf_counter() - start_time
                    if elapsed > timeout:
                        n_sims = i
                        break
                random.shuffle(remaining)
                opp_hand = remaining[0:2]
                extra_community = remaining[2:2 + community_needed]
                full_community = community_treys + extra_community
                player_score = self._evaluator.evaluate(full_community, player_treys)
                opp_score = self._evaluator.evaluate(full_community, opp_hand)
                if player_score < opp_score:
                    wins += 1
                elif player_score == opp_score:
                    ties += 1
                else:
                    losses += 1

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        hand_rank_str = ""
        if len(community_treys) >= 3:
            try:
                score = self._evaluator.evaluate(community_treys, player_treys)
                hand_rank_class = self._evaluator.get_rank_class(score)
                hand_rank_str = self._evaluator.class_to_string(hand_rank_class)
            except Exception:
                pass

        total = wins + ties + losses
        win_pct = round((wins / total) * 100, 1) if total > 0 else 0
        tie_pct = round((ties / total) * 100, 1) if total > 0 else 0
        lose_pct = round(100.0 - win_pct - tie_pct, 1) if total > 0 else 0
        if win_pct >= 65.0:
            rec = "RAISE"
        elif win_pct >= 40.0:
            rec = "CALL"
        else:
            rec = "FOLD"

        result = EquityResult(
            win_pct=win_pct,
            tie_pct=tie_pct,
            lose_pct=lose_pct,
            samples=total,
            player_hand=list(player_hand),
            community=list(community),
            hand_rank_str=hand_rank_str,
            recommendation=rec,
            computation_time_ms=round(elapsed_ms, 1),
        )

        return result

    def compute_async(self, player_hand: List[str], community: List[str]):
        
        if self._computing:
            return
        self._computing = True

        def _run():
            try:
                result = self.compute_equity(player_hand, community)
                with self._lock:
                    self._current_result = result
            finally:
                self._computing = False

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def get_result(self) -> Optional[EquityResult]:
        
        with self._lock:
            return self._current_result

    @property
    def is_computing(self) -> bool:
        return self._computing
