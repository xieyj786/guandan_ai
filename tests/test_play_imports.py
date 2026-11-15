"""The offline desktop must not load GUI network integrations on import."""
import subprocess
import sys
from pathlib import Path


def test_offline_play_import_does_not_load_llm():
    subprocess.run([sys.executable, '-c', '''
import sys
from play import GuandanPlay
from presentation.table_view import GameTableView
assert issubclass(GuandanPlay, GameTableView)
assert 'presentation.gui' not in sys.modules
assert not any(name.startswith('integrations.llm') for name in sys.modules)
'''], cwd=Path(__file__).resolve().parent.parent, check=True)
