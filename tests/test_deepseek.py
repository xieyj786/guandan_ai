"""合法动作协议、错误接管、配置隔离与真实 HTTP 请求形状。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import tempfile
from unittest.mock import patch
from agents.base import Observation
from agents.deepseek_agent import DeepSeekAgent
from agents.llm_client import DeepSeekLLMClient, LLMRequestError
from game_engine.card import Card, Rank, Suit
from game_engine.identify import identify_card_type
from game_engine.comparator import compare_card_type
from llm_settings import LLMSettings


class Reply:
    def __init__(self, value):
        self.value = value
        self.prompt = ''
    def chat(self, prompt):
        self.prompt = prompt
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def obs(last=None):
    return Observation([Card(Suit.SPADE, Rank.THREE), Card(Suit.HEART, Rank.NINE)],
                       Rank.TWO, last, 7, (4, 6))


def test_candidate_protocol_and_public_context():
    client = Reply('{"action_id":0,"reason":"保留大牌"}')
    agent = DeepSeekAgent('AI1', client)
    state = obs()
    action = agent.decide(state)
    assert action.cards == agent.candidates(state)[0].cards
    assert '手牌' in client.prompt and '下家和上家' in client.prompt
    assert 'DeepSeek' in agent.report
    assert all(a.action_type == 'play' for a in agent.candidates(state))
    last = identify_card_type([Card(Suit.CLUB, Rank.FIVE)], Rank.TWO)
    actions = agent.candidates(obs(last))
    assert any(a.action_type == 'pass' for a in actions)
    for a in actions:
        if a.action_type == 'play':
            assert compare_card_type(identify_card_type(a.cards, Rank.TWO), last, Rank.TWO) == 1


def test_invalid_and_failed_llm_fall_back_legally():
    for reply in ('[]', 'null', 'bad', '{"action_id":true}', '{"action_id":-1}',
                  '{"action_id":999}', '{"action_id":"0"}', LLMRequestError('连接超时')):
        agent = DeepSeekAgent('AI1', Reply(reply))
        action = agent.decide(obs())
        assert action.action_type == 'play'
        assert action.cards == [obs().hand[0]]
        assert '规则接管' in agent.report


def test_settings_never_store_key_and_recover_bad_json():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'llm.json'
        assert not LLMSettings.load(path).enabled
        settings = LLMSettings(True, 'deepseek-flash', 2)
        settings.save(path)
        assert LLMSettings.load(path) == settings
        assert set(json.loads(path.read_text())) == {'enabled', 'model', 'seat'}
        path.write_text('[]')
        assert not LLMSettings.load(path).enabled
        path.write_text('{"enabled":true,"model":"x","seat":99}')
        assert not LLMSettings.load(path).enabled


def test_deepseek_transport_configuration_and_safe_failures():
    client = DeepSeekLLMClient('test-secret', max_retries=1)
    with patch('agents.llm_client._post_json', return_value={'choices':[{'message':{'content':'{"ok":true}'}}]}) as post:
        assert client.chat('JSON test') == '{"ok":true}'
        args = post.call_args
        assert args.args[0] == 'https://api.deepseek.com/chat/completions'
        assert args.args[1]['Authorization'] == 'Bearer test-secret'
        assert args.args[2]['response_format'] == {'type':'json_object'}
        assert args.args[2]['thinking'] == {'type':'disabled'}
        assert args.kwargs['timeout'] == 25
    with patch('agents.llm_client._post_json', side_effect=ValueError('test-secret')):
        try:
            client.chat('test')
            assert False
        except LLMRequestError as exc:
            assert 'test-secret' not in str(exc)


def test_macos_system_ca_keeps_verification_enabled():
    import ssl
    from agents.llm_client import _tls_context
    context = _tls_context()
    assert context.check_hostname
    assert context.verify_mode == ssl.CERT_REQUIRED
    with patch('agents.llm_client.ssl.create_default_context') as factory, \
         patch('agents.llm_client.sys.platform', 'darwin'), \
         patch('agents.llm_client.Path.is_file', return_value=True):
        _tls_context()
        factory.return_value.load_verify_locations.assert_called_once_with(cafile=str(Path('/etc/ssl/cert.pem')))


def test_connection_failures_are_distinct_and_redacted():
    import ssl
    import socket
    from urllib.error import URLError
    from agents.llm_client import _post_json
    failures = [
        (URLError(ssl.SSLCertVerificationError(1, 'secret-in-error')), '证书'),
        (URLError(socket.gaierror(-2, 'secret-in-error')), 'DNS'),
        (TimeoutError('secret-in-error'), '超时'),
        (URLError(OSError('secret-in-error')), '网络'),
    ]
    for failure, expected in failures:
        with patch('agents.llm_client.urlopen', side_effect=failure):
            try:
                _post_json('https://api.deepseek.com/chat/completions', {}, {})
                assert False
            except LLMRequestError as exc:
                assert expected in str(exc) and 'secret-in-error' not in str(exc)


def test_masked_key_rejected_without_network_or_secret_echo():
    from agents.llm_client import validate_api_key
    for key in ('sk-abc*****123', 'sk-abc…123', 'sk-abc●123', 'sk-abc...123', 'sk-abc 123'):
        try:
            validate_api_key(key)
            assert False
        except LLMRequestError as exc:
            assert key not in str(exc)
    assert validate_api_key('  sk-example-full-key  ') == 'sk-example-full-key'
