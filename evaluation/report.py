"""Shared Chinese summary and complete UTF-8 benchmark report; no Tk dependency."""
import csv
import io
import json
from dataclasses import asdict
from pathlib import Path

def duration(seconds):
    if seconds is None:return '暂无'
    hours, remainder=divmod(max(0,int(seconds)),3600)
    minutes, seconds=divmod(remainder,60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


def usage_lines(data):
    lines=[]
    for label,usage in [('合计',data['usage']),('策略A',data['usage_by_strategy']['A']),
                        ('策略B',data['usage_by_strategy']['B'])]:
        count=usage['requests']
        def tokens(key):
            value=usage[key]
            if value is None:return '未提供'
            coverage=usage[key+'_reported_requests']
            return f'{value:,}' + (f'（仅{coverage}/{count}次已知）' if coverage<count else '')
        average=usage['average_request_seconds']
        lines.append(f"{label}：请求{count}次，收到JSON响应{usage['responses']}次；请求耗时{duration(usage['request_seconds'])}，"
                     + ('平均暂无' if average is None else f'平均{average:.2f}秒/次')
                     + f"，最慢{usage['max_request_seconds']:.2f}秒")
        lines.append(f"  Token：输入{tokens('prompt_tokens')} / 输出{tokens('completion_tokens')} / 总计{tokens('total_tokens')}")
        lines.append(f"  其中思考{tokens('reasoning_tokens')} / 输入缓存命中{tokens('cached_tokens')}（子项不重复加总）")
    lines.append('Token按接口usage记录；缺失不估算。请求统计含失败/取消局，不含连接测试。')
    return lines


def format_summary(data):
    rate=lambda v: '暂无' if v is None else f'{v:.2%}'
    names={'running':'运行中','completed':'已结束','cancelled':'已停止'}
    lines=[f"状态：{names.get(data['status'],data['status'])}  完成：{data['completed']}/{data['planned']}  失败：{data['failed']}",
           f"策略A（{data['labels'][0]}）：{data['wins_A']}胜，胜率{rate(data['win_rate_A'])}",
           f"策略B（{data['labels'][1]}）：{data['wins_B']}胜，胜率{rate(data['win_rate_B'])}",
           f"LLM决策：{data['llm_decisions']}；规则回退：{data['fallback_decisions']}次；含回退完成局：{data['fallback_rounds']}",
           f"唯一合法动作自动执行：{data.get('automatic_actions',0)}次（A：{data.get('automatic_actions_by_strategy',{}).get('A',0)}，B：{data.get('automatic_actions_by_strategy',{}).get('B',0)}；不计模型决策或规则回退）",
           f"钟表总时长：{duration(data.get('wall_elapsed_seconds',data['elapsed_seconds']))}（含系统睡眠；系统校时可能影响）",
           f"系统运行计时：{duration(data['elapsed_seconds'])}；按钮暂停：{duration(data['paused_seconds'])}；扣除暂停：{duration(data['active_seconds'])}",
           f"钟表与运行计时差：{data.get('wall_clock_difference_seconds',0):.1f}秒（可能含系统睡眠或校时）",
           f"平均每完成局：{duration(data['average_round_seconds'])}；预计剩余：{duration(data['estimated_remaining_seconds'])}（按当前均速粗估）"]
    if data.get('current_round'):
        lines.append(f"当前第{data['current_round']}局" +
                     (f"；策略{data['current_strategy']}本次决策已等待{data['current_request_seconds']:.1f}秒"
                      if data.get('current_strategy') else ''))
    lines.extend(usage_lines(data))
    lines.append('自然牌型（总次数 / 每局平均）：')
    for key,label in [('straight_flush','同花顺窗口'),('bomb6','6张炸弹'),('bomb7','7张炸弹'),('bomb8','8张炸弹'),('joker_bomb','王炸')]:
        avg=data['average_per_round'][key]
        lines.append(f"  {label}：{data['patterns'][key]} / {avg:.4f}" if avg is not None else f"  {label}：暂无")
    lines.append(f"完整轮：{data['completed_repetitions']}/{data['repetitions']}")
    for key,label in [('before_swap','换位前'),('after_swap','换位后')]:
        part=data[key]
        lines.append(f"{label}：完成{part['completed']}局；A胜率{rate(part['win_rate_A'])}，B胜率{rate(part['win_rate_B'])}")
    delta=data['swap_rate_difference_A']
    lines.append('换位后减换位前A胜率：'+('暂无' if delta is None else f'{delta*100:+.2f}个百分点（按各自完成局）'))
    pairs=data['pairs']
    lines.append(f"完整配对：{pairs['completed']}/{pairs['planned']}；缺失完整配对：{pairs['missing']}；仅完成一局：{pairs['incomplete']}")
    lines.append(f"配对比较：A两胜{pairs['A_two_wins']}；各胜一局{pairs['split']}；B两胜{pairs['B_two_wins']}")
    lines.append('各级牌：完成局 / A换位前胜率 / A换位后胜率 / A合并胜率（B为互补）')
    for level,part in data['by_level'].items():
        label={'11':'J','12':'Q','13':'K','14':'A'}.get(level,level)
        lines.append(f"  {label}：{part['combined']['completed']} / {rate(part['before_swap']['win_rate_A'])} / {rate(part['after_swap']['win_rate_A'])} / {rate(part['combined']['win_rate_A'])}")
    lines.append('同牌配对存在相关性，不报告普通独立样本置信区间。')
    lines.append('回退分类：'+json.dumps(data.get('fallback_reasons',{}),ensure_ascii=False))
    if data.get('fallback_decisions',0):lines.append('注意：存在规则接管，以上不是纯LLM胜率。')
    return '\n'.join(lines)


def render_report(run, summary):
    """Include the displayed summary and every exported aggregate/round field."""
    header = [
        '程序名称：掼蛋 · 独立牌局统计测试（benchmark_gui.py）',
        '测试引擎：benchmark.py；协议：level_sweep_paired_v2',
        f'开始时间：{run.started_time}',
        f'结束时间：{run.ended_time}',
        '时间时区：Asia/Shanghai（UTC+08:00）',
        f'总运行时长：{duration(summary.get("wall_elapsed_seconds",summary["elapsed_seconds"]))}（钟表时间，含系统睡眠）',
        f'系统运行计时：{summary["elapsed_seconds"]:.3f}秒；按钮暂停：{summary["paused_seconds"]:.3f}秒',
        f'详细日志目录：{run.folder.resolve()}',
        '', '统计结果', format_summary(summary),
        '', '完整运行配置（不含密钥）',
        json.dumps(dict(config=asdict(run.config), labels=run.labels), ensure_ascii=False, indent=2),
        '', '完整统计数据（JSON；null表示未提供或暂无）',
        json.dumps(summary, ensure_ascii=False, indent=2),
        '', '逐局统计明细（CSV；含失败和取消局，空Token字段表示未提供）',
    ]
    rows = io.StringIO(newline='')
    if run.rows:
        writer = csv.DictWriter(rows, fieldnames=list(run.rows[0]))
        writer.writeheader()
        writer.writerows(run.rows)
    else:
        rows.write('无已执行对局\n')
    content = '\n'.join(header) + '\n' + rows.getvalue()
    return content


def write_report(run, summary):
    """Number reports in the chosen log directory; never overwrite existing logs."""
    parent = run.folder.parent
    for number in range(1, 1000000):
        path = parent / f'benchmark_log_{number:03d}.txt'
        try:
            stream = path.open('x', encoding='utf-8', newline='')
        except FileExistsError:
            continue
        with stream:
            stream.write(render_report(run, dict(summary, report_path=str(path.resolve()))))
        return path.resolve()
    raise OSError('文本报告编号已用尽')
