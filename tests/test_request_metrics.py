"""Usage is provider-reported, counted per actual request, including fallbacks."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from agents.request_metrics import measured_post, empty_totals, add_request, describe_totals
from agents.lmstudio_client import LMStudioClient
from agents.deepseek_agent import DeepSeekAgent
from agents.llm_client import LLMRequestError
from benchmark import BenchmarkConfig, BenchmarkRun


def test_request_usage_missing_partial_and_failure_reset():
    client=LMStudioClient()
    response={'choices':[{'message':{'content':'{"action_id":0,"reason":"test"}'}}],
              'usage':{'prompt_tokens':10,'completion_tokens':4,'total_tokens':14,
                       'completion_tokens_details':{'reasoning_tokens':2},
                       'prompt_tokens_details':{'cached_tokens':3}}}
    totals=empty_totals()
    with patch('agents.lmstudio_client._post_json',return_value=response):
        client.chat('test');add_request(totals,client.last_request_metrics)
    assert totals['total_tokens']==14 and totals['reasoning_tokens']==2
    with patch('agents.lmstudio_client._post_json',side_effect=LLMRequestError('timeout')):
        try:client.chat('test')
        except LLMRequestError:pass
        else:assert False
        assert client.last_request_metrics['total_tokens'] is None
        add_request(totals,client.last_request_metrics)
    result=describe_totals(totals)
    assert result['requests']==2 and result['responses']==1
    assert result['total_tokens']==14 and result['total_tokens_reported_requests']==1
    assert result['request_seconds']>=0
    with patch('agents.lmstudio_client._post_json',return_value={
            'usage':{'prompt_tokens':True,'completion_tokens':-1,'total_tokens':'14'}}):
        try:client.chat('test')
        except LLMRequestError:pass
        assert all(client.last_request_metrics[k] is None for k in ('prompt_tokens','completion_tokens','total_tokens'))


def test_benchmark_usage_strategy_swap_failed_rounds_and_logs():
    with TemporaryDirectory() as tmp:
        def factory(name):return DeepSeekAgent(name,LMStudioClient())
        run=BenchmarkRun(BenchmarkConfig(repetitions=1,max_turns=1),Path(tmp)/'run',
                         factories=(factory,factory))
        response={'choices':[{'message':{'content':'{"action_id":0,"reason":"test"}'}}],
                  'usage':{'prompt_tokens':10,'completion_tokens':4,'total_tokens':14}}
        with patch('agents.lmstudio_client._post_json',return_value=response) as post:
            result=run.run()
        assert result['completed']==0 and result['failed']==26
        assert result['usage']['requests']==post.call_count==26
        assert result['usage']['total_tokens']==364
        assert result['usage']['reasoning_tokens'] is None
        for team in ('A','B'):
            assert result['usage_by_strategy'][team]['requests']==13
            assert result['usage_by_strategy'][team]['total_tokens']==182
            assert sum(r[f'{team}_total_tokens'] or 0 for r in run.rows)==182
        events=[json.loads(s) for s in (run.folder/'events.jsonl').read_text().splitlines()]
        assert len([e for e in events if 'request_metrics' in e])==26
        assert result['elapsed_seconds']>=result['usage']['request_seconds']
        frozen=result['elapsed_seconds']
        assert run.summary('completed')['elapsed_seconds']==frozen
        from benchmark_gui import format_summary
        text=format_summary(result)
        assert 'Token' in text and '未提供' in text and '钟表总时长' in text


def test_benchmark_timing_inflight_pause_and_frozen_end():
    with TemporaryDirectory() as tmp:
        run=BenchmarkRun(BenchmarkConfig(repetitions=1),Path(tmp)/'run')
        run.started_at=10;run.paused_seconds=2;run.pause_started=18
        run.request_started=19;run.current_strategy='A';run.current_round=1
        with patch('benchmark.time.monotonic',return_value=20):
            result=run.summary('running')
        assert result['elapsed_seconds']==10 and result['paused_seconds']==4
        assert result['active_seconds']==6 and result['current_request_seconds']==1
        assert result['estimated_remaining_seconds'] is None
        run.pause_started=None;run.ended_at=25;run.request_started=None
        assert run.summary('completed')['elapsed_seconds']==15


def test_cloud_usage_recorded_before_invalid_content():
    import benchmark_gui as gui
    client=gui.CompatibleClient('https://example.com','model','sk-test')
    with patch.object(gui,'_post_json',return_value={'choices':[],
            'usage':{'prompt_tokens':9,'completion_tokens':0,'total_tokens':9}}):
        try:client.chat('test')
        except LLMRequestError:pass
        else:assert False
    assert client.last_request_metrics['total_tokens']==9
    assert client.last_request_metrics['response_received']


def test_wall_clock_includes_sleep_and_freezes_separately():
    with TemporaryDirectory() as tmp:
        run=BenchmarkRun(BenchmarkConfig(repetitions=1),Path(tmp)/'run')
        run.started_at=10;run.wall_started_at=100
        with patch('benchmark.time.monotonic',return_value=20),patch('benchmark.time.time',return_value=1000):
            result=run.summary('running')
        assert result['elapsed_seconds']==10
        assert result['wall_elapsed_seconds']==900
        assert result['wall_clock_difference_seconds']==890
        run.ended_at=20;run.wall_ended_at=1000
        assert run.summary('completed')['wall_elapsed_seconds']==900


def test_inflight_fallback_and_model_counts_are_visible_before_round_end():
    with TemporaryDirectory() as tmp:
        run=BenchmarkRun(BenchmarkConfig(repetitions=1),Path(tmp)/'run')
        run.llm_decisions=3;run.fallback_reasons['invalid_action_json']=1
        summary=run.summary('running')
        assert summary['llm_decisions']==3 and summary['fallback_decisions']==1
        assert summary['completed']==0
