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
import os, sys

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

class BoundingBoxOutOfRange(Exception):
	'''
	Coordinates are too large for the current resolution
	'''


class DIBFailed(Exception):
	pass



def _deleteDCAndBitMap(dc, bitmap):
	dc.DeleteDC()
	win32gui.DeleteObject(bitmap.GetHandle())

def getMonitorInfo():
	'''
	Enumerates the available monitor. Return the 
	Screen Dimensions of the selected monitor. 
	'''
	H_MONITOR = 0
	HDC_MONITOR = 1
	SCREEN_RECT = 2

	try:
		monitors = win32api.EnumDisplayMonitors(None, None)
	finally:
		[monitors[i][HDC_MONITOR].Close() for i in range(len(monitors))]

	return [monitorAttribs[SCREEN_RECT] for monitorAttribs in monitors]


def getDCAndBitMap(saveBmpFilename=None, bbox=None):
	"""
	Returns a (DC, PyCBitmap).  On the returned PyCBitmap, you *must* call
	win32gui.DeleteObject(aPyCBitmap.GetHandle()).  On the returned DC,
	you *must* call aDC.DeleteDC()
	"""
	hwnd = win32gui.GetDesktopWindow()
	if bbox:
		left, top, width, height = bbox
		if (left < win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN) or 
			top < win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN) or 
			width > win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN) or
			height > win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)):
			raise Exception('Invalid bounding box. Range exceeds \
						available screen area.')	
	else:
		# Get complete virtual screen, including all monitors.
		left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
		top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
		width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
		height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
		##print "L", left, "T", top, "dim:", width, "x", height

		# Retrieve the device context (DC) for the entire window.
	
	hwndDevice = win32gui.GetWindowDC(hwnd)
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
				raise GrabFailed("Error during BitBlt. "
					"Possible reasons: locked workstation, no display, "
					"or an active UAC elevation screen. Error was: " + str(e))
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


def getBGR32(dc, bitmap):
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

	ret = ctypes.windll.gdi32.GetDIBgetits(
		dc.GetHandleAttrib(),
		bitmap.GetHandle(),
		0,
		height,
		ctypes.byref(pbBits),
		ctypes.pointer(bmi),
		win32con.DIB_RGB_COLORS)
	if ret == 0:
		raise DIBFailed("Return code 0 from GetDIBits")

	assert len(pbBits.raw) == bufferLen, len(pbBits.raw)

	return pbBits.raw, (width, height)


def getScreenAsImage(bbox=None):
	"""
	Returns a PIL Image object (mode RGB) of the current screen (incl.
	all monitors).

	bbox =  boundingBox. Used to snap a subarea of the screen. 
	A tuple of (x, y, width, height). 
	"""
	import Image
	dc, bitmap = getDCAndBitMap(bbox=bbox)
	try:
		bmpInfo = bitmap.GetInfo()
		# bmpInfo is something like {
		# 	'bmType': 0, 'bmWidthBytes': 5120, 'bmHeight': 1024,
		# 	'bmBitsPixel': 32, 'bmPlanes': 1, 'bmWidth': 1280}
		##print bmpInfo
		size = (bmpInfo['bmWidth'], bmpInfo['bmHeight'])

		if bmpInfo['bmBitsPixel'] == 32:
			# Use GetBitmapBits and BGRX if the bpp == 32, because
			# it's ~15% faster than the method below.
			data = bitmap.GetBitmapBits(True) # asString=True
			return Image.frombuffer(
				'RGB', size, data, 'raw', 'BGRX', 0, 1)
		else:
			# If bpp != 32, we cannot use GetBitmapBits, because it
			# does not return a 24/32-bit image when the screen is at
			# a lower color depth.
			try:
				data, size = getBGR32(dc, bitmap)
			except DIBFailed, e:
				raise GrabFailed("getBGR32 failed. Error was " + str(e))
			# BGR, 32-bit line padding, origo in lower left corner
			return Image.frombuffer(
				'RGB', size, data, 'raw', 'BGR', (size[0] * 3 + 3) & -4, -1)
	finally:
		_deleteDCAndBitMap(dc, bitmap)


def saveScreenToBmp(bmpFilename, bbox=None):
	"""
	Save a screenshot (incl. all monitors) to a .bmp file.  Does not require PIL.
	The .bmp file will have the same bit-depth as the screen; it is not
	guaranteed to be 32-bit.

	bbox = boundingBox. Used to snap a subarea of the screen. 
	A tuple of (x, y, width, height). 
	"""
	dc, bitmap = getDCAndBitMap(saveBmpFilename=bmpFilename, bbox=bbox)
	_deleteDCAndBitMap(dc, bitmap)

def buildAndSetDemoDir():
	'''
	_demo now generates a lot of files. 
	This generates a dir to store the images. 
	'''
	try:
		os.mkdir('demo')
		os.path.join(os.getcwd(), 'demo')
	except OSError:
		pass #already exists
	return 'demo'


def _demo():
	dirPath = buildAndSetDemoDir()

	monitors = getMonitorInfo()
	saveNames = ['allMonitors','boundingTestOne', 'boundingTestTwo']
	params = [None, (0,0,100,50), (400,300, 200,200)]
	
	for i in range(len(monitors)):
		saveNames.append('Monitor' + str(i + 1))
		params.append(monitors[i])

	for i in range(len(saveNames)):
		savePath = os.path.join(dirPath, saveNames[i]) 
		
		saveScreenToBmp(savePath + '.bmp', params[i])
		
		im = getScreenAsImage(params[i])
		im.save(savePath + '.png', format='png' )

	while True:
		getMonitorInfo()


if __name__ == '__main__':
	_demo()