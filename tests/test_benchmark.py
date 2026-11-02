from pathlib import Path
from tempfile import TemporaryDirectory
from game_engine.card import Card, Rank, Suit
from benchmark import BenchmarkConfig, BenchmarkRun, natural_patterns, wilson
from agents.deepseek_agent import DeepSeekAgent
from agents.llm_client import LLMRequestError


def test_natural_pattern_boundaries():
    hand=[Card(s,Rank.SIX) for s in (Suit.SPADE,Suit.CLUB,Suit.HEART,Suit.DIAMOND) for _ in range(2)]
    result=natural_patterns(hand)
    assert result['bomb8']==1 and result['bomb6']==result['bomb7']==0
    hand=[Card(Suit.HEART,Rank(r)) for r in (2,3,4,5,6,7)]
    assert natural_patterns(hand)['straight_flush']==2
    assert natural_patterns(hand+hand)['straight_flush']==2
    assert natural_patterns([Card(Suit.JOKER,r) for r in (Rank.SMALL_JOKER,Rank.BIG_JOKER) for _ in range(2)])['joker_bomb']==1


def test_benchmark_paired_and_logs():
    with TemporaryDirectory() as tmp:
        from agents.rule_agent import RuleAgent
        assigned=[]
        def factory(strategy):
            def make(name):
                assigned.append((name,strategy))
                return RuleAgent(name)
            return make
        run=BenchmarkRun(BenchmarkConfig(repetitions=1),Path(tmp)/'run',
                         factories=(factory('A'),factory('B')))
        result=run.run()
        assert result['completed']==26 and result['wins_A']==result['wins_B']==13
        assert result['independent_wilson95_A'] is None
        assert run.rows[0]['seed']==run.rows[13]['seed']
        assert run.rows[0]['winner_seat']==run.rows[13]['winner_seat']
        assert result['pairs']==dict(planned=13,completed=13,incomplete=0,missing=0,
                                     A_two_wins=0,split=13,B_two_wins=0)
        assert result['completed_repetitions']==1
        assert assigned[:4]==[('AI1','A'),('AI2','B'),('AI3','A'),('AI4','B')]
        assert assigned[52:56]==[('AI1','B'),('AI2','A'),('AI3','B'),('AI4','A')]
        assert all(part['combined']['completed']==2 and part['combined']['wins_A']==1
                   for part in result['by_level'].values())
        import json
        events=[json.loads(line) for line in (run.folder/'events.jsonl').read_text().splitlines()]
        deals=[e for e in events if 'hands' in e]
        assert [r['level'] for r in run.rows]==list(range(2,15))*2
        for before,after in zip(deals[:13],deals[13:]):
            assert before['hands']==after['hands']
            assert before['first_player']==after['first_player']
            assert before['pair_id']==after['pair_id']
            assert before['level']==after['level']
        assert len({json.dumps(d['hands']) for d in deals[:13]})==13
        assert (run.folder/'rounds.csv').exists()


def test_cancel_failure_zero_and_validation():
    with TemporaryDirectory() as tmp:
        run=BenchmarkRun(BenchmarkConfig(repetitions=1),Path(tmp)/'cancel');run.cancel.set()
        assert run.run()['win_rate_A'] is None
        result=BenchmarkRun(BenchmarkConfig(repetitions=1,max_turns=1),Path(tmp)/'fail').run()
        assert result['completed']==0 and result['failed']==26
    try: BenchmarkConfig(repetitions=0)
    except ValueError: pass
    else: assert False
    assert wilson(0,0) is None and wilson(1,1)[0]<1


def test_mock_llm_fallback_is_visible_and_secret_not_logged():
    class Client:
        def chat(self,prompt):raise LLMRequestError('sk-secret-test')
    with TemporaryDirectory() as tmp:
        run=BenchmarkRun(BenchmarkConfig(repetitions=1,max_turns=3),Path(tmp)/'mock',
            factories=(lambda n:DeepSeekAgent(n,Client()),lambda n:DeepSeekAgent(n,Client())))
        result=run.run()
        assert result['fallback_decisions']==78
        assert 'sk-secret-test' not in (run.folder/'events.jsonl').read_text(encoding='utf-8')


def test_compatible_deepseek_payload_and_diagnostics():
    import benchmark_gui as gui
    original=gui._post_json
    seen=[]
    try:
        def fake(url,headers,payload,timeout):
            seen.append(payload)
            return {'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]}
        gui._post_json=fake
        client=gui.CompatibleClient('https://api.deepseek.com','deepseek-flash','sk-test-only')
        assert client.chat('json')=='{"ok":true}'
        assert seen[-1]['thinking']=={'type':'disabled'}
        assert seen[-1]['response_format']=={'type':'json_object'}
        other=gui.CompatibleClient('https://example.com/v1','test','sk-test-only')
        other.chat('json');assert 'thinking' not in seen[-1]
        for finish,content,expected in [('length','{}','truncated'),('stop','','empty_content')]:
            gui._post_json=lambda *a,**k:{'choices':[{'finish_reason':finish,'message':{'content':content}}]}
            try:client.chat('json')
            except LLMRequestError:pass
            else:assert False
            assert client.last_error_kind==expected
        def fail(*a,**k):raise LLMRequestError('429 限流')
        gui._post_json=fail
        try:client.chat('json')
        except LLMRequestError as exc:assert str(exc)=='429 限流'
        else:assert False
    finally:gui._post_json=original


def test_schedule_and_partial_pair_denominators():
    for repeats in (50,100,500):
        config=BenchmarkConfig(repetitions=repeats)
        schedule=list(config.schedule())
        assert len(schedule)==repeats*26
        assert len({item[4] for item in schedule})==repeats*13
        assert schedule[26][4]==schedule[0][4]+13
    with TemporaryDirectory() as tmp:
        run=BenchmarkRun(BenchmarkConfig(repetitions=1),Path(tmp)/'partial')
        def row(pair, swapped, winner, status='completed'):
            return dict(pair_id=pair,swapped=swapped,winner_strategy=winner,status=status,
                        repetition=1,level=pair+1,fallbacks=0,llm_decisions=0,seconds=0,
                        **{k:0 for k in ('straight_flush','bomb6','bomb7','bomb8','joker_bomb')})
        run.rows=[row(1,0,'A'),row(1,1,'A'),row(2,0,'B'),row(2,1,'','failed')]
        summary=run.summary('cancelled')
        assert summary['completed']==3 and summary['wins_A']==2
        assert summary['before_swap']['win_rate_A']==.5
        assert summary['after_swap']['win_rate_A']==1
        assert summary['pairs']['completed']==1 and summary['pairs']['A_two_wins']==1
        assert summary['pairs']['incomplete']==1 and summary['pairs']['missing']==12
        assert summary['completed_repetitions']==0


def test_benchmark_local_client_selection_and_request():
    import benchmark_gui as gui
    from agents.lmstudio_client import LMStudioClient
    from unittest.mock import patch
    with patch.object(gui,'CompatibleClient',side_effect=AssertionError('cloud client')):
        client=gui.team_client('LM Studio','http://127.0.0.1:1234/v1',
                               'qwen/qwen3.5-9b','must-not-send','240')
        assert isinstance(client,LMStudioClient) and client.timeout==240
        with patch('agents.lmstudio_client._post_json',return_value={
                'choices':[{'message':{'content':'{"ok":true}'}}]}) as post:
            client.test_connection()
            assert post.call_args.args[1]=={'Content-Type':'application/json'}
            assert 'must-not-send' not in str(post.call_args)
    with patch.object(gui,'CompatibleClient',return_value='cloud') as cloud:
        assert gui.team_client('LLM','https://example.com','model','key','unused')=='cloud'
        cloud.assert_called_once_with('https://example.com','model','key')
    for timeout in ('bad','0','601'):
        try: gui.team_client('LM Studio','http://127.0.0.1:1234/v1','model','',timeout)
        except ValueError: pass
        else: assert False


def test_local_stable_and_experimental_protocols_are_explicit():
    from benchmark_gui import team_client
    args=('http://127.0.0.1:1234/v1','qwen/qwen3.5-9b','','180')
    assert team_client('LM Studio',*args).speed_mode is False
    assert team_client('LM Studio（实验）',*args).speed_mode is True
