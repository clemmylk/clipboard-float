# Privacy

Clipboard Float keeps captured clips in memory. It does not save clipboard history to disk, send it to a server, collect telemetry or require an account. History is cleared when the application exits or Windows restarts.

The opening shortcut uses a Windows keyboard hook to recognise Tab + V. Keystrokes are not stored. Ctrl + Alt + V is also registered as a hotkey.

The clipboard reader supports the Windows `ExcludeClipboardContentFromMonitorProcessing` flag and a zero `CanIncludeInClipboardHistory` flag. Applications must set these flags for the exclusions to apply. Use Pause capture or Clear history when needed.

Setup creates local application files, a desktop shortcut and a startup shortcut. Error logs can contain local paths and diagnostics. No clipboard contents, local logs, screenshots or user-specific shortcuts are shipped in the public package.
