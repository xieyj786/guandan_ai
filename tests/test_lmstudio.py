"""Local-model protocol and credential isolation; all requests are simulated."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import json
import tempfile
from unittest.mock import patch
from agents.lmstudio_client import LMStudioClient,validate_local_url
from agents.llm_client import LLMRequestError
from agents.deepseek_agent import DeepSeekAgent
from agents.base import Observation
from game_engine.card import Card,Rank,Suit
from llm_settings import LLMSettings,configured_client


def test_local_url_and_timeout_validation():
    for url in ('http://127.0.0.1:1234/v1/','http://localhost:1234/v1','http://[::1]:1234/v1'):
        assert validate_local_url(url).endswith('/v1')
    for url in ('https://example.com/v1','http://localhost.evil/v1','http://user@localhost/v1',
                'http://localhost:bad/v1','http://localhost:0/v1','http://localhost:1234',
                'http://localhost/v1?key=x','file:///v1'):
        try: validate_local_url(url); assert False,url
        except ValueError: pass
    for timeout in (True,0,601,'180'):
        try: LMStudioClient(timeout=timeout); assert False
        except ValueError: pass


def test_local_request_schema_and_inference_test():
    client=LMStudioClient()
    reply={'choices':[{'message':{'content':'{"action_id":0,"reason":"小牌"}'}}]}
    with patch('agents.lmstudio_client._post_json',return_value=reply) as post:
        assert json.loads(client.chat('own hand'))['action_id']==0
        args=post.call_args
        assert args.args[0]=='http://127.0.0.1:1234/v1/chat/completions'
        assert args.args[1]=={'Content-Type':'application/json'}
        assert args.kwargs['timeout']==180 and post.call_count==1
        payload=args.args[2]
        assert payload['model']=='qwen/qwen3.5-9b'
        assert 'thinking' not in payload and not payload['stream']
        assert payload['response_format']['json_schema']['schema']['required']==['action_id','reason']
        reply['choices'][0]['message']['content']='{"ok":true}'
        client.test_connection()
        assert post.call_args.args[2]['response_format']['json_schema']['schema']['required']==['ok']
        reply['choices'][0]['message']['content']='{}'
        try: client.test_connection(); assert False
        except LLMRequestError: pass


def test_local_invalid_responses_and_no_retries():
    for reply,kind in [({},'invalid_response'),({'choices':[]},'invalid_response'),
          ({'choices':[None]},'invalid_response'),
          ({'choices':[{'message':{'content':''}}]},'empty_content'),
          ({'choices':[{'finish_reason':'length'}]},'truncated')]:
        client=LMStudioClient()
        with patch('agents.lmstudio_client._post_json',return_value=reply) as post:
            try: client.chat('test'); assert False
            except LLMRequestError:
                assert client.last_error_kind==kind and post.call_count==1
    with patch('agents.lmstudio_client._post_json',side_effect=RuntimeError('private hand')):
        try: LMStudioClient().chat('test'); assert False
        except LLMRequestError as exc: assert 'private hand' not in str(exc)


def test_local_settings_and_no_cloud_credentials():
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'llm.json'
        path.write_text('{"enabled":true,"model":"deepseek-flash","seat":2}')
        assert LLMSettings.load(path).provider=='DeepSeek'
        settings=LLMSettings(True,'qwen/qwen3.5-9b',2,'LM Studio')
        settings.save(path);assert LLMSettings.load(path)==settings
        assert 'api_key' not in path.read_text()
        with patch('llm_settings.Keychain',side_effect=AssertionError('read cloud key')):
            client=configured_client(settings)
            assert isinstance(client,LMStudioClient)
            with patch('agents.lmstudio_client._post_json',return_value={'choices':[{'message':{'content':'{"ok":true}'}}]}):
                client.test_connection()
        data=json.loads(path.read_text());data['base_url']='http://evil/v1'
        path.write_text(json.dumps(data));assert not LLMSettings.load(path).enabled


def test_local_agent_and_fallback():
    obs=Observation([Card(Suit.SPADE,Rank.THREE),Card(Suit.HEART,Rank.NINE)],Rank.TWO,None,7,(4,6))
    agent=DeepSeekAgent('AI3',LMStudioClient())
    with patch('agents.lmstudio_client._post_json',return_value={'choices':[{'message':{'content':'{"action_id":0,"reason":"走完"}'}}]}):
        assert agent.decide(obs).cards==[obs.hand[0]]
        assert 'LM Studio' in agent.report and 'DeepSeek' not in agent.report
    with patch('agents.lmstudio_client._post_json',side_effect=LLMRequestError('本地超时')):
        assert agent.decide(obs).cards==[obs.hand[0]] and '规则接管' in agent.report


def test_local_dialog_save_does_not_access_keychain():
    from llm_dialog import LLMDialog
    class Var:
        def __init__(self,v): self.value=v
        def get(self): return self.value
    class Message:
        def configure(self,**kw): pass
    d=LLMDialog.__new__(LLMDialog);d.busy=d.closed=False
    for key,value in dict(provider='LM Studio',model='qwen/qwen3.5-9b',seat='AI3',enabled=False,
            base_url='http://127.0.0.1:1234/v1',timeout='180',compact=False,secret='must-not-send').items():
        setattr(d,key,Var(value))
    d.message=Message();d.close=lambda:None;saved=[];d.on_saved=saved.append
    d._run=lambda work,done:done(work())
    with patch('llm_settings.Keychain',side_effect=AssertionError('cloud credentials')),patch.object(LLMSettings,'save') as save:
        d.save();assert save.call_count==1 and saved[0].provider=='LM Studio'


def test_local_reasoning_routed_structured_json():
    client=LMStudioClient()
    def response(raw,finish='stop',content=''):
        return {'choices':[{'finish_reason':finish,'message':{
            'content':content,'reasoning_content':raw}}]}
    with patch('agents.lmstudio_client._post_json',return_value=response('{"ok":true}')):
        client.test_connection()
    with patch('agents.lmstudio_client._post_json',return_value=response('{"action_id":0,"reason":"出牌"}')):
        assert json.loads(client.chat('test'))['action_id']==0
    for raw,finish in [('{"ok":true}','length'),('thinking... {"ok":true}','stop'),
            ('{"ok":1}','stop'),('{"ok":true,"extra":1}','stop'),('{"ok":','stop')]:
        with patch('agents.lmstudio_client._post_json',return_value=response(raw,finish)):
            try:client.test_connection();assert False
            except LLMRequestError:pass
    for raw in ('{"action_id":true,"reason":"a"}', '{"action_id":-1,"reason":"a"}',
                '{"action_id":0,"reason":1}', '{"action_id":0}',
                '{"action_id":0,"reason":"'+('a'*121)+'"}'):
        with patch('agents.lmstudio_client._post_json',return_value=response(raw)):
            try:client.chat('test');assert False
            except LLMRequestError:pass
    with patch('agents.lmstudio_client._post_json',return_value=response('{"ok":true}',content='invalid正文')):
        try:client.test_connection();assert False
        except LLMRequestError:pass
