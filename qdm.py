from utils import *
from db import *
import sqlite3 as lite
import threading
import requests
import logging
import rfc6266
import shutil
import time
import sys
import os

from file import *
from utils import *
from widgets import *
import urllib.parse as parse


from multiprocessing import Pool


from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import Qt, QMimeData, pyqtSignal, QSize, QItemSelection, QThread, pyqtSlot

class UpdateThread(QThread):
	update_signal = pyqtSignal(Update)
	done_signal = pyqtSignal(int)

	def __init__(self, target, name=None):
		QThread.__init__(self)
		self.target = target
		self.name = name

	def __del__(self):
		self.wait()

	def run(self):
		self.target()


class Download:
	''' Handles the download of a single file '''

	def __init__(self, file, mainWidget=None):
		self.file = file
		self.mainWidget = mainWidget
		self.settings = mainWidget.settings
		self.client = self.getClient()


	def getClient(self):
		par = parse.urlparse(self.file.url)

		# Configure proxies
		proxies = http_proxies()


		if par.scheme == 'http' or par.scheme == 'https':
			return self.HTTPClient(self.file, self.mainWidget, proxies=proxies)
		elif par.scheme == 'magnet':
			return None 
		elif par.scheme == 'ftp':
			return None


	def start(self):
		self.client.start()


		
	class HTTPClient:

		def __init__ (self, file, mainWidget=None, chunk_size=8192*6, no_of_connections=10, is_daemon=True, proxies=None):
			self.file = file
			# self.file.name = self.file.name.replace(' ', '_')
			self.mainWidget = mainWidget

			self.no_of_connections = no_of_connections
			self.threads = []
			self.thread_lock = threading.Lock()
			self.stopper = False

			self.session_download_size = 0
			self.total_download_size = 0
			self.chunk_size = chunk_size
			self.proxies = proxies

			self.settings = QSettings('ndersam', 'qdm')
			self.tmpdir =  self.settings.value('temp_download_dir')+ '/' + self.file.name
			self.speed = ''
			self.start_time = 0

			self.configure()

		

		def configure(self):
			''' Determines how to download the file (multipart or single chunked transfer) '''
			size_on_disk = self.check_if_file_exists(self.file.path + '/' + self.file.name)
			if size_on_disk is not 0 and size_on_disk == self.file.name:
				return

			update_handler = None

			if self.file.size == 0:
				self.no_of_connections = 1 
				t = threading.Thread(target=self.monopart_download_handler, daemon=True)
				self.threads.append(t)
				update_handler = self.update_handler_mono
			else:
				self.min_part_size = self.file.size // self.no_of_connections
				for i in range(self.no_of_connections):
					part_size = self.min_part_size
					name = '%5d' % (i + 1)
					# add leftover chunk for last thread
					if i + 1 == self.no_of_connections:
						part_size += self.file.size % self.no_of_connections
					t = threading.Thread(name=name, target=self.multipart_download_handler,
						args=(i+1, i * self.min_part_size, part_size), daemon=True)
					self.threads.append(t)
				update_handler = self.multipart_update_handler

			# Add update thread
			name = '%10s' % 'update'
			t_update = UpdateThread(name=name, target=update_handler)
			t_update.update_signal.connect(self.mainWidget.updateProgress)
			self.threads.append(t_update)


			# Add clean up thread
			t_update.done_signal.connect(self.cleanup_handler)

			# Create tmp dir
			self.tmpdir = self.tmpdir.replace(' ', '_')
			if not os.path.exists(self.tmpdir):
				os.makedirs(self.tmpdir)

			# Create output directory
			if not os.path.exists(self.file.path):
				os.makedirs(self.file.path)


		def check_if_file_exists(self, filename):
			try:
				size = os.path.getsize(filename)
			except:
				size = 0
			return size


		@pyqtSlot(int)
		def cleanup_handler(self):
			# print('In cleanup_handler')
			if self.total_download_size == self.file.size:
				t = threading.Thread(target=self.__cleanup_handler__, daemon=True)
				t.start()


		def __cleanup_handler__(self):
			# print('I called mini handler')
			# Save downloaded file
			append_files(self.tmpdir, self.file.name, self.file.path)
			# clean up
			shutil.rmtree(self.tmpdir)



		def multipart_download_handler(self, thread_no, start_byte, part_size):
			tmpfile = self.tmpdir + '/' + '{}'.format(thread_no) + '.part'
			
			# determine range of bytes
			end_byte = start_byte + part_size
			try:
				part_size_on_disk = os.path.getsize(tmpfile)
				with self.thread_lock:
					self.total_download_size += part_size_on_disk
			except Exception as e:
				part_size_on_disk = 0

			# exit if part has been downloaded
			if not part_size_on_disk < part_size:
				return 

			# adjust start_byte index
			start_byte += part_size_on_disk
			headers = {'Range':'bytes=%d-%d' % (start_byte, end_byte - 1), 'User-Agent': get_random_user_agent()}

			try:
				r = requests_retry_session().get(self.file.url, headers=headers, stream=True, proxies=self.proxies)
				r.raise_for_status()

				append_write = 'wb'
				if os.path.exists(tmpfile):
					append_write = 'ab'
				else:
					append_write =  'wb'

				with open(tmpfile, append_write) as f:
					for chunk in r.iter_content(self.chunk_size):
						f.write(chunk)
						# Update download size
						with self.thread_lock:
							self.total_download_size += len(chunk)
							self.session_download_size += len(chunk)
							# kill thread on pause
							if self.stopper:
								QThread.currentThread().quit()
							if getWidgetByObjectName('%d_status' % self.file.getId()).pause():
								return
			except Exception as e:
				raise e


		def monopart_download_handler(self):
			try:
				headers = {'User-Agent': get_random_user_agent()}
				r = requests_retry_session().get(self.file.url, headers=headers, stream=True, proxies=self.proxies)
				with open(self.file.path + '/' + self.file.name, 'wb') as f:
					for chunk in r.iter_content():
						if chunk:
							f.write(chunk)
							self.session_download_size += len(chunk)
							self.total_download_size += len(chunk)
			except Exception as e:
				raise e

		def update_handler(self):
			progress = 0
			s = 0
			while self.total_download_size < self.file.size:
				with self.thread_lock:
					progress = float(self.total_download_size * 100) / self.file.size
					# calculate avg speed
					if time.clock() - self.start_time:
						s = float(self.session_download_size) / (time.clock() - self.start_time)
						self.speed = format_speed(s)
					# kill thread on pause
					if getWidgetByObjectName('%d_status' % self.file.getId()).pause():
						package = '%d_paused %f' % (self.file.getId(), progress)
						QThread.currentThread().update_signal.emit(package)
						return
				package = '%d_status %f' % (self.file.getId(), progress)
				QThread.currentThread().update_signal.emit(package)
				QThread.currentThread().sleep(1)
				package = '%d_speed %s' % (self.file.getId(), self.speed)
				QThread.currentThread().update_signal.emit(package)

			# 100% update		
			progress = 100
			package = '%d_status %f' % (self.file.getId(), progress)
			QThread.currentThread().update_signal.emit(package)

			# Clear 'speed' column
			package = '%d_speed %s' % (self.file.getId(), '')
			QThread.currentThread().update_signal.emit(package)

			# Emit done_signal for post-download processes
			QThread.currentThread().done_signal.emit(self.file.getId())


		def multipart_update_handler(self):
			''' sends download progress for ui update ... '''

			# download details
			id_ = self.file.getId()
			pbar = '%d_status' % id_
			speed_col = '%d_speed' % id_
			priority_col = '%d_priority' % id_
			eta_col = '%d_eta' % id_

			####### [1] Send download update while download is less than 100%
			while self.total_download_size < self.file.size:
				progress = 0
				with self.thread_lock:
					# calculate % progress
					progress = float(self.total_download_size * 100) / self.file.size
					# calculate avg speed
					if time.clock() - self.start_time:
						s = float(self.session_download_size) / (time.clock() - self.start_time)
						self.speed = format_speed(s)

					if self.stopper:
						# print('Oi I heard it')
						QThread.currentThread().quit()

					# kill thread if download has been paused
					if getWidgetByObjectName(pbar).pause():
						package = Update(id_, pbar, Update.WIDGET, progress, Update.PAUSE) # add extra 'pause' instruction
						QThread.currentThread().update_signal.emit(package)
						return

				# Update Download Progress
				package = Update(id_, pbar, Update.WIDGET, progress)
				QThread.currentThread().update_signal.emit(package)
				
				# Update Download Speed
				package = Update(id_, speed_col, Update.TABLE_ITEM, self.speed)
				QThread.currentThread().update_signal.emit(package)

				# update eta
				eta = float('inf') if s == 0 else (self.file.size - self.total_download_size)/s
				eta_str = format_time(eta)
				package = Update(id_, eta_col, Update.TABLE_ITEM, eta_str )
				QThread.currentThread().update_signal.emit(package)

				QThread.currentThread().sleep(1)

			###### [2] Tidy up @100%

			# Update Download Progress: 100% update		
			package = Update(id_, pbar, Update.WIDGET, 100, Update.COMPLETE)
			QThread.currentThread().update_signal.emit(package)

			# Update Download Speed: clear 'speed' column
			package = Update(id_, speed_col, Update.TABLE_ITEM, '')
			QThread.currentThread().update_signal.emit(package)

			package = Update(id_, eta_col, Update.TABLE_ITEM, '')
			QThread.currentThread().update_signal.emit(package)

			# Emit done_signal for post-download processes
			QThread.currentThread().done_signal.emit(id_)


		def update_handler_mono(self):
			progress = 0
			s = 0
			while self.threads[0].is_alive():
				with self.thread_lock:
					progress = 99.9
					# calculate avg speed
					if time.clock() - self.start_time:
						s = float(self.session_download_size) / (time.clock() - self.start_time)
						self.speed = format_speed(s)
					# kill thread on pause
					if getWidgetByObjectName('%d_status' % self.file.getId()).pause():
						return
				# update download progress
				package = '%d_status %f' % (self.file.getId(), progress)
				QThread.currentThread().update_signal.emit(package)
				
				# update speed
				package = '%d_speed %s' % (self.file.getId(), self.speed)
				QThread.currentThread().update_signal.emit(package)

				# update eta
				eta = float('inf') if s == 0 else (self.file.size - self.total_download_size)/s
				eta_str = format_time(eta)
				package = '%d_eta %s' % (self.file.getId(), eta_str)
				QThread.currentThread().update_signal.emit(package)

				#### delay 
				QThread.currentThread().sleep(1)

			# 100% update		
			progress = 100
			package = '%d_status %f' % (self.file.getId(), progress)
			QThread.currentThread().update_signal.emit(package)

			# Clear 'speed' column
			package = '%d_speed %s' % (self.file.getId(), '')
			QThread.currentThread().update_signal.emit(package)

			# Update 'size'
			package = '%d_size %d' % (self.file.getId(), self.total_download_size)
			QThread.currentThread().update_signal.emit(package)


		def start(self):
			self.start_time = time.clock()
			for t in self.threads:
				t.start()

		@pyqtSlot()
		def stop(self):
			self.stopper = True