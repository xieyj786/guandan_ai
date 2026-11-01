import json
from unittest.mock import patch
from agents.local_prompt import fast_prompt,encode_cards,decode_cards,encode_history,decode_history,FAST_SYSTEM
from agents.lmstudio_client import LMStudioClient
from agents.deepseek_agent import DeepSeekAgent
from agents.base import Observation
from game_engine.card import Card,Rank,Suit


def test_packed_cards_and_history_roundtrip():
    cards='♠3 ♠3 ♥2 ♣10 ♦J 小王 大王'
    assert decode_cards(encode_cards(cards))==cards
    records=['AI1 出牌：♠3, ♠3 〔PAIR〕，剩余 25 张','AI2 过牌',
             'AI3 已出完，排名第 1','AI4 接风，重新领出。','未知公开信息原样保留']
    assert [decode_history(encode_history(item)) for item in records]==records


def test_packed_state_preserves_all_information_and_ids():
    state={'玩家':'AI3','本局全桌级牌':'TWO','手牌':['♠3','♠3','小王'],
           '队友剩余':5,'下家和上家对手剩余':[3,4],'当前控牌者':'队友',
           '当前牌':['♥4'],'公开已出牌及张数':{'♠3':2,'大王':1},
           '近期记录':['AI1 出牌：♥4 〔SINGLE〕，剩余 26 张','AI2 过牌'],
           '规则推荐编号':1,'合法动作':[{'id':0,'action':'play','cards':['小王']},
                                  {'id':1,'action':'pass','cards':[]}]}
    prompt=fast_prompt(state,2,True)
    system,body=prompt.split('\n',1);assert system==FAST_SYSTEM
    data=json.loads(body)
    assert decode_cards(data['手牌']).split()==state['手牌']
    assert decode_cards(data['当前牌']).split()==state['当前牌']
    assert {decode_cards(pair.split('=')[0]):int(pair.split('=')[1]) for pair in data['已出'].split()}==state['公开已出牌及张数']
    assert [decode_history(h) for h in data['近况']]==state['近期记录']
    assert data['推荐']==1 and data['敌下家上家剩余']==[3,4] and data['级牌']==2 and data['红心配'] is True
    assert [decode_cards(m).split() for m in data['动作'].values()]==[a['cards'] for a in state['合法动作']]


def test_speed_mode_fixed_system_and_action_only_schema():
    client=LMStudioClient(speed_mode=True)
    with patch('agents.lmstudio_client._post_json',return_value={
            'choices':[{'finish_reason':'stop','message':{'content':'','reasoning_content':'{"action_id":0}'}}]}) as post:
        agent=DeepSeekAgent('AI1',client)
        obs=Observation([Card(Suit.SPADE,Rank.THREE),Card(Suit.HEART,Rank.NINE)],Rank.TWO,None,7,(4,6))
        assert agent.decide(obs).cards==[obs.hand[0]]
        payload=post.call_args.args[2]
        assert payload['messages'][0]=={'role':'system','content':FAST_SYSTEM}
        assert payload['messages'][1]['role']=='user'
        assert payload['response_format']['json_schema']['schema']['required']==['action_id']
        assert payload['response_format']['json_schema']['schema']['properties']['action_id']['enum']==[0,1]
        assert agent.last_decision_kind=='llm' and '规则接管' not in agent.report


def test_stable_protocol_also_bounds_only_actual_action_ids():
    client=LMStudioClient()
    prompt='instructions\n'+json.dumps({'合法动作':{'0':'♠3','1':''}})
    with patch('agents.lmstudio_client._post_json',return_value={
            'choices':[{'message':{'content':'{"action_id":1,"reason":"pass"}'}}]}) as post:
        client.chat(prompt)
        schema=post.call_args.args[2]['response_format']['json_schema']['schema']
        assert schema['properties']['action_id']['enum']==[0,1]
        assert schema['required']==['action_id','reason']
