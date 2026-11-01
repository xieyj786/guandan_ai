"""Skip forced moves and preserve all information in compact local prompts."""
import json
from collections import Counter
from unittest.mock import patch
from agents.base import Observation
from agents.deepseek_agent import DeepSeekAgent
from game_engine.card import Card,Rank,Suit,card_display
from game_engine.identify import identify_card_type


class Capture:
    def __init__(self, provider=''):
        self.provider_name=provider;self.prompts=[]
    def chat(self,prompt):
        self.prompts.append(prompt)
        return '{"action_id":0,"reason":"test"}'


def test_unique_lead_and_pass_skip_client_and_rule_recommendation():
    client=Capture('LM Studio');agent=DeepSeekAgent('AI1',client)
    hand=[Card(Suit.SPADE,Rank.THREE)]
    obs=Observation(hand,Rank.TWO,None,7,(4,6))
    with patch.object(agent.fallback,'decide',side_effect=AssertionError('unneeded planning')):
        assert agent.decide(obs).cards==hand
        obs.last_play=identify_card_type([Card(Suit.HEART,Rank.FOUR)],Rank.TWO)
        assert agent.decide(obs).action_type=='pass'
    assert client.prompts==[] and agent.last_decision_kind=='automatic'
    assert agent.fallback_reason=='' and '规则接管' not in agent.report
    assert '唯一合法动作' in agent.report
    obs.hand.append(Card(Suit.CLUB,Rank.SIX));obs.last_play=None
    agent.decide(obs)
    assert len(client.prompts)==1 and agent.last_decision_kind=='llm'


def test_local_compact_prompt_preserves_cards_public_state_and_action_ids():
    hand=[Card(s,Rank(rank)) for s,rank in [(Suit.SPADE,3),(Suit.SPADE,3),(Suit.HEART,9),
          (Suit.CLUB,4),(Suit.DIAMOND,4),(Suit.CLUB,6),(Suit.HEART,2)]]
    obs=Observation(hand,Rank.TWO,None,7,(4,6),played_cards=hand[:3],
                    play_history=[f'AI1 出牌：♠{i}' for i in range(20)])
    old=Capture();local=Capture('LM Studio')
    old_agent=DeepSeekAgent('AI1',old);new_agent=DeepSeekAgent('AI1',local)
    old_action=old_agent.decide(obs);new_action=new_agent.decide(obs)
    assert old_action==new_action
    before=json.loads(old.prompts[0].split('\n',1)[1])
    after=json.loads(local.prompts[0].split('\n',1)[1])
    assert len(local.prompts[0])<len(old.prompts[0])
    assert Counter(after['手牌'].split())==Counter(before['手牌'])
    assert after['当前牌'].split()==before['当前牌']
    assert after['合法动作']=={str(a['id']):' '.join(a['cards']) for a in before['合法动作']}
    assert len(after['合法动作'])==len(new_agent.candidates(obs))
    for key in before.keys()-{'手牌','当前牌','合法动作'}:
        assert after[key]==before[key],key
    assert after['近期记录']==obs.play_history[-16:]
