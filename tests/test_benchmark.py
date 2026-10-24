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
        run=BenchmarkRun(BenchmarkConfig(rounds=2,paired=True),Path(tmp)/'run')
        result=run.run()
        assert result['completed']==2 and result['wins_A']==result['wins_B']==1
        assert result['independent_wilson95_A'] is None
        assert run.rows[0]['seed']==run.rows[1]['seed']
        assert run.rows[0]['winner_seat']==run.rows[1]['winner_seat']
        assert (run.folder/'rounds.csv').exists()


def test_cancel_failure_zero_and_validation():
    with TemporaryDirectory() as tmp:
        run=BenchmarkRun(BenchmarkConfig(rounds=2),Path(tmp)/'cancel');run.cancel.set()
        assert run.run()['win_rate_A'] is None
        result=BenchmarkRun(BenchmarkConfig(rounds=1,max_turns=1),Path(tmp)/'fail').run()
        assert result['completed']==0 and result['failed']==1
    try: BenchmarkConfig(rounds=3,paired=True)
    except ValueError: pass
    else: assert False
    assert wilson(0,0) is None and wilson(1,1)[0]<1


def test_mock_llm_fallback_is_visible_and_secret_not_logged():
    class Client:
        def chat(self,prompt):raise LLMRequestError('sk-secret-test')
    with TemporaryDirectory() as tmp:
        run=BenchmarkRun(BenchmarkConfig(rounds=1,max_turns=3),Path(tmp)/'mock',
            factories=(lambda n:DeepSeekAgent(n,Client()),lambda n:DeepSeekAgent(n,Client())))
        result=run.run()
        assert result['fallback_decisions']==3
        assert 'sk-secret-test' not in (run.folder/'events.jsonl').read_text()


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
