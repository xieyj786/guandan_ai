"""Independent-round evaluation; no GUI or credentials in persisted configuration."""
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
import csv
import json
import math
import threading
import time

from agents.rule_agent import RuleAgent
from game_engine.card import Rank, Suit
from match_runner import Match

PATTERNS = ('straight_flush', 'bomb6', 'bomb7', 'bomb8', 'joker_bomb')


def natural_patterns(hand):
    """Count suit/rank windows once, exact maximal bombs; hearts retain face rank."""
    counts = Counter(c.rank for c in hand if c.suit != Suit.JOKER)
    result = {k: 0 for k in PATTERNS}
    for n in (6, 7, 8):
        result[f'bomb{n}'] = sum(v == n for v in counts.values())
    for suit in (Suit.SPADE, Suit.HEART, Suit.CLUB, Suit.DIAMOND):
        ranks = {int(c.rank) for c in hand if c.suit == suit}
        windows = [set(range(start, start+5)) for start in range(2, 11)] + [{14,2,3,4,5}]
        result['straight_flush'] += sum(w <= ranks for w in windows)
    jokers = Counter(c.rank for c in hand if c.suit == Suit.JOKER)
    result['joker_bomb'] = int(jokers[Rank.SMALL_JOKER] == 2 and jokers[Rank.BIG_JOKER] == 2)
    return result


@dataclass(frozen=True)
class BenchmarkConfig:
    rounds: int = 250
    seed: int = 42
    level: int = 2
    paired: bool = False
    wildcards: bool = True
    max_turns: int = 3000

    def __post_init__(self):
        if self.rounds < 1 or self.rounds > 100000 or self.level not in range(2,15):
            raise ValueError('局数须为1～100000，级牌须为2～14')
        if self.paired and self.rounds % 2:
            raise ValueError('换位配对模式需要偶数局数')
        if self.max_turns < 1:
            raise ValueError('回合上限须大于0')


def wilson(wins, n):
    if not n:
        return None
    z = 1.96
    p = wins/n
    center = (p+z*z/(2*n))/(1+z*z/n)
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0,center-half), min(1,center+half)]


class BenchmarkRun:
    def __init__(self, config, folder, factories=None, labels=('规则AI','规则AI'), on_update=None):
        self.config = config
        self.folder = Path(folder)
        self.factories = factories or (lambda name: RuleAgent(name), lambda name: RuleAgent(name))
        self.labels = labels
        self.on_update = on_update or (lambda data: None)
        self.cancel = threading.Event()
        self.play = threading.Event()
        self.play.set()
        self.rows = []
        self.fallback_reasons = Counter()

    def summary(self, status):
        good = [r for r in self.rows if r['status'] == 'completed']
        n = len(good)
        totals = {k: sum(r[k] for r in good) for k in PATTERNS}
        wins = sum(r['winner_strategy'] == 'A' for r in good)
        return dict(status=status, planned=self.config.rounds, completed=n,
                    failed=sum(r['status']=='failed' for r in self.rows),
                    cancelled=sum(r['status']=='cancelled' for r in self.rows),
                    fallback_reasons=dict(self.fallback_reasons), labels=self.labels, wins_A=wins, wins_B=n-wins,
                    win_rate_A=wins/n if n else None, win_rate_B=(n-wins)/n if n else None,
                    independent_wilson95_A=None if self.config.paired else wilson(wins,n),
                    patterns=totals, average_per_round={k:v/n if n else None for k,v in totals.items()},
                    fallback_rounds=sum(r['fallbacks']>0 for r in good),
                    fallback_decisions=sum(r['fallbacks'] for r in self.rows),
                    llm_decisions=sum(r['llm_decisions'] for r in self.rows),
                    elapsed_seconds=sum(r['seconds'] for r in self.rows))

    def run(self):
        self.folder.mkdir(parents=True, exist_ok=False)
        (self.folder/'config.json').write_text(json.dumps(dict(config=asdict(self.config),labels=self.labels,
            strategy_version=getattr(RuleAgent('version'),'strategy_version','unknown')),ensure_ascii=False,indent=2),encoding='utf-8')
        status = 'completed'
        with (self.folder/'rounds.csv').open('w',newline='',encoding='utf-8-sig') as f, (self.folder/'events.jsonl').open('w',encoding='utf-8') as events:
            writer = None
            for index in range(self.config.rounds):
                if self.cancel.is_set():
                    status='cancelled'; break
                swapped = self.config.paired and index % 2 == 1
                seed = self.config.seed + (index//2 if self.config.paired else index)
                agents = [self.factories[(seat%2)^int(swapped)](f'AI{seat+1}') for seat in range(4)]
                row = dict(round=index+1,seed=seed,swapped=int(swapped),status='completed',winner_seat='',winner_strategy='',
                           turns=0,llm_decisions=0,fallbacks=0,seconds=0,**{k:0 for k in PATTERNS})
                start = time.monotonic()
                def event(message):
                    events.write(json.dumps({'round':index+1,'event':message},ensure_ascii=False)+'\n')
                try:
                    match = Match(agents,seed=seed,level_rank=Rank(self.config.level),verbose=False,
                                  use_wildcards=self.config.wildcards,event_callback=event)
                    match.prepare()
                    for hand in match.hands:
                        for k,v in natural_patterns(hand).items(): row[k] += v
                    events.write(json.dumps({'round':index+1,'hands':[[[c.suit.value,int(c.rank)] for c in h] for h in match.hands]},ensure_ascii=False)+'\n')
                    while len(match.finish_order)<4:
                        while not self.play.wait(.1):
                            if self.cancel.is_set(): break
                        if self.cancel.is_set():
                            row['status']='cancelled'; status='cancelled'; break
                        if row['turns'] >= self.config.max_turns:
                            raise RuntimeError('turn limit')
                        actor = agents[match.current_player]
                        match._take_turn(); row['turns'] += 1
                        if hasattr(actor,'report'):
                            row['llm_decisions'] += 1
                            fallback = '规则接管' in actor.report
                            row['fallbacks'] += int(fallback)
                            if fallback:
                                reason=getattr(actor,'fallback_reason','')
                                if reason not in ('api_error','transport_error','truncated','empty_content','invalid_response','invalid_action_json'):
                                    reason='unknown'
                                self.fallback_reasons[reason] += 1
                                event('LLM fallback: '+reason)
                            else: event('LLM legal selection')
                    if row['status']=='completed':
                        seat = match._build_round_result().winning_team
                        row['winner_seat']=seat
                        row['winner_strategy']=('B' if seat=='A' else 'A') if swapped else seat
                except Exception as exc:
                    row['status']='failed'
                    event('Failure: '+type(exc).__name__)  # No provider response or secret.
                row['seconds']=round(time.monotonic()-start,3)
                self.rows.append(row)
                if writer is None:
                    writer=csv.DictWriter(f,fieldnames=list(row)); writer.writeheader()
                writer.writerow(row); f.flush(); events.flush()
                summary=self.summary(status if status=='cancelled' else 'running')
                (self.folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
                self.on_update(summary)
                if status=='cancelled': break
        final=self.summary(status)
        (self.folder/'summary.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
        self.on_update(final)
        return final
