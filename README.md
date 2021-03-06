Desktopmagic overview
=====================
Desktopmagic can take screenshots (Windows-only for now) without
leaking memory in any type of error case (locked workstation, no
monitor attached, etc).

You may want this instead of PIL's ImageGrab because:

*	This takes a screenshot of all monitors.

*	PIL leaks memory if you try to take a screenshot when the
	workstation is locked (as of 2011-01).



Requirements
============
*	pywin32: http://sourceforge.net/projects/pywin32/files/pywin32/

*	If you want to use `getScreenAsImage` (and you probably do), you
	need PIL: http://www.pythonware.com/products/pil/



Installation
============
`python setup.py install`

This installs the module `desktopmagic` and the script `screengrab_torture_test`.



Sample use
==========
`desktopmagic.screengrab_win32.getScreenAsImage()` returns a PIL `Image` object
(mode RGB) of the current screen (all monitors).

You can save it to disk:

```
from desktopmagic.screengrab_win32 import getScreenAsImage

im = getScreenAsImage()
im.save('screencapture.png', format='png')
```

`desktopmagic.screengrab_win32.saveScreenToBmp(bmpFilename)` saves a screenshot
(all monitors) to a .bmp file.  This does not require PIL.  The .bmp file will
have the same bit-depth as the screen; it is not guaranteed to be 32-bit.
You'll get an probably-unreadable BMP if your screen depth is 256 colors.

See the source for more advanced/raw usage.



Wishlist
========
*	Support taking screenshots of just one monitor.

*	Support OS X

*	Support Linux

*	Write some tests



Contributing
============

Patches and pull requests are welcome.

This coding standard applies: http://ludios.org/coding-standard/
