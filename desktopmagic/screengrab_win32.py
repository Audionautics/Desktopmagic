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



class DIBFailed(Exception):
	pass



def _deleteDCAndBitMap(dc, bitmap):
	dc.DeleteDC()
	win32gui.DeleteObject(bitmap.GetHandle())


def getDCAndBitMap(saveBmpFilename=None, target_monitor=None, bbox=None):
	"""
	Returns a (DC, PyCBitmap).  On the returned PyCBitmap, you *must* call
	win32gui.DeleteObject(aPyCBitmap.GetHandle()).  On the returned DC,
	you *must* call aDC.DeleteDC()
	"""

	if target_monitor != None:
		# Get attached devices
		# Enum returns a list of tuples containing monitorHandle, DCHandle, screenRect 
		monitors = win32api.EnumDisplayMonitors(None, None)

		# Make sure the choice is valid. Instruct usage if not. 
		if target_monitor > len(monitors)-1:
			raise Exception('Monitor argument exceeds attached number of devices. There '+
							'are %d devices currently availble.\n'  % len(monitors) +
							'Please select appropriate device ( 0=Primary, 1=secondary, etc..)' + 
							' or leave param blank to capture entire virtual screen.')

		hwnd = monitors[target_monitor][1].handle
		left,top,right,bottom = monitors[target_monitor][2]
		width = right - left
		height = bottom
	
	elif bbox:
		hwnd = win32gui.GetDesktopWindow()

		# Unpack tuple
		left, top, width, height = bbox
		# make sure the coordinates aren't too big. 
		if (left < win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN) or 
			top < win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN) or 
			width > win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN) or
			height > win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)):
			raise Exception('Invalid bounding box. Range exceeds available screen area.')	

	else:
		hwnd = win32gui.GetDesktopWindow()

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

	ret = ctypes.windll.gdi32.GetDIBits(
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


def getScreenAsImage(target_monitor=None, bbox=None):
	"""
	Returns a PIL Image object (mode RGB) of the current screen (incl.
	all monitors).
	"""
	import Image
	dc, bitmap = getDCAndBitMap(target_monitor = target_monitor, bbox=bbox)
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


def saveScreenToBmp(bmpFilename, target_monitor=None, bbox=None):
	"""
	Save a screenshot (incl. all monitors) to a .bmp file.  Does not require PIL.
	The .bmp file will have the same bit-depth as the screen; it is not
	guaranteed to be 32-bit.
	"""
	dc, bitmap = getDCAndBitMap(saveBmpFilename=bmpFilename, target_monitor=target_monitor, bbox=bbox)
	_deleteDCAndBitMap(dc, bitmap)


def _demo():
	save_names = ['all_monitors', 'primary_monitor', 'secondary_monitor', 'bounding_test_1', 'bounding_test_2']
	monitor_params = [None, 0, 1, None, None]
	bbox_params = [None, None, None, (0,0,100,50), (400,300, 200,200)]


	for i in range(len(save_names)):
		saveScreenToBmp( save_names[i] + '.bmp', monitor_params[i], bbox_params[i] )
		im = getScreenAsImage( monitor_params[i], bbox_params[i] )
		im.save( save_names[i] + '.png', format='png' )


if __name__ == '__main__':
	_demo()