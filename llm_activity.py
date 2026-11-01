"""Thread-safe numeric activity handoff; UI reads and renders on its own thread."""
from collections import Counter
from queue import SimpleQueue, Empty
from agents.request_metrics import empty_totals, add_request, describe_totals


class LLMActivity:
    def __init__(self):
        self.pending = SimpleQueue()
        self.totals = empty_totals()
        self.kinds = Counter()

    def record(self, kind, metrics):
        self.pending.put((kind, dict(metrics) if metrics else None))

    def summary(self):
        while True:
            try:
                kind, metrics = self.pending.get_nowait()
            except Empty:
                break
            self.kinds[kind] += 1
            if metrics is not None:
                add_request(self.totals, metrics)
        return dict(usage=describe_totals(self.totals), automatic=self.kinds['automatic'],
                    fallbacks=self.kinds['fallback'])


def activity_text(data):
    usage = data['usage']
    def tokens(key):
        value = usage[key]
        if value is None:
            return '未提供'
        covered = usage[key + '_reported_requests']
        suffix = f'（{covered}/{usage["requests"]}次已知）' if covered < usage['requests'] else ''
        return f'{value:,}' + suffix
    average = usage['average_request_seconds']
    return (f'本窗口累计：请求{usage["requests"]}次 · 自动执行{data["automatic"]}次 · 回退{data["fallbacks"]}次 · '
            f'请求耗时{usage["request_seconds"]:.1f}秒'
            + (f' · 平均{average:.2f}秒/次' if average is not None else '')
            + f'\nToken 输入{tokens("prompt_tokens")} / 输出{tokens("completion_tokens")} / 总计{tokens("total_tokens")} '
              '（含已丢弃请求，不含连接测试）')
