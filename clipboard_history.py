"""Desktop/startup entry point. Clipboard contents are never written to this log."""
import os,sys,traceback,ctypes
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))

if __name__=='__main__':
    logs=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'ClipboardFloat'/'logs'
    logs.mkdir(parents=True,exist_ok=True)
    sys.stderr=(logs/'application-errors.log').open('a',encoding='utf-8',buffering=1)
    try:
        from floating_clipboard import main
        main()
    except Exception:
        traceback.print_exc()
        ctypes.windll.user32.MessageBoxW(0,'Clipboard Float could not start.\nRun CHECK_SETUP.bat or check:\n'+str(logs/'application-errors.log'),'Clipboard Float',16)
        sys.exit(1)
