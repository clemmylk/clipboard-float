"""Local per-user installer. No downloads, administrator rights or shared history."""
import argparse,ctypes,json,os,shutil,subprocess,sys,traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
APP_FILES=('clipboard_history.py','clipboard_backend.py','floating_clipboard.py','filee_motion.py','setup_tool.py','START.bat','INSTALL.bat','UNINSTALL.bat','CHECK_SETUP.bat','README.md','QUICK_START.txt','PRIVACY.md','LICENSE','THIRD_PARTY_NOTICES.md','VERSION.txt','requirements.txt')
APP_FOLDERS=('runtime','assets','third_party')

def running():
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenMutexW.argtypes=[ctypes.c_uint32,ctypes.c_bool,ctypes.c_wchar_p]
    k.OpenMutexW.restype=ctypes.c_void_p;k.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=k.OpenMutexW(0x00100000,False,r'Local\ClipboardHistoryRunning_v1')
    if handle:k.CloseHandle(handle)
    return bool(handle)

def check():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage
    import clipboard_backend,filee_motion,floating_clipboard
    if not (ROOT/'runtime/python.exe').is_file():raise RuntimeError('Use the Windows-x64 setup ZIP; the source-only ZIP does not include Python.')
    if Path(sys.base_prefix).resolve()!=(ROOT/'runtime').resolve():raise RuntimeError('Run INSTALL.bat so the included Python runtime is used.')
    app=QApplication.instance() or QApplication([])
    assert app.platformName() in ('windows','offscreen','minimal')
    for name in APP_FILES:
        if not (ROOT/name).is_file():raise RuntimeError('Missing package file: '+name+'. Extract the entire ZIP again.')
    print('Bundled Python, Qt interface and application files: OK',flush=True)
    return app

def shortcut_folders():
    script="@{desktop=[Environment]::GetFolderPath('Desktop');startup=[Environment]::GetFolderPath('Startup')} | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],check=True,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    data=json.loads(result.stdout)
    return Path(data['desktop']),Path(data['startup'])

def shortcuts(destination,desktop,startup,remove=False):
    env=os.environ.copy();env.update(CLIP_ROOT=str(destination),CLIP_DESKTOP=str(desktop),CLIP_STARTUP=str(startup),CLIP_REMOVE='1' if remove else '0')
    script=r'''$ErrorActionPreference='Stop'
$shell=New-Object -ComObject WScript.Shell
$root=[IO.Path]::GetFullPath($env:CLIP_ROOT)
foreach($item in @(@($env:CLIP_DESKTOP,'Clipboard Float.lnk',''),@($env:CLIP_STARTUP,'Clipboard History.lnk',' --background'))) {
    $folder=$item[0]; $path=Join-Path $folder $item[1]
    if($env:CLIP_REMOVE -eq '1') {
        if(Test-Path -LiteralPath $path) {
            $link=$shell.CreateShortcut($path)
            if($link.TargetPath -eq (Join-Path $root 'runtime\pythonw.exe')) { Remove-Item -LiteralPath $path -Force }
        }
        continue
    }
    [IO.Directory]::CreateDirectory($folder) | Out-Null
    $link=$shell.CreateShortcut($path)
    $link.TargetPath=Join-Path $root 'runtime\pythonw.exe'
    $link.Arguments='"'+(Join-Path $root 'clipboard_history.py')+'"'+$item[2]
    $link.WorkingDirectory=$root
    $link.IconLocation=Join-Path $root 'assets\clipboard-float.ico'
    $link.Description='Clipboard Float - Tab + V'
    $link.WindowStyle=7
    $link.Save()
}'''
    subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=env,check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)

def install(destination=None,desktop=None,startup=None,launch=True):
    app=check()
    if launch and running():raise RuntimeError('Clipboard Float is already running. Choose Quit from its tray menu, then run INSTALL.bat again.')
    destination=Path(destination) if destination is not None else Path(os.environ['LOCALAPPDATA'])/'ClipboardFloat'
    if destination.is_symlink() or destination.is_junction():raise RuntimeError('The installation folder must be a normal local folder.')
    destination=destination.resolve()
    if ROOT!=destination:
        destination.mkdir(parents=True,exist_ok=True)
        for name in APP_FILES:shutil.copy2(ROOT/name,destination/name)
        for name in APP_FOLDERS:
            shutil.copytree(ROOT/name,destination/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.log'))
    (destination/'.clipboardfloat-install.json').write_text(json.dumps({'version':(ROOT/'VERSION.txt').read_text().strip(),'folder':str(destination)}),encoding='utf-8')
    if desktop is None or startup is None:desktop,startup=shortcut_folders()
    shortcuts(destination,Path(desktop),Path(startup))
    if launch:
        subprocess.Popen([str(destination/'runtime/pythonw.exe'),str(destination/'clipboard_history.py')],cwd=destination,creationflags=subprocess.CREATE_NO_WINDOW)
    print('Installed. Desktop shortcut and automatic startup are ready. Press Tab + V.',flush=True)
    return destination

def uninstall():
    expected=(Path(os.environ['LOCALAPPDATA'])/'ClipboardFloat').resolve()
    if ROOT!=expected or not (ROOT/'.clipboardfloat-install.json').is_file():raise RuntimeError('Run UNINSTALL.bat from the installed ClipboardFloat folder.')
    if ROOT.is_symlink() or ROOT.is_junction():raise RuntimeError('Refusing to remove a linked folder.')
    if running():raise RuntimeError('Choose Quit in the Clipboard Float tray menu, then run UNINSTALL.bat again.')
    desktop,startup=shortcut_folders();shortcuts(ROOT,desktop,startup,remove=True)
    env=os.environ.copy();env['CLIP_DELETE_ROOT']=str(ROOT);env['CLIP_DELETE_PID']=str(os.getpid())
    script=r'''$ErrorActionPreference='Stop'
Wait-Process -Id ([int]$env:CLIP_DELETE_PID) -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 300
$expected=[IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'ClipboardFloat'))
$target=[IO.Path]::GetFullPath($env:CLIP_DELETE_ROOT)
if(-not [String]::Equals($expected,$target,[StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected removal target' }
if(Test-Path -LiteralPath $target) {
    if(([IO.File]::GetAttributes($target) -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Refusing linked folder removal' }
    Remove-Item -LiteralPath $target -Recurse -Force
}'''
    subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=env,cwd=os.environ.get('TEMP',str(Path.home())),creationflags=subprocess.CREATE_NO_WINDOW)
    print('Shortcuts removed. The installed folder will be removed when this window closes.',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check-only',action='store_true');parser.add_argument('--uninstall',action='store_true');args=parser.parse_args()
    try:
        if args.uninstall:uninstall()
        elif args.check_only:check()
        else:install()
    except Exception as exc:
        print('Setup could not finish: '+str(exc),flush=True);sys.exit(1)
