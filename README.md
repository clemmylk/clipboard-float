# Clipboard Float

A small Windows clipboard-history tool with a floating circular menu, smooth motion and keyboard paging. Inspired by [Filee](https://github.com/KnifeLemon/Filee), with its MIT-licensed geometry, springs and palette adaptations credited in `third_party/Filee`.

## Download and install

Download **Clipboard-Float-1.0.0-Windows-x64.zip** from this repository's **Releases**. Extract the entire ZIP and double-click **INSTALL.bat**.

Python and the required interface libraries are included. No separate Python installation, account, network access or administrator permission is needed for normal per-user setup. The source ZIP is for development and does not contain the runtime.

Setup creates a desktop shortcut, starts the tool and enables background startup after Windows sign-in. It installs into `%LOCALAPPDATA%\ClipboardFloat`; the extracted setup folder can be deleted after installation.

## Use it

| Action | Shortcut |
| --- | --- |
| Open the floating menu | Hold Tab and press V |
| Alternative opening shortcut | Ctrl + Alt + V |
| Next page while open | Tab, Page Down or scroll down |
| Previous page | Shift + Tab, Page Up or scroll up |
| Choose an item | Up / Down |
| Paste selected item | Enter or click the item |
| Copy without pasting | Ctrl + Enter or right-click the item |
| Paste a visible item directly | Alt + 1 through Alt + 6 |
| Hide the menu | Esc or click outside |

Type in the search box to filter text labels. Hover to preview. The three-dot menu and system-tray menu provide **Pause capture**, **Start with Windows**, **Clear history** and **Quit**.

Closing the popup keeps the background tool running. Choose Quit to stop it. History is cleared on exit or restart.

## Features

- Six visible clips per page, with wrapping keyboard paging.
- Text, image and copied-file clipboard formats.
- Smooth spring animation, antialiased painting and cached previews.
- Event-driven clipboard capture with a background reader.
- Duplicate clips move to the front. Up to 40 clips, with a 64 MB total memory cap and a 12 MB limit per clipboard format.
- Local, memory-only history. No accounts, cloud sync, telemetry or clipboard database.
- A per-user setup, desktop shortcut, automatic startup and uninstaller.

## Troubleshooting

- If Tab + V conflicts with another app, try **Ctrl + Alt + V** or click the tray icon.
- After a restart, check the tray and the **Start with Windows** menu option. The startup shortcut is named **Clipboard History**.
- To update an existing copy, choose **Quit** in the tray menu before running the new INSTALL.bat.
- If Windows or company policy blocks the unsigned tool, ask your IT team to review it. The installer does not disable Windows protections.
- Use **CHECK_SETUP.bat** to check the bundled runtime. Startup errors are written locally under `%LOCALAPPDATA%\ClipboardFloat\logs`.
- Windows can restrict pasting into an application running with higher privileges. You can copy the item and paste it manually there.

## Remove it

Choose **Quit** in the tray menu. Open `%LOCALAPPDATA%\ClipboardFloat` and run **UNINSTALL.bat**. It removes the app's startup shortcut, desktop shortcut and installed folder.

## Development

Use Windows x64 and Python 3.14. Create a virtual environment, install `requirements.txt`, then run `python clipboard_history.py`. Run `python -m unittest discover -v` for the UI geometry, paging, image-preview and installer tests. The Windows release includes Python 3.14 and PySide6/Qt 6.12.0.

Application source is under the MIT license. Filee portions retain their upstream MIT notice. Python, Qt/PySide6, Shiboken and other bundled dependencies keep their own licenses; see **THIRD_PARTY_NOTICES.md** and `third_party`.
