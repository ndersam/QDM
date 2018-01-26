import os

if os.name == 'nt':
	import ctypes
	from ctypes import windll, wintypes
	from uuid import UUID

	# ctypes GUID copied from MSDN sample code
	class GUID(ctypes.Structure):
		_fields_ = [ ('Data1', wintypes.DWORD), ('Data2', wintypes.WORD), ('Data3', wintypes.WORD), ('Data4', wintypes.BYTE * 8)]

		def __init__(self, uuidstr):
			uuid = UUID(uuidstr)
			ctypes.Structure.__init__(self)
			self.Data1, self.Data2, self.Data3, self.Data4[0], self.Data4[1], rest = uuid.fields
			for i in range(2, 8):
				self.Data4[i] = rest>>(8-i-1)*8 & 0xff

	SHGetKnownFolderPath = windll.shell32.SHGetKnownFolderPath
	SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]


	def _get_known_folder_path(uuidstr):
		pathptr = ctypes.c_wchar_p()
		guid = GUID(uuidstr)
		if SHGetKnownFolderPath(ctypes.byref(guid), 0, 0, ctypes.byref(pathptr)):
			raise ctypes.WinError()
		path = pathptr.value.replace('\\', '/')
		return path

	# TO-DO add more folders
	FOLDERID_localappdata = '{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}'
	FOLDERID_download = '{374DE290-123F-4565-9164-39C4925E467B}'


	def get_download_folder():
		return _get_known_folder_path(FOLDERID_download)

	def get_localAppData_folder():
		return _get_known_folder_path(FOLDERID_localappdata)
else:
	pass
	# def get_download_folder():
	# 	home = os.path.expanduser('~')
	# 	return os.path.join(home, 'Downloads')

	# def get_localAppData_folder():
	# 	home = os.path.expanduser('~')
	# 	return os.path.join(home, 'LocalAppData')