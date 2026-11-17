import json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import setup_tool

class InstallerTests(unittest.TestCase):
    def fake_source(self,root):
        for name in setup_tool.APP_FILES:
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('1.0.0' if name=='VERSION.txt' else '')
        for name in setup_tool.APP_FOLDERS:(root/name).mkdir(exist_ok=True)
        (root/'runtime/pythonw.exe').write_bytes(b'fake test executable, never run')
        (root/'application-errors.log').write_text('private diagnostic')
        (root/'clipboard-history.json').write_text('private history')

    def test_install_shortcuts_with_spaces_and_no_history_copy(self):
        with tempfile.TemporaryDirectory(prefix='Clipboard Float setup ') as tmp:
            base=Path(tmp);source=base/'Source Files';source.mkdir();self.fake_source(source)
            destination=base/'Installed App';desktop=base/'Desktop';startup=base/'Startup'
            with patch.object(setup_tool,'ROOT',source),patch.object(setup_tool,'check',return_value=object()):
                setup_tool.install(destination,desktop,startup,launch=False)
            self.assertTrue((destination/'runtime/pythonw.exe').is_file())
            self.assertFalse((destination/'application-errors.log').exists());self.assertFalse((destination/'clipboard-history.json').exists())
            self.assertEqual(json.loads((destination/'.clipboardfloat-install.json').read_text())['folder'],str(destination.resolve()))
            script="$s=New-Object -ComObject WScript.Shell; @($s.CreateShortcut($env:T_DESKTOP),$s.CreateShortcut($env:T_STARTUP)) | ForEach-Object { @{target=$_.TargetPath;args=$_.Arguments;working=$_.WorkingDirectory} } | ConvertTo-Json -Compress"
            env=os.environ.copy();env.update(T_DESKTOP=str(desktop/'Clipboard Float.lnk'),T_STARTUP=str(startup/'Clipboard History.lnk'))
            result=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],env=env,text=True))
            self.assertTrue(all(Path(x['target'])==destination/'runtime/pythonw.exe' and Path(x['working'])==destination for x in result))
            self.assertNotIn('--background',result[0]['args']);self.assertIn('--background',result[1]['args'])
            setup_tool.shortcuts(destination,desktop,startup,remove=True)
            self.assertFalse((desktop/'Clipboard Float.lnk').exists());self.assertFalse((startup/'Clipboard History.lnk').exists())

    def test_other_installation_shortcuts_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);desktop=root/'Desktop';startup=root/'Startup'
            setup_tool.shortcuts(root/'Other App',desktop,startup)
            setup_tool.shortcuts(root/'Our App',desktop,startup,remove=True)
            self.assertTrue((desktop/'Clipboard Float.lnk').exists());self.assertTrue((startup/'Clipboard History.lnk').exists())

    def test_uninstall_refuses_source_folder(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(setup_tool,'ROOT',Path(tmp)):
            with self.assertRaisesRegex(RuntimeError,'installed ClipboardFloat folder'):setup_tool.uninstall()

    def test_uninstall_requires_quitting_before_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'ClipboardFloat';root.mkdir();(root/'.clipboardfloat-install.json').write_text('{}')
            with patch.dict(os.environ,{'LOCALAPPDATA':tmp}),patch.object(setup_tool,'ROOT',root),patch.object(setup_tool,'running',return_value=True),patch.object(setup_tool,'shortcuts') as changes:
                with self.assertRaisesRegex(RuntimeError,'Quit'):setup_tool.uninstall()
                changes.assert_not_called();self.assertTrue(root.exists())

if __name__=='__main__':unittest.main()
