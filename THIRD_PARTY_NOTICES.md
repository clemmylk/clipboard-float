# Third-party notices

## Filee

The polar geometry, spring stepping and palette adaptations use resources from Filee by Myeonggu Kim (KnifeLemon) and contributors, under MIT. Retained references and the complete notice are in `third_party/Filee`. Upstream: https://github.com/KnifeLemon/Filee . This is an independent clipboard utility, not an official Filee release.

## Python

The Windows package includes unmodified Python 3.14 runtime files. Python's license is included in `runtime/LICENSE.txt` and `third_party/Python/LICENSE.txt`. Source and release information: https://www.python.org/downloads/source/ .

## Qt for Python, Qt and Shiboken

The Windows package dynamically loads unmodified PySide6 Essentials 6.12.0, Shiboken6 6.12.0 and the required Qt libraries. They are not covered by this application's MIT license. The supplied package metadata declares LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only licensing. This distribution uses the LGPLv3 option for the linked libraries.

The corresponding upstream Qt license texts, including LGPLv3 and GPLv3, are in `third_party/Qt`; the installed wheel metadata and notices are retained under `runtime/Lib/site-packages`. Qt/PySide6 dependencies remain separate shared-library files and can be replaced with compatible modified builds. The application source needed to run against them is supplied separately in the Source ZIP.

Upstream code and build instructions:

- PySide6/Shiboken: https://code.qt.io/cgit/pyside/pyside-setup.git/ (release v6.12.0)
- Qt base: https://code.qt.io/cgit/qt/qtbase.git/ (release v6.12.0)
- Qt for Python documentation: https://doc.qt.io/qtforpython-6/
- Qt licensing and third-party attribution: https://doc.qt.io/qt-6/licensing.html

Unused Qt modules and development utilities are omitted from the portable runtime. The included upstream libraries themselves have not been modified. Microsoft runtime components retain their upstream redistribution terms.
