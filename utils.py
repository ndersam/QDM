import threading
import math
import re
import os

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import Qt, QMimeData, pyqtSignal, QSize, QItemSelection, QThread, QSettings

import requests,time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from fake_useragent import UserAgent
import rfc6266


from file import *


'''
Module contains the following 

## Classes
1. InvalidProtocolException
2. ExtractInfoThread


##functions

 1. extract_filename
 2. read_in_chunks
 3. append_files
 4. get_random_user_agent
 5. requests_retry_session
 6. get_fileprotocol
 7. extract_downloadinfo
 8. validate_uri
 9. check_if_file_exists
10. format_size
11. format_speed
12. getWidgetByObjectName
13. extract_basename
14. format_name
15. format_string
16. http_proxies
17. format_time
'''

class InvalidProtocolException(Exception):
	"""Raised when an invalid URI is passed in"""
	pass


def extract_filename(url):
		'''
		Extracts filename from download url
		'''
		name = url[url.rfind("/")+1:] # substr from the char after the last '/' to the end

		content_type = requests.head(url).headers['Content-type'] 
		ext = content_type[content_type.rfind('/')+1:]
		if ext == "":
			ext = content_type

		# if file extension doesn't exist in the filename, add it
		if name[name.rfind('.') + 1:] == ext: 
			return name
		else:
			return name + "." + ext


def read_in_chunks(file_object, chunk_size=1024):
	''' 
	Lazy function (generator) to read a file piece by piece. Default chunk size: 1kB 

	Usage:
	------
	f = open('really_big_file.dat')
	for piece in read_in_chunks(f):
		process_data(piece)


	Another option would be to use iter and a helper function:

	f = open('really_big_file.dat')
	def read1k():
	    return f.read(1024)

	for piece in iter(read1k, ''):
	    process_data(piece)

	If the file is line-based, the file object is already a lazy generator of lines:

	for line in open('really_big_file.dat'):
	    process_data(line)
	'''
	while True:
		data = file_object.read(chunk_size)
		if not data:
			break
		yield data



def append_files(tempfiles_dir, filename, filepath):
	'''
	
	@param: tempfiles_dir  -> directory of list of temporary files
	@param: filename -> filename for resulting larger file
	@param: filepath -> directory for saving resulting larger file
	'''

	# files in temp directory are like: 1.part, 10.part, 11.part, 2.part, ... 9.part
	# create sorted list tempFiles in order: 1.part, ..., 9.part, 10.part, 11.part

	ls = os.listdir(tempfiles_dir)
	tempFiles = ['{}.part'.format(idx) for idx in range(1, len(ls) + 1)]

	with open(filepath + '/' + filename, "wb") as f:
		for file in tempFiles:
			with open(tempfiles_dir + '/' + file, "rb") as tempFile:
				for piece in read_in_chunks(tempFile):
					f.write(piece)



def get_random_user_agent():
	return UserAgent().random



def requests_retry_session( retries=4, backoff_factor=0.3, status_forcelist=(500, 502, 504), session=None):
	session = session or requests.Session()
	retry = Retry(
		total=retries,
    	read=retries,
    	connect=retries,
    	backoff_factor=backoff_factor,
    	status_forcelist=status_forcelist,
    	)
	adapter = HTTPAdapter(max_retries=retry)
	session.mount('http://', adapter)
	session.mount('https://', adapter)
	return session



		
def get_fileprotocol(word):
	pattern = re.compile(r'^(\w+)://')
	magnet_uri_pattern = re.compile(r'^(magnet):\?')
	match = re.search(pattern, word) or re.search(magnet_uri_pattern, word)
	if match:
		return match.group(1)
	else:
		raise InvalidProtocolException('Invalid URL or Magnet')


def extract_downloadinfo(url):
	''' Extracts from information from url '''
	protocol = get_fileprotocol(url)

	if protocol == 'http' or protocol == 'https':
		file = File()
		try:
			r = requests_retry_session().get(url, stream=True)
			r.raise_for_status()
			name =rfc6266.parse_requests_response(r).filename_unsafe
			file.name = name
			file.url = url
			try:
				file.size = int(r.headers['Content-Length'])
			except:
				file.size = 0
				file.setResume(0)
			return file
		except Exception as e:
			print(e.args[0])
			return file
	else:
		print(protocol, 'not supported yet!')
		return None



class ExtractInfoThread(QThread):
	done_ = pyqtSignal(File)

	def __init__(self, url, name=None):
		QThread.__init__(self)
		self.url = url
		self.name = name

	def __del__(self):
		self.wait()

	def run(self):
		file = self.extract_downloadinfo()
		self.done_.emit(file)
		
	def extract_downloadinfo(self):
		''' Extracts from information from url '''
		protocol = get_fileprotocol(self.url)
		if protocol == 'http' or protocol == 'https':
			file = File()
			try:
				proxies = http_proxies()
				r = requests_retry_session().get(self.url, stream=True, proxies=proxies)
				r.raise_for_status()
				name =rfc6266.parse_requests_response(r).filename_unsafe
				file.name = name
				file.url = self.url
				try:
					file.size = int(r.headers['Content-Length'])
				except:
					file.size = 0
					file.setResume(0)
				return file
			except Exception as e:
				print(e.args[0])
				return file
		else:
			print(protocol, 'not supported yet!')
			return None


def validate_uri(uri):
	''' checks if uri passed in is valid '''

	# Check if its a url
	regex = re.compile(
    r'^(?:http|ftp)s?://' # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
    r'localhost|' #localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
    r'(?::\d+)?' # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)

	match = re.match(regex, uri)
	if match:
		url = match.group()
		return True

	# check if its a valid path
	try:
		size = os.path.exists(uri)
		if size > 0:
			return True
	except:
		return False



def check_if_file_exists(filename):
	try:
		size = os.path.exists(filename)
		return size
	except Exception as e:
		size = 0
		return size


def format_size(size):
	''' converts size (in bytes) to human friendly string '''
	if size == 0:
		return ''
	log = int(math.log(size, 1024))
	size_str = ''
	if log == 0:
		size_str = '%d bytes' % size
	elif log == 1:
		size_str = '%.2f KB' % (size / 1024 ** log)
	elif log == 2:
		size_str = '%.2f MB' % (size / 1024 ** log)
	elif log == 3:
		size_str = '%.2f GB' % (size / 1024 ** log)
	return size_str


def format_speed(speed):
	''' converts speed (in bytes/sec) to human friendly string '''
	if speed == 0:
		return '0 bytes/s'
	log = int(math.log(speed, 1024))
	size_str = ''
	if log == 0:
		size_str = '%d bytes/s' % speed
	elif log == 1:
		size_str = '%.2f KB/s' % (speed / 1024 ** log)
	elif log == 2:
		size_str = '%.2f MB/s' % (speed / 1024 ** log)
	elif log == 3:
		size_str = '%.2f GB/s' % (speed / 1024 ** log)
	return size_str


def getWidgetByObjectName(name):
	try:
		widgets = QApplication.instance().topLevelWidgets()
		widgets = widgets + QApplication.instance().allWidgets()
		for x in widgets:
			if str(x.objectName()) == name:
				return x
	except Exception as e:
		print(e.args[0])
		import sys
		sys.exit(0)


def extract_basename(fullname):
	''' extracts and returns the basename of a file without extension ''' 
	basename = os.path.splitext(fullname)[0] # separates filename and extension
	basename = os.path.basename(basename) # returns basename from path
	return basename


def format_name(filename):
	''' resizes the length of filename for display '''
	if len(filename) > 54:
		name, ext = os.path.splitext(filename)
		name = filename[:49] + '...'
		return name + ext 
	return filename


def format_string(string, length):
	#
	if len(string) > length:
		return string[0:length-3] + '...'
	return string


def http_proxies():
	proxies = None
	settings = QSettings('ndersam', 'qdm')
	proxy_choice = settings.value('proxy/choice')

	if proxy_choice == 'none':
		p = settings.value('proxy/config/none')
		http = p['HTTP']
		https = p['HTTPS']
		proxies = {
			'http': http['Address'] + ':' + str(http['Port']),
			'https': https['Address'] + ':' + str(https['Port']),
			}
	elif proxy_choice == 'manual':
		p = settings.value('proxy/config/manual')
		http = p['HTTP']
		https = p['HTTPS']
		proxies = { 
			'http': http['Address'] + ':' + str(http['Port']),
			'https': https['Address'] + ':' + str(https['Port']),
			}

	return proxies


def format_time(seconds):

	if seconds == float('inf'):
		return u'\u221E'
 
	seconds = int(seconds)
	
	# withing a minute
	if seconds < 60:
		return '%d sec' % seconds

	# within an hour
	elif seconds < 3600:
		min_ = seconds // 60
		secs = seconds % 60
		return '%d min %d sec' % (min_, secs)

	# within a day
	elif seconds < 24*3600:
		hour = seconds // 3600 
		min_ = (seconds % 3600) // 60
		return '%d h %d min' % (hour, min_)
	
	# more than a day (but withing a year)
	elif seconds < 365*24*3600:
		day = seconds // (24 * 3600)
		hour = (seconds % (24 * 3600)) // (3600)
		return '%d day %d h' % (day, hour)
	else:
		return u'\u221E'