"""LLM 只能选择规则引擎生成的合法动作编号。"""
from __future__ import annotations

import json
from typing import Protocol
from collections import Counter
from agents.base import Action, Agent, Observation
from agents.llm_client import LLMRequestError
from agents.rule_agent import RuleAgent
from game_engine.card import card_display
from game_engine.moves import generate_all_moves


class ChatClient(Protocol):
    def chat(self, prompt: str) -> str: ...


class DeepSeekAgent(Agent):
    def __init__(self, name: str, client: ChatClient):
        super().__init__(name)
        self.client = client
        self.fallback = RuleAgent(name)
        self.report = ""

    def candidates(self, obs: Observation) -> list[Action]:
        moves = generate_all_moves(obs.hand, obs.level_rank, use_wildcards=obs.use_wildcards,
                                   last_play=obs.last_play)
        actions = [Action('play', m.cards) for m in moves if obs.last_play is None or
                   RuleAgent._beats(m, obs.last_play, obs.level_rank)]
        if obs.last_play is not None:
            actions.append(Action('pass'))
        return actions

    def decide(self, observation: Observation) -> Action:
        actions = self.candidates(observation)
        recommended = self.fallback.decide(observation)
        suggestion = next((i for i, a in enumerate(actions) if a.action_type == recommended.action_type
                           and Counter(a.cards) == Counter(recommended.cards)), None)
        public = Counter(card_display(c) for c in observation.played_cards)
        state = {
            '玩家': self.name, '本局全桌级牌': observation.level_rank.name,
            '手牌': [card_display(c) for c in observation.hand],
            '队友剩余': observation.teammate_hand_size,
            '下家和上家对手剩余': observation.opponent_hand_sizes,
            '当前控牌者': '无人，必须领出' if observation.last_play is None else
                          '队友' if observation.last_play_by_teammate else '对手或自己',
            '当前牌': [card_display(c) for c in observation.last_play.cards] if observation.last_play else [],
            '公开已出牌及张数': dict(public),
            '近期记录': observation.play_history[-16:],
            '规则推荐编号': suggestion,
            '合法动作': [{'id': i, 'action': a.action_type,
                        'cards': [card_display(c) for c in a.cards]} for i, a in enumerate(actions)],
        }
        prompt = ('你是掼蛋玩家。只根据自己的手牌和公开信息决策，不猜看不到的手牌。'
                  '红心级牌为逢人配，两副牌。合法动作已由引擎验证，不自行添加动作。'
                  '优先一手走完；队友控牌默认让牌，但可直接走完或封堵报单的下家。'
                  '队友报单时，自己牌弱且超过三手才走完则送现成小散单；有控制牌时按自身计划。'
                  '对手报单避免喂小单。规则推荐供参考。'
                  '只输出 JSON：{"action_id": 整数编号, "reason": "一句简短策略说明"}。\n'
                  + json.dumps(state, ensure_ascii=False))
        try:
            data = json.loads(self.client.chat(prompt))
            if not isinstance(data, dict) or type(data.get('action_id')) is not int:
                raise ValueError('无效编号')
            index = data['action_id']
            if not 0 <= index < len(actions):
                raise ValueError('编号超出范围')
            reason = data.get('reason', '')
            # 绝不将凭据或完整响应写入日志。
            if not isinstance(reason, str):
                reason = ''
            import re
            reason = re.sub(r'sk-[\w-]+', '[密钥已隐藏]', reason)
            reason = ' '.join(reason.split())[:120]
            self.report = f'{self.name}〔DeepSeek〕：{reason or "已选择合法动作"}'
            return actions[index]
        except LLMRequestError as exc:
            # 客户端错误均为经过脱敏的固定说明。
            self.report = f'{self.name}〔规则接管〕：{exc}'
        except (ValueError, TypeError, KeyError):
            self.report = f'{self.name}〔规则接管〕：模型回答不是有效动作编号'
        return recommended
