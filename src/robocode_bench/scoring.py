from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence


@dataclass
class RoundScore:
    round_number: int
    total_score: float
    bullet_damage: float
    bullet_damage_bonus: float
    ram_damage: float
    ram_damage_bonus: float
    survival_score: float
    last_survivor_bonus: float
    rank: int
    crashed_or_disqualified: bool = False


@dataclass
class MatchMetrics:
    rounds: List[RoundScore]
    avg_total_score: float = field(init=False)
    avg_rank: float = field(init=False)
    winrate_round: float = field(init=False)
    avg_survival_score: float = field(init=False)
    avg_bullet_damage: float = field(init=False)
    avg_ram_damage: float = field(init=False)

    def __post_init__(self) -> None:
        if not self.rounds:
            raise ValueError("MatchMetrics requires at least one round")
        n = len(self.rounds)
        self.avg_total_score = sum(r.total_score for r in self.rounds) / n
        self.avg_rank = sum(r.rank for r in self.rounds) / n
        self.winrate_round = sum(1 for r in self.rounds if r.rank == 1) / n
        self.avg_survival_score = sum(r.survival_score for r in self.rounds) / n
        self.avg_bullet_damage = sum(r.bullet_damage for r in self.rounds) / n
        self.avg_ram_damage = sum(r.ram_damage for r in self.rounds) / n


@dataclass
class BotAggregate:
    match_metrics: Dict[str, MatchMetrics]

    def crash_rate(self) -> float:
        rounds = [r for m in self.match_metrics.values() for r in m.rounds]
        total = len(rounds)
        crashed = sum(1 for r in rounds if r.crashed_or_disqualified)
        return crashed / total if total else 0.0

    def variance_of(self, attr: str) -> float:
        values: List[float] = []
        for metrics in self.match_metrics.values():
            values.extend(getattr(r, attr) for r in metrics.rounds)
        if len(values) <= 1:
            return 0.0
        return statistics.pvariance(values)


@dataclass
class ScoreWeights:
    w_bps: float = 0.5
    w_fps: float = 0.3
    w_srs: float = 0.2
    alpha_winrate: float = 0.7


@dataclass
class FinalScore:
    bps: float
    fps: float
    srs: float
    bot_score: float


def score_1v1(match: MatchMetrics, normalized_avg_total_score: float, alpha: float) -> float:
    return alpha * match.winrate_round + (1 - alpha) * normalized_avg_total_score


def rank_score(rank: int, participants: int) -> float:
    if participants <= 1:
        return 1.0
    return (participants - rank) / (participants - 1)


def compute_bps(per_baseline: Dict[str, MatchMetrics], normalization: Dict[str, float], alpha: float) -> float:
    if not per_baseline:
        return 0.0
    scores: List[float] = []
    for baseline, metrics in per_baseline.items():
        norm = normalization.get(baseline, 0.0)
        scores.append(score_1v1(metrics, norm, alpha))
    return sum(scores) / len(scores)


def compute_fps(ffa_rounds: Iterable[RoundScore], participants: int) -> float:
    rounds = list(ffa_rounds)
    if not rounds:
        return 0.0
    return sum(rank_score(r.rank, participants) for r in rounds) / len(rounds)


def compute_srs(bot: BotAggregate, variance_normalizer: float = 1.0) -> float:
    crash_component = 1 - bot.crash_rate()
    variance = bot.variance_of("total_score")
    normalized_variance = min(variance / variance_normalizer, 1.0) if variance_normalizer > 0 else 0.0
    stability_component = 1 - normalized_variance
    return 0.5 * crash_component + 0.5 * stability_component


def compute_final_score(
    bps: float,
    fps: float,
    srs: float,
    weights: ScoreWeights | None = None,
) -> FinalScore:
    weights = weights or ScoreWeights()
    bot_score = (
        weights.w_bps * bps
        + weights.w_fps * fps
        + weights.w_srs * srs
    )
    return FinalScore(bps=bps, fps=fps, srs=srs, bot_score=bot_score)


def normalize_scores(values: Sequence[float], clamp: bool = True) -> List[float]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if math.isclose(low, high):
        return [0.0 for _ in values]
    normed = [(v - low) / (high - low) for v in values]
    if clamp:
        normed = [min(max(v, 0.0), 1.0) for v in normed]
    return normed

