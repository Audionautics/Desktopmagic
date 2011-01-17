"""
Robust functions for grabbing and saving screenshots on Windows.
"""

# TODO: support capture of individual displays (and at the same time with a "single screenshot")
# Use GetDeviceCaps; see http://msdn.microsoft.com/en-us/library/dd144877%28v=vs.85%29.aspx

import ctypes
import win32gui
import win32ui
import win32con
import win32api


class BITMAPINFOHEADER(ctypes.Structure):
	_fields_ = [
		('biSize', ctypes.c_uint32),
		('biWidth', ctypes.c_int),
		('biHeight', ctypes.c_int),
		('biPlanes', ctypes.c_short),
		('biBitCount', ctypes.c_short),
		('biCompression', ctypes.c_uint32),
		('biSizeImage', ctypes.c_uint32),
		('biXPelsPerMeter', ctypes.c_long),
		('biYPelsPerMeter', ctypes.c_long),
		('biClrUsed', ctypes.c_uint32),
		('biClrImportant', ctypes.c_uint32)
	]



class BITMAPINFO(ctypes.Structure):
	_fields_ = [
		('bmiHeader', BITMAPINFOHEADER),
		('bmiColors', ctypes.c_ulong * 3)
	]



class GrabFailed(Exception):
	"""
	Could not take a screenshot.
	"""



def _deleteDCAndBitMap(dc, bitmap):
	dc.DeleteDC()
	win32gui.DeleteObject(bitmap.GetHandle())


def getDCAndBitMap(saveBmpFilename=None):
	"""
	Returns a (DC, PyCBitmap).  On the returned PyCBitmap, you *must* call
	win32gui.DeleteObject(aPyCBitmap.GetHandle()).  On the returned DC,
	you *must* call aDC.DeleteDC()
	"""
	hwndDesktop = win32gui.GetDesktopWindow()

	# Get complete virtual screen, including all monitors.
	left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
	top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
	width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
	height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
	##print "L", left, "T", top, "dim:", width, "x", height

	# Retrieve the device context (DC) for the entire window.
	hwndDevice = win32gui.GetWindowDC(hwndDesktop)
	##print "device", hwndDevice
	assert isinstance(hwndDevice, (int, long)), hwndDevice

	mfcDC  = win32ui.CreateDCFromHandle(hwndDevice)
	try:
		saveDC = mfcDC.CreateCompatibleDC()
		saveBitMap = win32ui.CreateBitmap()
		# Above line is assumed to never raise an exception.
		try:
			saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
			saveDC.SelectObject(saveBitMap)
			try:
				saveDC.BitBlt((0, 0), (width, height), mfcDC, (left, top), win32con.SRCCOPY)
			except win32ui.error, e:
				raise GrabFailed("Error during BitBlt.  "
					"Workstation might be locked.  Error was: " + str(e))
			if saveBmpFilename is not None:
				saveBitMap.SaveBitmapFile(saveDC, saveBmpFilename)
		except:
			_deleteDCAndBitMap(saveDC, saveBitMap)
			# Let's just hope the above line doesn't raise an exception
			# (or it will mask the previous exception)
			raise
	finally:
		mfcDC.DeleteDC()

	return saveDC, saveBitMap


def getScreenDIB(dc, bitmap):
	"""
	Returns a (raw BGR str, (width, height)) for C{dc}, C{bitmap}.
	Guaranteed to be 32-bit.  Note that the origin of the returned image is
	in the bottom-left corner, and the image has 32-bit line padding.
	"""
	bmpInfo = bitmap.GetInfo()
	width, height = bmpInfo['bmWidth'], bmpInfo['bmHeight']

	bmi = BITMAPINFO()
	ctypes.memset(ctypes.byref(bmi), 0x00, ctypes.sizeof(bmi))
	bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
	bmi.bmiHeader.biWidth = width
	bmi.bmiHeader.biHeight = height
	bmi.bmiHeader.biBitCount = 24
	bmi.bmiHeader.biPlanes = 1

	bufferLen = height * ((width * 3 + 3) & -4)
	pbBits = ctypes.create_string_buffer(bufferLen)

	ret = ctypes.windll.gdi32.GetDIBits(
		dc.GetHandleAttrib(),
		bitmap.GetHandle(),
		0,
		height,
		ctypes.byref(pbBits),
		ctypes.pointer(bmi),
		win32con.DIB_RGB_COLORS)
	if ret == 0:
		raise GrabFailed("Return code %r from GetDIBits" % (ret,))

	assert len(pbBits.raw) == bufferLen, len(pbBits.raw)

	return pbBits.raw, (width, height)


def getScreenAsImage():
	"""
	Returns a PIL Image object (mode RGB) of the current screen (incl.
	all monitors).
	"""
	import Image

	dc, bitmap = getDCAndBitMap()
	try:
		bmpInfo = bitmap.GetInfo()
		# bmpInfo is something like {
		# 	'bmType': 0, 'bmWidthBytes': 5120, 'bmHeight': 1024,
		# 	'bmBitsPixel': 32, 'bmPlanes': 1, 'bmWidth': 1280}
		##print bmpInfo
		size = (bmpInfo['bmWidth'], bmpInfo['bmHeight'])

		if bmpInfo['bmBitsPixel'] == 32:
			data = bitmap.GetBitmapBits(True) # asString = True
			return Image.frombuffer(
				'RGB', size, data, 'raw', 'BGRX', 0, 1)
		else:
			# If bpp != 32, we cannot use bitmap.GetBitmapBits,
			# because it does not convert 8-bit or 16-bit bitmaps to
			# the 32-bit format we need.
			data, size = getScreenDIB(dc, bitmap)
			# BGR, 32-bit line padding, origo in lower left corner
			return Image.frombuffer(
				'RGB', size, data, 'raw', 'BGR', (size[0] * 3 + 3) & -4, -1)
	finally:
		_deleteDCAndBitMap(dc, bitmap)


def saveScreenToBmp(bmpFilename):
	"""
	Save a screenshot (incl. all monitors) to a .bmp file.  Does not require PIL.
	The .bmp file will have the same bit-depth as the screen; it is not
	guaranteed to be 32-bit.
	"""
	dc, bitmap = getDCAndBitMap(saveBmpFilename=bmpFilename)
	_deleteDCAndBitMap(dc, bitmap)


def _demo():
	saveScreenToBmp('screencapture.bmp')
	im = getScreenAsImage()
	im.save('screencapture.png', format='png')


if __name__ == '__main__':
	_demo()
