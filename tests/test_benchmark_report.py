import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from benchmark import BenchmarkConfig, BenchmarkRun
from benchmark_report import write_report


def test_report_numbering_full_results_and_cancelled_run():
    with TemporaryDirectory() as tmp:
        parent=Path(tmp)
        previous=parent/'benchmark_log_001.txt'
        previous.write_text('preserve old report')
        run=BenchmarkRun(BenchmarkConfig(repetitions=1,max_turns=1),parent/'run')
        result=run.run()
        path=Path(result['report_path'])
        assert path.name=='benchmark_log_002.txt' and path.parent==parent.resolve()
        assert previous.read_text()=='preserve old report'
        text=path.read_text(encoding='utf-8')
        for value in ('benchmark_gui.py',run.started_time,run.ended_time,'总运行时长',
                      'Token','各级牌','配对比较','完整运行配置','逐局统计明细',
                      'A_total_tokens_reported_requests','max_request_seconds'):
            assert value in text,value
        complete=json.loads(text.split('完整统计数据（JSON；null表示未提供或暂无）\n')[1]
                            .split('\n\n逐局统计明细')[0])
        assert complete==json.loads(json.dumps(result))
        assert len(run.rows)==26 and complete['failed']==26
        assert json.loads((run.folder/'summary.json').read_text())==complete
        cancelled=BenchmarkRun(BenchmarkConfig(repetitions=1),parent/'cancel')
        cancelled.cancel.set()
        result=cancelled.run()
        assert Path(result['report_path']).name=='benchmark_log_003.txt'
        text=Path(result['report_path']).read_text()
        assert '已停止' in text and '无已执行对局' in text


def test_report_failure_is_not_silently_reported_as_success():
    with TemporaryDirectory() as tmp:
        run=BenchmarkRun(BenchmarkConfig(repetitions=1),Path(tmp)/'run')
        run.cancel.set()
        with patch('benchmark.write_report',side_effect=OSError('disk full')):
            try:run.run()
            except OSError:pass
            else:assert False
        assert run.report_path is None
