"""Numeric request telemetry only; no prompts, credentials or response text."""
import time

TOKEN_FIELDS = ('prompt_tokens', 'completion_tokens', 'total_tokens', 'reasoning_tokens', 'cached_tokens')


def measured_post(client, post, *args, **kwargs):
    started = time.monotonic()
    metrics = dict(seconds=0.0, response_received=False, **{key: None for key in TOKEN_FIELDS})
    client.last_request_metrics = metrics
    try:
        data = post(*args, **kwargs)
        metrics['response_received'] = True
        usage = data.get('usage') if isinstance(data, dict) else None
        if isinstance(usage, dict):
            for key in TOKEN_FIELDS[:3]:
                value = usage.get(key)
                if type(value) is int and value >= 0:
                    metrics[key] = value
            for parent, key in (('completion_tokens_details', 'reasoning_tokens'),
                                ('prompt_tokens_details', 'cached_tokens')):
                details = usage.get(parent)
                value = details.get(key) if isinstance(details, dict) else None
                if type(value) is int and value >= 0:
                    metrics[key] = value
        return data
    finally:
        metrics['seconds'] = max(0.0, time.monotonic() - started)


def empty_totals():
    return dict(requests=0, responses=0, request_seconds=0.0, max_request_seconds=0.0,
                **{key: 0 for key in TOKEN_FIELDS},
                **{key + '_reported_requests': 0 for key in TOKEN_FIELDS})


def add_request(totals, metrics):
    totals['requests'] += 1
    totals['responses'] += int(metrics['response_received'])
    totals['request_seconds'] += metrics['seconds']
    totals['max_request_seconds'] = max(totals['max_request_seconds'], metrics['seconds'])
    for key in TOKEN_FIELDS:
        if metrics[key] is not None:
            totals[key] += metrics[key]
            totals[key + '_reported_requests'] += 1


def combine_totals(parts):
    result = empty_totals()
    for part in parts:
        for key in result:
            if key == 'max_request_seconds':
                result[key] = max(result[key], part[key])
            else:
                result[key] += part[key]
    return result


def describe_totals(totals):
    result = dict(totals)
    n = totals['requests']
    result['average_request_seconds'] = totals['request_seconds'] / n if n else None
    for key in TOKEN_FIELDS:
        if not totals[key + '_reported_requests']:
            result[key] = None
    return result
