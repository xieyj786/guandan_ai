"""Enforce module ownership and one-way dependencies without third-party tools."""
import ast
import importlib
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
LAYERS = {'game_engine', 'strategy', 'gameplay', 'presentation', 'integrations', 'evaluation'}
LEGACY = {'agents', 'gui', 'viewer', 'play', 'card_ui', 'play_display', 'play_game',
          'match_runner', 'game_series', 'turn_log', 'llm_dialog', 'llm_settings',
          'llm_activity', 'benchmark', 'benchmark_gui', 'benchmark_report', 'benchmark_runtime'}


def imports(path):
    module = '.'.join(path.relative_to(ROOT).with_suffix('').parts)
    package = module.rpartition('.')[0]
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                yield importlib.util.resolve_name('.' * node.level + (node.module or ''), package)
            else:
                yield node.module or ''
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
            if isinstance(node.func, ast.Name) and node.func.id == '__import__':
                yield node.args[0].value
            elif isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module':
                yield node.args[0].value


def test_layer_dependency_directions():
    allowed = {
        'game_engine': {'game_engine'},
        'strategy': {'strategy', 'game_engine', 'gameplay.contracts'},
        'gameplay': {'gameplay', 'game_engine', 'strategy'},
        'integrations': {'integrations', 'gameplay.contracts', 'gameplay.actions', 'game_engine', 'strategy'},
        'evaluation': {'evaluation', 'gameplay', 'game_engine', 'strategy', 'integrations'},
        'presentation': LAYERS,
    }
    for layer in sorted(LAYERS):
        for path in (ROOT / layer).rglob('*.py'):
            for target in imports(path):
                top = target.split('.')[0]
                assert top not in LEGACY, f'{path}: implementation imports compatibility module {target}'
                if top in LAYERS:
                    assert any(target == prefix or target.startswith(prefix + '.') for prefix in allowed[layer]), f'{path}: forbidden dependency {target}'
                elif layer != 'presentation':
                    assert top != 'tkinter', f'{path}: UI dependency leaked into {layer}'
                    if layer in ('game_engine', 'strategy', 'gameplay'):
                        assert top not in {'urllib', 'http', 'socket', 'ctypes', 'subprocess'}, f'{path}: platform/network dependency {target}'


def test_contract_and_card_renderer_stay_independent():
    assert all(t.split('.')[0] not in LAYERS - {'game_engine'}
               for t in imports(ROOT / 'gameplay/contracts.py'))
    assert all(t.split('.')[0] not in LAYERS
               for t in imports(ROOT / 'presentation/cards.py'))


def test_compatibility_modules_share_implementation_identity():
    pairs = {
        'agents.base': 'gameplay.contracts', 'agents.rule_agent': 'strategy.rule_agent',
        'agents.strategy_planner': 'strategy.planner', 'match_runner': 'gameplay.match',
        'game_series': 'gameplay.series', 'play_game': 'gameplay.offline',
        'turn_log': 'gameplay.turn_log', 'agents.deepseek_agent': 'integrations.llm.deepseek_agent',
        'agents.llm_agent': 'integrations.llm.legacy_agent', 'agents.llm_client': 'integrations.llm.client',
        'agents.lmstudio_client': 'integrations.llm.local_client', 'agents.llm_actions': 'integrations.llm.actions',
        'agents.local_prompt': 'integrations.llm.local_prompt', 'agents.request_metrics': 'integrations.llm.metrics',
        'llm_settings': 'integrations.llm.settings', 'llm_activity': 'integrations.llm.activity',
        'benchmark': 'evaluation.benchmark', 'benchmark_report': 'evaluation.report',
        'benchmark_runtime': 'evaluation.runtime',
    }
    for old, new in pairs.items():
        assert importlib.import_module(old) is importlib.import_module(new), (old, new)


def test_all_packages_in_distribution():
    import tomllib
    config = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    included = config['tool']['setuptools']['packages']['find']['include']
    assert all(layer + '*' in included for layer in LAYERS)


def test_ui_does_not_implement_turn_transitions_or_rule_comparison():
    forbidden_imports = {'game_engine.identify', 'game_engine.comparator',
                         'game_engine.moves', 'game_engine.legal_moves'}
    private_actions = {'_handle_play', '_handle_pass', '_take_turn', '_build_observation', '_active_players'}
    for path in (ROOT / 'presentation').glob('*.py'):
        assert not forbidden_imports.intersection(imports(path)), path
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in private_actions, f'{path}: direct internal turn method {node.func.attr}'
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    assert not (isinstance(target, ast.Attribute) and target.attr in {'last_play', 'pass_streak'}), f'{path}: turn transition leaked into UI'


def test_legacy_script_entrypoints_dispatch_main():
    import subprocess
    pairs = {
        'gui.py': 'presentation.gui', 'viewer.py': 'presentation.viewer',
        'play.py': 'presentation.play', 'benchmark_gui.py': 'presentation.benchmark_gui',
        'match_runner.py': 'gameplay.match', 'game_series.py': 'gameplay.series',
    }
    # Stub the target before executing the wrapper: verifies CLI wiring without Tk.
    code = '''
import runpy, sys, types
path, target = sys.argv[1:]
calls = []
module = types.ModuleType(target)
module.main = lambda: calls.append(True)
sys.modules[target] = module
runpy.run_path(path, run_name='__main__')
assert calls == [True], (path, calls)
'''
    for old, target in pairs.items():
        subprocess.run([sys.executable, '-B', '-c', code, old, target], cwd=ROOT, check=True)


def test_shared_progression_caps_levels_and_only_ace_double_down_finishes():
    from game_engine.card import Rank
    from gameplay.progression import advance_levels
    initial = {'A': Rank.KING, 'B': Rank.TWO}
    progress = advance_levels(initial, 'A', 3)
    assert progress.team_levels == {'A': Rank.ACE, 'B': Rank.TWO}
    assert progress.leading_team == 'A' and not progress.finished
    assert initial['A'] == Rank.KING
    for upgrade in (1, 2, 3):
        result = advance_levels(progress.team_levels, 'A', upgrade)
        assert result.team_levels['A'] == Rank.ACE
        assert result.finished == (upgrade == 3)
