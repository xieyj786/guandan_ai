import sys,time,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import tkinter as tk
import benchmark_gui as module
with tempfile.TemporaryDirectory() as folder:
    module.filedialog.askdirectory=lambda **kw:folder
    notices=[]
    module.messagebox.showinfo=lambda *a:notices.append(a)
    module.messagebox.showerror=lambda *a:notices.append(a)
    root=tk.Tk(); app=module.BenchmarkWindow(root)
    app.rounds.set('2');app.start();app.pause()
    for _ in range(10):root.update();time.sleep(.03)
    assert not app.run.play.is_set()
    app.pause()
    deadline=time.monotonic()+40
    while app.worker.is_alive() and time.monotonic()<deadline:root.update();time.sleep(.02)
    for _ in range(10):root.update();time.sleep(.03)
    assert not app.worker.is_alive()
    assert app.run.summary('completed')['completed']==2
    assert '胜率' in app.output.get('1.0','end')
    assert str(app.start_btn['state'])=='normal'
    root.destroy()
    assert not notices,notices
print('Benchmark GUI: two real rounds, pause/resume, summary and control reset passed')
