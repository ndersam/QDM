from time import strftime, localtime
import time
import threading
import queue
import struct
import ctypes
import sys

from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPixmap, QPalette, QIcon
from PyQt5.QtCore import Qt, QMimeData, pyqtSignal, QSize, QRect, pyqtSlot, QSettings


from paths import get_download_folder, get_localAppData_folder
from initialize_settings import default_settings
from widgets import *
from db import *
from qdm import *
from file import *
from settings import *
from utils import *


myappid = 'ndersam.qdm.0.4'



class Application(QWidget):

	download_started = pyqtSignal(File) # emitted when a download has just been added to the queue
	download_paused = pyqtSignal(int) # emitted when a download has been paused
	download_completed = pyqtSignal(int) # emitted when a download has been completed
	

	def __init__(self, que=None):
		super().__init__()
		
		# App settings
		self.settings = QSettings('ndersam', 'qdm')
		default_settings() # create default settings if settings don't exist
		
		self.tmp_download_dir = self.settings.value('temp_download_dir')
		self.queue_size = self.settings.value('queue_size')

		# dasdas
		self.lst_incomplete_downloads = [] # list of IDs of current downloads
		self.queue = que
		self.bool_exit = False

		self.database = DownloadDatabase()
		self.initUI()
		self.load_data()
				
		self.download_started.connect(self.onAddDownload)
		self.download_completed.connect(self.onCompleteDownload)
		self.download_paused.connect(self.onPauseDownload)

		# show app in System Tray
		if QSystemTrayIcon.isSystemTrayAvailable():
			self.trayIcon = Tray(icon=QIcon('./imgs/pause2.png'),parent=self)
			self.trayIcon.activated.connect(self.onSystemTrayActivated)
			self.trayIcon.show()

		## Keyboard Shortcuts
		shortcut_add = QShortcut(QKeySequence('Ctrl+A'), self)
		shortcut_add.activated.connect(self.add_download)
		# shortcut_del = QShortcut(QKeySequence('Del'), self)
		# shortcut_open= QShortcut(QKeySequence('Del'), self)
		# shortcut_pause = QShortcut(QKeySequence('Del'), self)


			
	def changeEvent(self, event):

		# handle the 'Minimize button' event
		if event.type() == QEvent.WindowStateChange:
			if self.windowState() & Qt.WindowMinimized:
				if self.settings.value('minimize_button_minimizes'):
					event.ignore()
					self.hide()
				else:
					event.accept()

		

	def onSystemTrayActivated(self, reason):
		''' Restore QDM (if minimized) when the system tray icon is 'triggered' or clicked '''
		if reason == QSystemTrayIcon.Trigger:
			if self.settings.value('restore_on_tray_clicked'):
				self.show()
				if self.isMinimized():
					self.showNormal()

				self.activateWindow()

		elif reason == QSystemTrayIcon.DoubleClick:
			self.show()
			if self.isMinimized():
				self.showNormal()
			self.activateWindow()


	def initButtons(self):
		''' Adds 'Main' buttons to layout '''
		self.btns_widget = QWidget()
		hbox = QHBoxLayout()
		hbox.setContentsMargins(0,0,0,0)

		# ADD
		self.btn_add = Button(onClickHandler=0)
		self.btn_add.setObjectName('btn_add')
		self.btn_add.clicked.connect(self.add_download)

		# DOWNLOAD / RESUME / START
		self.btn_start = Button(onClickHandler=1)
		self.btn_start.setObjectName('btn_start')
		self.btn_start.clicked.connect(self.resume_download)

		# PAUSE
		self.btn_pause = Button()
		self.btn_pause.setObjectName('btn_pause')
		self.btn_pause.clicked.connect(self.pause_download)
		
		# DELETE
		self.btn_del = Button()
		self.btn_del.setObjectName('btn_del')
		self.btn_del.setContentsMargins(10,10,10,10)
		self.btn_del.clicked.connect(self.delete_selected)

		# MOVE UP (THE QUEUE)
		self.btn_moveup = Button()
		self.btn_moveup.setObjectName('btn_moveup')
		self.btn_moveup.clicked.connect(self.moveup)

		# MOVE DOWN (THE QUEUE)
		self.btn_movedown = Button()
		self.btn_movedown.setObjectName('btn_movedown')
		self.btn_movedown.clicked.connect(self.movedown)
		

		# SETTINGS
		self.btn_settings = Button()
		self.btn_settings.setObjectName('btn_settings')
		self.btn_settings.clicked.connect(self.display_settings)

		self.btns = [self.btn_add, self.btn_start, self.btn_pause, self.btn_del, self.btn_moveup, self.btn_movedown, self.btn_settings]

		hbox.addStretch(1)
		for i, btn in enumerate(self.btns):
			hbox.addWidget(btn)
		hbox.addStretch(1)
		
		self.btns_widget.setLayout(hbox)


	def initUI(self):
		vbox = QVBoxLayout()
		vbox.setSpacing(10)
		vbox.setContentsMargins(10,5,10,10)
		
		self.table = Table(self)
		self.initButtons()

		vbox.addWidget(self.btns_widget)
		vbox.addWidget(self.table)

		self.setLayout(vbox)

		self.setObjectName('mainWidget')
		self.setStyleSheet(
		'''
            #mainWidget {background: white; font:12px bold; border-radius: 10px;}
            #mainWidget:hover {background: red}
		'''
		)
		self.toast = None
		self.setWindowIcon(QIcon())
		
		self.resize(self.settings.value('window_size'))
		self.setMinimumSize(1000, 600)
		self.move(QDesktopWidget().availableGeometry().center() - self.frameGeometry().center())
		self.setWindowTitle('QDM')
		icon = QIcon('imgs/icon.png')
		self.setWindowIcon(icon)
		self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
		self.show()


	def display_settings(self):
		''' shows the Preferences dialog '''
		dlg = Preferences(self)
		dlg.show()
		# dlg.exec_() 


	def delete_selected(self):
		''' deletes selected rows of 'paused' or 'complete' downloads '''

		# If none of the selected downloads if 'inactive', return
		inactive_download_selected = False 
		for pbar in self.table.getSelectedProgressBars():
			if pbar.pause() or pbar.value() == 100: # check for inactive download
				inactive_download_selected =True
				break 

		if not inactive_download_selected:
			return

		delete_directive = 0 # default: Remove ONLY from LIST
		# check user preferences
		# if 'delete_downloads/confirm' is True, user's input is required to delete files
		if self.settings.value('delete_downloads/confirm'):
			dlg = DeleteConfirmationDialog(self)
			if dlg.exec_() == QDialog.Rejected:
				return
			delete_directive = dlg.result

		# otherwise, proceed with the saved delete directive
		else:
			delete_directive = self.settings.value('delete_downloads/remove_everything')



		# [1] Remove selected rows from table
		key_properties = self.table.deleteSelectedRows()

		for id_, priority in key_properties:
			# [2] Remove selection from database
			row = self.database.selectById(id_)
			name = row[1]
			path = row[3]
			tmp_path = self.settings.value('temp_download_dir') + '/' + name
			self.database.delete(name)

			# [3] Remove from list of active downloads (if present)
			if id_ in self.lst_incomplete_downloads:
				self.lst_incomplete_downloads.remove(id_)

			# [4] Remove Everyting (if directed)
			if delete_directive == 1:
				# Remove temp file if any
				if os.path.exists(tmp_path):
					shutil.rmtree(tmp_path)

				# Remove saved download if any
				if os.path.exists(path + '/' + name):
					os.remove(path + '/' + name)

		# [5] Adjust priority values
		for _, priority in key_properties:
			if priority == 0:
				continue
			for active_id in self.lst_incomplete_downloads:
				item_p = self.table.findTableWidgetItem('%d_priority' % active_id)
				p = int(item_p.value())

				if priority < p: # if deleted download was of higher priority
					item_p.setText(str(p - 1))


	def delete_selected2(self):
		''' 
		This method is called by the 'restart_download' method to remove an existing download, the user wants to restart.
		This method doesn't require user interaction.

		'''

		# [1] Remove selected rows from table
		key_properties = self.table.deleteSelectedRows()

		for id_, priority in key_properties:
			# [2] Remove selection from database
			row = self.database.selectById(id_)
			name = row[1]
			path = row[3]
			tmp_path = self.settings.value('temp_download_dir') + '/' + name
			self.database.delete(name)

			# [3] Remove from list of active downloads (if present)
			if id_ in self.lst_incomplete_downloads:
				self.lst_incomplete_downloads.remove(id_)

			# [4] Remove Everything
			# Remove temp file if any
			if os.path.exists(tmp_path):
				shutil.rmtree(tmp_path)

			# Remove saved download if any
			if os.path.exists(path + '/' + name):
				os.remove(path + '/' + name)

		# [5] Adjust priority values
		for _, priority in key_properties:
			if priority == 0:
				continue
			for active_id in self.lst_incomplete_downloads:
				item_p = self.table.findTableWidgetItem('%d_priority' % active_id)
				p = int(item_p.value())

				if priority < p: # if deleted download was of higher priority
					item_p.setText(str(p - 1))


	def get_current_download_id(self):
		return self.database.getMaxId() + 1

	def get_least_priority(self):
		''' Determines the priority for new download if it added to the top '''
		# [1] Get least priority from database and increment by one
		p = self.database.getLeastPriorityNumber() + 1
		# [2] Check if there exists 'paused' downloads 
		# 	  If there exists, get the priority of the top 'paused' download
		ans = p
		for id_ in self.lst_incomplete_downloads:
			item = self.table.findTableWidgetItem('%d_priority' % id_)
			priority = int(item.value())
			pbar = getWidgetByObjectName('%d_status' % id_)
			# if downloadItem with id, id_ is paused, ...
			if pbar.pause() and pbar.value() < 100:
				if priority < p: # if 'paused' download if of greater priority, 'take its space'
					if priority < ans: # store 'highest priority' download
						ans = priority		
		return ans


	def add_download(self):
		''' Called to add a new download '''
		file = File()

		''' Create 'Add download' dialog ''' 
		self.add_dialog = AddDownloadDialog()
		# Center dialog
		qr = self.add_dialog.frameGeometry()
		qr.moveCenter(self.frameGeometry().center())
		self.add_dialog.move(qr.topLeft())

		# display dialog
		if self.add_dialog.exec_() == QDialog.Accepted:
			# file = self.add_dialog.file
			url = self.add_dialog.uri
			t = ExtractInfoThread(url)
			t.done_.connect(self.continue_to_download)
			t.start()


	def resume_download(self):
		''' Resumes paused downloads '''

		pbars = self.table.getSelectedProgressBars()
		for pbar in pbars:
			# attempt to resume incomplete downloads
			if pbar.pause() and pbar.value() != 100:
				pbar.setResume()

				# [1] Obtain download properties
				id_ = int(pbar.objectName().split('_')[0])
				row = self.database.selectById(id_)
				file = File()
				file.setId(row[0])
				file.name = row[1]
				file.url = row[2]
				file.path = row[3]
				file.size = row[4]
				file.eta = row[5]
				file.speed = row[6]
				file.date_added = row[7]
				file.status = row[8]
				file.setPriority(row[9])
				file.setResume(row[10])
				
				# [2] Move download above 'fellow' paused downloads
				table_item = self.table.findTableWidgetItem('%d_priority' % file.getId()) # priority QTableWidgetItem
				file.setPriority(int(table_item.value()))

				priority_of_top_paused_download = file.priority()
				current_row = file.priority() - 1
				new_row = current_row

				for _id in self.lst_incomplete_downloads:
					if _id == file.getId():
						continue
					pbar = getWidgetByObjectName('%d_status' % _id)

					# find 'top paused' download from the top
					if pbar.pause():
						item_p = self.table.findTableWidgetItem('%d_priority' % _id)
						priority = int(item_p.value())
						
						# if download-to-be-resumed is of less priority ... (NOTE: bigger priority value means less)
						if priority < file.priority(): 
							if priority < priority_of_top_paused_download:
								priority_of_top_paused_download = priority

							# ... decrease priority of 'fellow' paused download by 1
							item_p.setText(str(priority + 1)) 

				if priority_of_top_paused_download != file.priority():
					file.setPriority(priority_of_top_paused_download)
					table_item.setText(str(file.priority()))

					new_row = priority_of_top_paused_download - 1

					if new_row != current_row:
						self.table.moveRowTo(current_row, new_row)
						self.table.table.selectRow(new_row)
					else:
						self.table.table.selectRow(current_row)

				# [3] Start download
				d = Download(file, self)
				d.start()


	@pyqtSlot(File)
	def continue_to_download(self, file):
		''' continues download process '''
		#### find file in database
		existing_file = self.database.find(file.name)

		if existing_file: # if download exists 

			file = existing_file

			# [1] Select User Choice for handling duplicate download (via 'DupliateDownloadDialog')
			self.dlg_duplicate_download = DuplicateDownloadDialog(file=file)
			# Center dialog
			qr = self.dlg_duplicate_download.frameGeometry()
			qr.moveCenter(self.frameGeometry().center())
			self.dlg_duplicate_download.move(qr.topLeft())

			# [2] Handle Duplicate download
			if self.dlg_duplicate_download.exec_() == QDialog.Accepted:

				# if KEEP_BOTH_FILES
				if self.dlg_duplicate_download.instruction == DuplicateDownloadDialog.KEEP_BOTH:

					# (i) Update date, id and priority
					file.date_added = strftime('%b %d %Y %H:%M:%S', localtime())
					file.setId(self.get_current_download_id())
					if file.priority() == 0:
						file.setPriority(self.get_least_priority())
					
					# (ii) Update filename and path (via 'DownloadFileInfo' dialog)
					self.dlg_download = DownloadFileInfo(parent=self,file=file)
					# Center dialog
					qr = self.dlg_download.frameGeometry()
					qr.moveCenter(self.frameGeometry().center())
					self.dlg_download.move(qr.topLeft())

					if self.dlg_download.exec_() == QDialog.Accepted:
						file = self.dlg_download.file
					else:
						return

					# (iii) Insert (new 'duplicate' download) into database
					if not self.database.find(file.name):
						self.database.insert(file)

					# (iv) Show new record
					self.table.insert_file(file, new=True)

				# if KEEP_DUPLICATE_ONLY
				elif self.dlg_duplicate_download.instruction == DuplicateDownloadDialog.KEEP_DUPLICATE_ONLY:

					# (i) Remove existing file (and/or temporary files) from system
					if os.path.exists(file.path + '/' + file.name):
						os.remove(file.path + '/' + file.name)
					if os.path.exists(self.tmp_download_dir + '/' + file.name):
						shutil.rmtree(self.tmp_download_dir + '/' + file.name)

					# (ii) Delete existing record from database
					self.database.delete(file.name)

					# (iii) Delete existing record from the table
					item = self.table.findTableWidgetItem('%d_priority' % file.getId())
					p = None
					if item.value() == '':
						p = 0
					else:
						p = int(item.value())
					self.table.deleteRow(file.getId())

					# (iv) Update the priority of incomplete downloads
					if file.getId() in self.lst_incomplete_downloads:
						self.lst_incomplete_downloads.remove(file.getId())
						for id_ in self.lst_incomplete_downloads:
							item_p = self.table.findTableWidgetItem('%d_priority' % id_)
							priority = int(item_p.value())
							if p < priority:
								item_p.setText(str(priority - 1)) 
					
					# (v) Update date, id and priority
					file.date_added = strftime('%b %d %Y %H:%M:%S', localtime())
					file.setId(self.get_current_download_id())
					if file.priority() == 0:
						file.setPriority(self.get_least_priority())

					# (vi) Update filename and path (via 'DownloadFileInfo' dialog)
					self.dlg_download = DownloadFileInfo(parent=self,file=file)
					# Center dialog
					qr = self.dlg_download.frameGeometry()
					qr.moveCenter(self.frameGeometry().center())
					self.dlg_download.move(qr.topLeft())

					if self.dlg_download.exec_() == QDialog.Accepted:
						file = self.dlg_download.file
					else:
						return

					# (vii) Insert into database
					if not self.database.find(file.name):
						self.database.insert(file)

					# (viii) Show new record
					self.table.insert_file(file, new=True)

				# if KEEP_EXISTING_ONLY
				elif self.dlg_duplicate_download.instruction == DuplicateDownloadDialog.KEEP_EXISTING_ONLY:

					# if existing file is complete
					if file.status == 100:
						# scroll to the 'completed' download
						self.highlightRow(file.getId())
						self.show()

						# attempt to open the file
						self.table.table.open_file()
						return

					# otherwise, continue download ....
			else:
				return

		else: 
			''' COMPLETELY NEW DOWNLOAD '''

			# [1] Update date, id and priority
			file.date_added = strftime('%b %d %Y %H:%M:%S', localtime())
			file.setId(self.get_current_download_id())
			if file.priority() == 0:
				file.setPriority(self.get_least_priority())

			# [2] Update filename and path from 'DownloadFileInfo' dialog
			dlg_download = DownloadFileInfo(parent=self,file=file)
			# Center dialog
			qr = dlg_download.frameGeometry()
			qr.moveCenter(self.frameGeometry().center())
			dlg_download.move(qr.topLeft())

			if dlg_download.exec_() == QDialog.Accepted:
				file = dlg_download.file
			else:
				return

			# [3] Insert into database
			if not self.database.find(file.name):
				self.database.insert(file)

			# [4] Show new record 
			self.table.insert_file(file, new=True)

		# add to download queue
		self.add_to_queue(file)
		
		### Start download
		d = Download(file, self)
		pbar = getWidgetByObjectName('%d_status' % file.getId())
		if pbar:
			pbar.setResume()
		d.start()


	def pause_download(self):
		''' pauses selected downloads '''
		rowIds = self.table.getSelectedRows()
		for rowId in rowIds:
			pbar = getWidgetByObjectName('%d_status' % rowId)
			pbar.setPause()
			self.download_paused.emit(rowId)

	def load_data(self, index=None):

		while True:
			file = self.database.fetchone()

			if file == None:
				break

			if file.status < 100:
				self.lst_incomplete_downloads.append(file.getId())
			self.table.insert_file(file, self.table.table.rowCount())

			if index is not None:
				index += 1

	def moveup(self):
		self.table.moveCurrentRow(-1)
		
	def movedown(self):
		self.table.moveCurrentRow(1)

	def add_to_queue(self, file):
		self.lst_incomplete_downloads.append(file.getId())
		self.download_started.emit(file)

	def take_off_queue(self, file_id):
		self.lst_incomplete_downloads.remove(file_id)
		self.download_completed.emit(file_id)


	def restart_download(self):
		files = self.table.table.getSelectedFiles()
		pbars = self.table.getSelectedProgressBars()

		# [1] Pause 'active' download(s)
		for pbar in pbars:
			pbar.setPause()

		# [2] delete previous records
		self.delete_selected2()
		

		## start new dowload
		for file in files:

			# [1] Update date_added, ID, eta and priority
			file.date_added = strftime('%b %d %Y %H:%M:%S', localtime())
			file.setId(self.get_current_download_id())
			file.eta = u'\u221E'
			file.setPriority(self.get_least_priority())

			# [2] Show new record 
			self.table.insert_file(file, new=True)

			# [3] add to download queue
			self.add_to_queue(file)

			# [3] Insert into database
			if not self.database.find(file.name):
				self.database.insert(file)

			### Start download
			d = Download(file, self)
			pbar = getWidgetByObjectName('%d_status' % file.getId())
			if pbar:
				pbar.setResume()
			d.start()
			self.highlightRow(file.getId())



	@pyqtSlot(Update)
	def updateProgress(self, update):
		''' Performs table and database updates for current downloads '''
		
		# if update is meant for a TableWidgetItem
		if update.type == Update.TABLE_ITEM:
			item = self.table.findTableWidgetItem(update.name)
			if item:
				item.setText(update.msg)

			if update.name.split('_')[-1] == 'size':
				self.database.updateColumn(update.id, 'size', size)

		# if update is meant for a QWidget e.g progressbar
		elif update.type == Update.WIDGET:
			pbar = getWidgetByObjectName(update.name)
			pbar.setValue(update.msg)

			# if there's a special instruction
			if update.instruction:

				if update.instruction == Update.PAUSE:
					pbar.setPause()
					self.database.updateColumn(update.id, 'status', update.msg)
				elif update.instruction == Update.COMPLETE:
					_, name, *_ = self.database.selectById(update.id)
					self.notify_download_complete(name)
					self.database.updateColumn(update.id, 'status', 100)
					self.database.updateColumn(update.id, 'priority', 0)
					self.database.updateColumn(update.id, 'speed', 0)
					self.database.updateColumn(update.id, 'eta', '')

					# take download of the 'download' queue
					self.take_off_queue(update.id)


	@pyqtSlot(File)
	def onAddDownload(self, file):
		''' Adjust priority values of other active downloads when a new one is started '''
		new_priority = file.priority()
		for id_ in self.lst_incomplete_downloads:

			if id_ == file.getId():
				continue

			item = self.table.findTableWidgetItem('%d_priority' % id_)
			priority_val = int(item.value())
			
			if new_priority <= priority_val:
				item.setText(str(priority_val + 1))
		self.table.table.selectRow(file.priority() - 1)


	@pyqtSlot(int)
	def onPauseDownload(self, file_id):
		''' Move down 'selected' paused download below other 'downloading' ones'''
		paused_p = self.table.findTableWidgetItem('%d_priority' % file_id)
		if paused_p.value() == '':
			return
		priority = int(paused_p.value())
		row = priority - 1
		dest_priority = priority
		newRow = row 

		for id_ in self.lst_incomplete_downloads:
			pbar = getWidgetByObjectName('%d_status' % id_)

			if id_ == file_id:
				continue

			# if downloading
			if not pbar.pause():
				item_p = self.table.findTableWidgetItem('%d_priority' % id_)
				val = int(item_p.value())

				# Move paused download below 'downloading' works
				if priority < val:
					if dest_priority < val:
						dest_priority = val
					item_p.setText(str(val - 1))

		if dest_priority == priority:
			self.table.table.selectRow(row)
			return

		newRow = dest_priority - 1
		paused_p.setText(str(dest_priority))
		self.table.moveRowTo(row, newRow)
		self.table.table.selectRow(newRow)


	@pyqtSlot(int)
	def onCompleteDownload(self, file_id):
		''' Adjust priority values of other active downloads when one gets completed '''

		item_old_priority = self.table.findTableWidgetItem('%d_priority' % file_id)
		old_priority = int(item_old_priority.value())
		item_old_priority.setText('')
		row = old_priority - 1

		# to determine where to insert completed download
		least_priority = old_priority 

		for id_ in self.lst_incomplete_downloads:

			if id_ == file_id:
				continue

			item = self.table.findTableWidgetItem('%d_priority' % id_)
			if item:
				priority_val = int(item.value())

				if priority_val > least_priority:
					least_priority = priority_val

				if old_priority < priority_val:
					item.setText(str(priority_val - 1))

		# if just completed download is least on priority (or is the only download)
		if least_priority == old_priority:
			self.highlightRow(file_id)
			return

		newRow = least_priority - 1
		self.table.moveRowTo(row, newRow)
		self.highlightRow(file_id)


	def highlightRow(self, file_id):
		self.table.scrollToRow(file_id)


	def closeEvent(self, e):
		''' tidies up before application closes '''

		if self.settings.value('close_button_minimizes', 1):
			self.hide()
			if not self.bool_exit:
				e.ignore()
				return

		self.settings.setValue('window_size', self.size())

		# [1] Save changes in download progress and priorities
		for id_ in self.lst_incomplete_downloads:
			pbar = getWidgetByObjectName('%d_status' % id_)
			item_p = self.table.findTableWidgetItem('%d_priority' % id_)

			# pause currently running downloads
			# if not pbar.pause():
			# 	pbar.pause()
			if pbar:
				self.database.updateColumn(id_, 'status', pbar.prefixFloat)
			if item_p:
				self.database.updateColumn(id_, 'priority', int(item_p.value()))
			# self.database.updateColumn(id_, 'speed', 0)
			# self.database.updateColumn(id_, 'eta', '')

		if self.settings.value('confirm_exit'):
			pass

		# [2] Close other top level widgets e.g. dialogs ; if open
		widgets = QApplication.instance().topLevelWidgets()
		for x in widgets:
			if self == x:
				continue
			x.close()

		# [3] Close database
		self.database.close_connection()
		e.accept()


	def resizeEvent(self, e):
		if self.toast:
			self.toast.moveBottomCenter()

	def displayToast(self, msg, duration=3):
		self.toast = Toast(self, msg, duration)
		self.toast.exec_()
	
	def notify_download_complete(self, filename):
		if self.settings.value('notify_only_inactive'):
			if not self.isActiveWindow():
				self.trayIcon.showMessage('Download Complete', filename)
		else:
			self.trayIcon.showMessage('Download Complete', filename)
		

	def restore_window(self):
		widgets = QApplication.instance().topLevelWidgets()
		for x in widgets:
			if self == x:
				continue
			x.showNormal()
			x.show()
		self.show()
		if self.isMinimized():
			self.showNormal()
		self.activateWindow()

def eprint(*args, **kwargs):
	print(*args, file=sys.stderr, **kwargs)	