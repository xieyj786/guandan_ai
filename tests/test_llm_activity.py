import tempfile
from pathlib import Path
from unittest.mock import patch
from llm_activity import LLMActivity,activity_text
from llm_settings import LLMSettings,configured_client,StoredDeepSeekClient
from agents.llm_client import LLMRequestError


def test_local_speed_setting_backward_compatible_and_key_isolated():
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'settings.json'
        settings=LLMSettings(True,'qwen/qwen3.5-9b',2,'LM Studio',local_speed_mode=True)
        settings.save(path);assert LLMSettings.load(path)==settings
        with patch('llm_settings.Keychain',side_effect=AssertionError('key access')):
            assert configured_client(settings).speed_mode is True
        path.write_text('{"enabled":true,"model":"qwen","seat":2,"provider":"LM Studio"}')
        assert not LLMSettings.load(path).local_speed_mode
        path.write_text('{"enabled":true,"model":"qwen","seat":2,"provider":"LM Studio","local_speed_mode":"true"}')
        assert not LLMSettings.load(path).enabled


def test_activity_counts_automatic_failed_and_discarded_requests():
    activity=LLMActivity()
    metrics=dict(seconds=2,response_received=True,prompt_tokens=10,completion_tokens=4,
                 total_tokens=14,reasoning_tokens=None,cached_tokens=None)
    activity.record('automatic',None)
    # Completion may be recorded after a GUI reset; it must still count.
    activity.record('llm',metrics)
    metrics['total_tokens']=999
    activity.record('fallback',dict(seconds=3,response_received=False,
        **{k:None for k in ('prompt_tokens','completion_tokens','total_tokens','reasoning_tokens','cached_tokens')}))
    s=activity.summary()
    assert s['automatic']==1 and s['fallbacks']==1
    assert s['usage']['requests']==2 and s['usage']['total_tokens']==14
    assert s['usage']['request_seconds']==5
    assert activity.summary()==s
    text=activity_text(s)
    assert '1/2次已知' in text and '含已丢弃请求' in text


def test_cloud_wrapper_forwards_numeric_usage_even_on_error():
    class Store:
        def get(self):return 'sk-test-key'
    wrapper=StoredDeepSeekClient('model')
    with patch('llm_settings.Keychain',return_value=Store()),patch('agents.llm_client._post_json',return_value={
            'choices':[{'message':{'content':'{"action_id":0}'}}],
            'usage':{'prompt_tokens':10,'completion_tokens':4,'total_tokens':14}}):
        wrapper.chat('test')
        assert wrapper.last_request_metrics['total_tokens']==14
    with patch('agents.llm_client._post_json',side_effect=LLMRequestError('timeout')):
        try:wrapper.chat('test')
        except LLMRequestError:pass
        else:assert False
        assert wrapper.last_request_metrics['total_tokens'] is None
        assert not wrapper.last_request_metrics['response_received']


def test_cloud_main_client_matches_benchmark_error_classification_and_usage():
    from agents.llm_client import DeepSeekLLMClient
    cases=[({'choices':[{'finish_reason':'length','message':{'content':'{}'}}]},'truncated'),
           ({'choices':[{'message':{'content':''}}]},'empty_content'),({'choices':[]},'invalid_response')]
    for response,kind in cases:
        response['usage']={'prompt_tokens':5,'completion_tokens':2,'total_tokens':7}
        client=DeepSeekLLMClient('sk-test-only',max_retries=1)
        with patch('agents.llm_client._post_json',return_value=response) as post:
            try:client.chat('test')
            except LLMRequestError:pass
            else:assert False
            assert client.last_error_kind==kind and client.last_request_metrics['total_tokens']==7
            assert post.call_args.args[2]['max_tokens']==512
