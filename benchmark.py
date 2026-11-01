"""Independent-round evaluation; no GUI or credentials in persisted configuration."""
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
import csv
import json
import math
import threading
import time
from datetime import datetime, timezone, timedelta
from benchmark_report import write_report

from agents.request_metrics import (TOKEN_FIELDS, empty_totals, add_request, combine_totals, describe_totals)
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
    repetitions: int = 50
    seed: int = 42
    wildcards: bool = True
    max_turns: int = 3000

    def __post_init__(self):
        if type(self.repetitions) is not int or not 1 <= self.repetitions <= 500:
            raise ValueError('重复轮数须为1～500；常用50、100、500')
        if type(self.seed) is not int:
            raise ValueError('种子须为整数')
        if self.max_turns < 1:
            raise ValueError('回合上限须大于0')

    @property
    def rounds(self):
        return self.repetitions * 26

    def schedule(self):
        """One fresh 13-deal block, then replay the block with strategies swapped."""
        for repetition in range(1, self.repetitions + 1):
            for swapped in (False, True):
                for level in range(2, 15):
                    pair_id = (repetition - 1) * 13 + level - 1
                    yield repetition, level, swapped, pair_id, self.seed + pair_id - 1


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
        self.llm_decisions = 0
        self.usage_by_strategy = {team: empty_totals() for team in ('A','B')}
        self.started_at = self.ended_at = None
        self.started_time = self.ended_time = None
        self.wall_started_at = self.wall_ended_at = None
        self.automatic_by_strategy = Counter()
        self.report_path = None
        self.paused_seconds = 0.0
        self.pause_started = None
        self.current_round = None
        self.current_strategy = None
        self.request_started = None

    def timing(self):
        pause_started = self.pause_started
        now = self.ended_at if self.ended_at is not None else time.monotonic()
        elapsed = max(0.0, now-self.started_at) if self.started_at is not None else 0.0
        paused = self.paused_seconds + (now-pause_started if pause_started is not None else 0.0)
        return elapsed, paused


    def summary(self, status):
        rows = list(self.rows)
        good = [r for r in rows if r['status'] == 'completed']
        elapsed, paused = self.timing()
        request_started = self.request_started
        current_strategy = self.current_strategy if request_started is not None else None
        wall_now = self.wall_ended_at if self.wall_ended_at is not None else time.time()
        wall_elapsed = max(0.0, wall_now-self.wall_started_at) if self.wall_started_at is not None else elapsed
        n = len(good)
        totals = {k: sum(r[k] for r in good) for k in PATTERNS}
        def rates(rows):
            count = len(rows)
            wins = sum(r['winner_strategy'] == 'A' for r in rows)
            return dict(completed=count, wins_A=wins, wins_B=count-wins,
                        win_rate_A=wins/count if count else None,
                        win_rate_B=(count-wins)/count if count else None)
        pairs = {}
        for row in good:
            pairs.setdefault(row['pair_id'], []).append(row)
        complete = [rows for rows in pairs.values() if len(rows) == 2]
        outcomes = Counter(sum(r['winner_strategy'] == 'A' for r in rows) for rows in complete)
        repetition_counts = Counter(r['repetition'] for r in good)
        before = rates([r for r in good if not r['swapped']])
        after = rates([r for r in good if r['swapped']])
        return dict(started_time=self.started_time, ended_time=self.ended_time,
                    report_path=str(self.report_path) if self.report_path else None,
                    status=status, planned=self.config.rounds, **rates(good),
                    repetitions=self.config.repetitions,
                    completed_repetitions=sum(count == 26 for count in repetition_counts.values()),
                    failed=sum(r['status']=='failed' for r in self.rows),
                    cancelled=sum(r['status']=='cancelled' for r in self.rows),
                    before_swap=before, after_swap=after,
                    swap_rate_difference_A=(after['win_rate_A']-before['win_rate_A']
                        if before['completed'] and after['completed'] else None),
                    by_level={str(level):dict(
                        combined=rates([r for r in good if r['level']==level]),
                        before_swap=rates([r for r in good if r['level']==level and not r['swapped']]),
                        after_swap=rates([r for r in good if r['level']==level and r['swapped']]))
                        for level in range(2,15)},
                    pairs=dict(planned=self.config.repetitions*13, completed=len(complete),
                        incomplete=len(pairs)-len(complete),
                        missing=self.config.repetitions*13-len(complete),
                        A_two_wins=outcomes[2], split=outcomes[1], B_two_wins=outcomes[0]),
                    fallback_reasons=dict(self.fallback_reasons), labels=self.labels,
                    independent_wilson95_A=None,
                    patterns=totals, average_per_round={k:v/n if n else None for k,v in totals.items()},
                    fallback_rounds=sum(r['fallbacks']>0 for r in good),
                    fallback_decisions=sum(self.fallback_reasons.values()),
                    llm_decisions=self.llm_decisions,
                    elapsed_seconds=elapsed, paused_seconds=paused,
                    wall_elapsed_seconds=wall_elapsed,
                    wall_clock_difference_seconds=wall_elapsed-elapsed,
                    automatic_actions=sum(self.automatic_by_strategy.values()),
                    automatic_actions_by_strategy={team:self.automatic_by_strategy[team] for team in ('A','B')},
                    active_seconds=max(0.0,elapsed-paused),
                    average_round_seconds=(elapsed-paused)/n if n else None,
                    estimated_remaining_seconds=((elapsed-paused)/n * (self.config.rounds-len(rows)) if n else None),
                    current_round=self.current_round, current_strategy=current_strategy,
                    current_request_seconds=(max(0.0,time.monotonic()-request_started)
                                             if request_started is not None else None),
                    usage=describe_totals(combine_totals(self.usage_by_strategy.values())),
                    usage_by_strategy={team:describe_totals(value) for team,value in self.usage_by_strategy.items()})

    def run(self):
        self.started_at = time.monotonic()
        self.wall_started_at = time.time()
        self.started_time = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
        self.folder.mkdir(parents=True, exist_ok=False)
        (self.folder/'config.json').write_text(json.dumps(dict(config=asdict(self.config), protocol="level_sweep_paired_v2",
            llm_policy="unique_action_skip_v1; local_bounded_action_ids_v1",
            local_protocols={"LM Studio":"lmstudio_compact_prompt_v1",
                "LM Studio（实验）":"lmstudio_packed_prompt_v3; action_only_v1; bounded_action_ids_v1; stable_system_prefix_v1"},
            planned_rounds=self.config.rounds, labels=self.labels,
            strategy_version=getattr(RuleAgent('version'),'strategy_version','unknown')),ensure_ascii=False,indent=2),encoding='utf-8')
        status = 'completed'
        with (self.folder/'rounds.csv').open('w',newline='',encoding='utf-8-sig') as f, (self.folder/'events.jsonl').open('w',encoding='utf-8') as events:
            writer = None
            for index, (repetition, level, swapped, pair_id, seed) in enumerate(self.config.schedule()):
                if self.cancel.is_set():
                    status='cancelled'; break
                agents = [self.factories[(seat%2)^int(swapped)](f'AI{seat+1}') for seat in range(4)]
                row = dict(round=index+1,repetition=repetition,level=level,pair_id=pair_id,seed=seed,first_player='',swapped=int(swapped),status='completed',winner_seat='',winner_strategy='',
                           turns=0,llm_decisions=0,automatic_actions=0,A_automatic_actions=0,B_automatic_actions=0,fallbacks=0,seconds=0,**{k:0 for k in PATTERNS})
                self.current_round = index+1
                round_usage = {team:empty_totals() for team in ('A','B')}
                for team in ('A','B'):
                    for key,value in describe_totals(empty_totals()).items():row[f'{team}_{key}'] = value
                start = time.monotonic()
                def event(message):
                    events.write(json.dumps({'round':index+1,'event':message},ensure_ascii=False)+'\n')
                try:
                    match = Match(agents,seed=seed,level_rank=Rank(level),verbose=False,
                                  use_wildcards=self.config.wildcards,event_callback=event)
                    match.prepare()
                    row['first_player'] = match.current_player + 1
                    for hand in match.hands:
                        for k,v in natural_patterns(hand).items(): row[k] += v
                    events.write(json.dumps({'round':index+1,'repetition':repetition,'level':level,'pair_id':pair_id,
                                             'swapped':int(swapped),'first_player':row['first_player'],'hands':[[[c.suit.value,int(c.rank)] for c in h] for h in match.hands]},ensure_ascii=False)+'\n')
                    while len(match.finish_order)<4:
                        if not self.play.is_set():
                            self.pause_started = time.monotonic()
                            while not self.play.wait(.1):
                                if self.cancel.is_set(): break
                            self.paused_seconds += time.monotonic()-self.pause_started
                            self.pause_started = None
                        if self.cancel.is_set():
                            row['status']='cancelled'; status='cancelled'; break
                        if row['turns'] >= self.config.max_turns:
                            raise RuntimeError('turn limit')
                        actor = agents[match.current_player]
                        strategy = 'A' if ((match.current_player % 2) ^ int(swapped)) == 0 else 'B'
                        client = getattr(actor,'client',None)
                        if client is not None:
                            # Clear stale telemetry even if this action makes no request.
                            client.last_request_metrics = None
                            self.current_strategy = strategy
                            self.request_started = time.monotonic()
                        try:
                            match._take_turn(); row['turns'] += 1
                        finally:
                            metrics = getattr(client,'last_request_metrics',None)
                            if metrics is not None:
                                add_request(round_usage[strategy], metrics)
                                add_request(self.usage_by_strategy[strategy], metrics)
                                events.write(json.dumps(dict(round=index+1, strategy=strategy,
                                    request_metrics=metrics),ensure_ascii=False)+'\n')
                            self.current_strategy = self.request_started = None
                        if getattr(actor,'last_decision_kind','') == 'automatic':
                            row['automatic_actions'] += 1
                            row[f'{strategy}_automatic_actions'] += 1
                            self.automatic_by_strategy[strategy] += 1
                            event('Automatic unique legal action: '+strategy)
                        elif hasattr(actor,'report'):
                            row['llm_decisions'] += 1
                            self.llm_decisions += 1
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
                for team in ('A','B'):
                    for key,value in describe_totals(round_usage[team]).items():row[f'{team}_{key}'] = value
                row['seconds']=round(time.monotonic()-start,3)
                self.rows.append(row)
                if writer is None:
                    writer=csv.DictWriter(f,fieldnames=list(row)); writer.writeheader()
                writer.writerow(row); f.flush(); events.flush()
                summary=self.summary(status if status=='cancelled' else 'running')
                (self.folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
                self.on_update(summary)
                if status=='cancelled': break
        self.current_round = None
        self.ended_at = time.monotonic()
        self.wall_ended_at = time.time()
        self.ended_time = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
        final=self.summary(status)
        self.report_path = write_report(self, final)
        final["report_path"] = str(self.report_path)
        (self.folder/'summary.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
        self.on_update(final)
        return final
