"""LM Studio on this computer; no cloud credentials, retries or vendor-only fields."""
from __future__ import annotations
import json
from urllib.parse import urlsplit
from integrations.llm.client import LLMRequestError, _post_json
from integrations.llm.metrics import measured_post


def validate_local_url(value: str) -> str:
    parts = urlsplit(value.strip())
    try:
        port = parts.port
    except ValueError:
        raise ValueError('本地服务端口无效') from None
    if (parts.scheme not in ('http', 'https')
            or parts.hostname not in ('127.0.0.1', 'localhost', '::1')
            or parts.username is not None or parts.password is not None
            or parts.query or parts.fragment or parts.path.rstrip('/') != '/v1'
            or port == 0):
        raise ValueError('请填写本机兼容地址，例如 http://127.0.0.1:1234/v1')
    return value.strip().rstrip('/')


def _matches_schema_json(raw, schema):
    """Accept an entire structured object only; never extract JSON from prose."""
    if not isinstance(raw, str):
        return False
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return False
    properties = schema['properties']
    if not isinstance(data, dict) or set(data) != set(schema['required']):
        return False
    for key, value in data.items():
        spec = properties[key]
        if 'enum' in spec and value not in spec['enum']:
            return False
        if spec['type'] == 'boolean' and type(value) is not bool:
            return False
        if spec['type'] == 'integer' and (type(value) is not int or value < spec.get('minimum', value)):
            return False
        if spec['type'] == 'string' and (not isinstance(value, str) or len(value) > spec.get('maxLength', len(value))):
            return False
    return True


class LMStudioClient:
    provider_name = 'LM Studio'

    def __init__(self, model='qwen/qwen3.5-9b', base_url='http://127.0.0.1:1234/v1', timeout=180, speed_mode=False):
        self.base_url = validate_local_url(base_url)
        if not isinstance(model, str) or not model.strip():
            raise ValueError('请填写 LM Studio 的模型标识')
        if type(timeout) is not int or not 10 <= timeout <= 600:
            raise ValueError('本地等待时间须为10～600秒的整数')
        self.model, self.timeout = model.strip(), timeout
        self.last_error_kind = ''
        self.speed_mode = speed_mode

    def _request(self, prompt, schema):
        self.last_error_kind = ''
        messages = [{'role': 'user', 'content': prompt}]
        if self.speed_mode and '\n' in prompt:
            system, user = prompt.split('\n', 1)
            messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]
        payload = {'model': self.model, 'messages': messages,
                   'stream': False, 'temperature': 0.2, 'max_tokens': 1024,
                   'response_format': {'type': 'json_schema', 'json_schema': {
                       'name': 'guandan_response', 'strict': True, 'schema': schema}}}
        try:
            data = measured_post(self, _post_json, self.base_url + '/chat/completions',
                              {'Content-Type': 'application/json'}, payload, timeout=self.timeout)
        except LLMRequestError:
            self.last_error_kind = 'api_error'
            raise
        except Exception:
            self.last_error_kind = 'transport_error'
            raise LLMRequestError('LM Studio 请求失败，请检查本地服务与模型') from None
        try:
            choice = data['choices'][0]
            if choice.get('finish_reason') == 'length':
                self.last_error_kind = 'truncated'
                raise LLMRequestError('本地模型输出达到长度上限；请检查 Thinking 设置后重试')
            message = choice['message']
            content = message.get('content')
            # Some LM Studio reasoning parsers route the entire schema-constrained
            # answer to reasoning_content. Accept only a full, validated object
            # on a normal stop, never prose, partial JSON or truncated output.
            if (isinstance(content, str) and not content.strip() or content is None):
                structured = message.get('reasoning_content')
                if choice.get('finish_reason') == 'stop' and _matches_schema_json(structured, schema):
                    content = structured
            if not isinstance(content, str) or not content.strip():
                self.last_error_kind = 'empty_content'
                raise LLMRequestError('本地模型没有返回正文，请检查模型与 Thinking 设置')
            return content
        except LLMRequestError:
            raise
        except (KeyError, IndexError, TypeError, AttributeError):
            self.last_error_kind = 'invalid_response'
            raise LLMRequestError('LM Studio 返回结构不符合兼容接口约定') from None

    def chat(self, prompt):
        properties = {'action_id': {'type': 'integer', 'minimum': 0}}
        required = ['action_id']
        if not self.speed_mode:
            properties['reason'] = {'type': 'string', 'maxLength': 120}
            required.append('reason')
        # Constrain actual action IDs in the decoder, not just their JSON type.
        # Generic client callers without an agent state retain the old schema.
        try:
            state = json.loads(prompt.split('\n', 1)[1])
            actions = state.get('动作', state.get('合法动作'))
            if isinstance(actions, dict) and actions and set(actions) == {str(i) for i in range(len(actions))}:
                properties['action_id']['enum'] = list(range(len(actions)))
        except (IndexError, ValueError, TypeError, AttributeError):
            pass
        return self._request(prompt, {'type': 'object', 'properties': properties,
            'required': required, 'additionalProperties': False})

    def test_connection(self):
        raw = self._request('连接测试。请只输出 JSON：{"ok":true}', {
            'type': 'object', 'properties': {'ok': {'type': 'boolean'}},
            'required': ['ok'], 'additionalProperties': False})
        try:
            if json.loads(raw) != {'ok': True}:
                raise ValueError()
        except (ValueError, TypeError):
            raise LLMRequestError('服务已响应，但测试回答格式不符合要求') from None
