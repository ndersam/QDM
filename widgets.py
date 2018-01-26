import subprocess
import struct
import shutil
import queue
import json
import math
import sys
import os
import re

import pyperclip
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from file import *
from utils import *
from db import *
from qdm import *
from paths import *
from settings import *



class Button(QPushButton):
	''' Toolbar buttons '''

	def __init__(self, text='', parent=None, onClickHandler=None):
		super().__init__(text, parent)
		self.style = '''
			QPushButton#btn_add {border-color: white; border-style: inset; border-image:url(./imgs/link.png);} 
			QPushButton#btn_pause {border-color: white; border-style: inset; border-image:url(./imgs/pause.png);} 
			QPushButton#btn_del {border-color: white; border-style: inset; border-image:url(./imgs/delete.png);} 
			QPushButton#btn_moveup {border-color: white; border-style: inset; border-image:url(./imgs/up.png);}
			QPushButton#btn_movedown {border-color: white; border-style: inset; border-image:url(./imgs/down.png);} 
			QPushButton#btn_settings {border-color: white; border-style: inset; border-image:url(./imgs/settings.png);} 
			QPushButton#btn_start {border-color: white; border-style: inset; border-image:url(./imgs/arrow.png);}
			QPushButton:pressed { background-color: #E5F3FF;} 
			QPushButton:hover { background-color: #E5F3FF;}
			'''

		self.parent = parent
		self.onClickHandler = onClickHandler
		self.initUI()

	def initUI(self):
		self.setMinimumSize(25,25)
		self.setMaximumSize(25,25)
		self.setStyleSheet(self.style)

	# adds new download
	def add_download(self):
		self.new_download_window = AddDownloads(self.parent)


class Table(QWidget):
		
		# direction constants (for moving row up or down)
		DOWN = 1
		UP = -1

		def __init__(self,parent=None):
			super().__init__(parent=parent)
			self.parent = parent
			self.headerLabels = ['priority', 'name', 'size', 'status', 'speed', 'eta', 'date_added']
			self.initUI()


		def initUI(self):
			self.table = TableWidget(self)
			vbox = QVBoxLayout()
			vbox.addWidget(self.table)
			self.setLayout(vbox)

	
		def __insert_widgets__(self, widgets, newRow):
			''' inserts a row of tableitems removed from another row into new position, 'newRow' '''

			# add a new row
			self.table.insertRow(newRow)

			for col, item in enumerate(widgets):
				if col == 3: # 'Status' column (Progress bars)
					cloned_pbar = ProgressBar(parent=item.parent())
					cloned_pbar.setValue(item.value())
					if item.pause():
						cloned_pbar.setPause()
					else:
						cloned_pbar.setResume()
					cloned_pbar.setObjectName(item.objectName())
					del item
					self.table.setCellWidget(newRow, col, cloned_pbar)
				else: 
					self.table.setItem(newRow, col, item)

		## Main Insert method
		def insert_file(self, newFile, index=None, new=False):
			'''adds a download file '''

			row = newFile.priority() - 1 if index is None else index
			fileId = newFile.getId()

			if row == -1:
				return
			
			# add a new row
			self.table.insertRow(row)
			
			# populate new row
			for key, entry in newFile.properties().items():
				# skip irrelevant file properties
				if key not in self.headerLabels:
					continue
				col = self.headerLabels.index(key)

				if key == 'priority':
					item = TableWidgetItem('', TableWidgetItem.PRIORITY) if entry == 0 else TableWidgetItem(str(entry), TableWidgetItem.PRIORITY)
					item.setObjectName('%d_priority' % fileId)
					self.table.setItem(row, col, item)
				elif key == 'size':
					item = TableWidgetItem(format_size(entry), TableWidgetItem.SIZE) # + 7 spaces from the right
					item.setObjectName('%d_size' % fileId)
					self.table.setItem(row, col, item)
				elif key == 'speed':
					item = TableWidgetItem('', TableWidgetItem.SPEED) 
					item.setObjectName('%d_speed' % fileId)
					self.table.setItem(row, col, item)
				elif key == 'eta':
					item = TableWidgetItem(str(entry), TableWidgetItem.ETA)
					item.setObjectName('%d_eta' % fileId)
					self.table.setItem(row, col, item)
				elif key == 'status':					
					item = ProgressBar(self.table)
					item.setObjectName('%d_status' % fileId)
					if new:
						item.setResume()
					else:
						item.setPause()
					item.setValue(entry)
					self.table.setCellWidget(row, col, item)
				else:
					item = TableWidgetItem(entry)
					self.table.setItem(row, col, item)

			self.table.model().layoutChanged.emit()

		def moveCurrentRow(self, direction=DOWN):
			'''
			Moves selected rows in a vertical direction (either 'up' or 'down')
			'''
			if direction not in (self.DOWN, self.UP):
				return

			model = self.table.selectionModel()
			selected = model.selectedRows()

			if not selected: # return if no row was selected
				return

			# Get indices of new positions
			destination_indices = []
			for qm_index in selected:
				row = qm_index.row()
				col = qm_index.column()
				newRow = row + direction
				if not (0 <= newRow < self.table.rowCount()):
					newRow = row
				destination_indices.append(qm_index.sibling(newRow, col))
			

			items = []
			indexes = sorted(selected, key=lambda x: x.row(), reverse=(direction==self.DOWN))

			for idx in indexes:
				items.append(self.table.itemFromIndex(idx))
				rowNum = idx.row()
				
				newRow = rowNum + direction 
				if not (0 <= newRow < self.table.rowCount()):
					continue

				# Do not move inactive or completed downloads
				rowPriority = self.table.item(rowNum, 0).value()
				destRowPriority = self.table.item(newRow, 0).value()

				if len(rowPriority) == 0 or len(destRowPriority) == 0:
					continue

				rowItems = [] # for holding items from a certain row
				for col in range(self.table.columnCount()):
					taken = self.table.takeItem(rowNum, col)
					# hack for dealing with widgets inserted into tableWidget
					if not taken:
						taken = self.table.cellWidget(rowNum, col)
					# change the display priority number for the target row
					if col == 0:
						taken.setText(str(newRow + 1))
					rowItems.append(taken)
				self.table.removeRow(rowNum) # delete row
				self.__insert_widgets__(rowItems, newRow) # insert item in new row
				# change the display priority number for the 'displaced' row
				item_p = self.table.item(rowNum, 0)
				new_priority = rowNum + 1 
				item_p.setText(str(new_priority))

			model.clear()
			# Reselect moved rows
			for newIndex in destination_indices:
				model.select(newIndex, model.Select | model.Rows)

		def moveRowTo(self, row, newRow):
			''' moves row from one position to another '''

			if not (0 <= newRow < self.table.rowCount()):
				return

			# Do not move inactive or completed downloads
			rowPriority = self.table.item(row, 0).value()
			destRowPriority = self.table.item(newRow, 0).value()
			if destRowPriority == '':
				return

			rowItems = [] # for holding items from a certain row
			for col in range(self.table.columnCount()):
				taken = self.table.takeItem(row, col)
				# hack for dealing with widgets inserted into tableWidget
				if not taken:
					taken = self.table.cellWidget(row, col)
				rowItems.append(taken)
			self.table.removeRow(row) # delete row
			self.__insert_widgets__(rowItems, newRow) # insert item in new row
				
		def getSelectedRows(self):
			''' returns the download IDs of the selected rows '''
			selectedRowIndices = [index.row() for index in self.table.selectedIndexes()]
			selectedRowIndices = set(selectedRowIndices)
			rowIDs = [int(self.table.item(x, 0).objectName().split('_')[0]) for  x in selectedRowIndices]
			return rowIDs

		def getSelectedProgressBars(self):
			''' returns 'pause/resume' status of selected file '''
			selectedRowIndices = [index.row() for index in self.table.selectedIndexes()]
			selectedRowIndices = set(selectedRowIndices)
			pbars = [self.table.cellWidget(x, 3)for  x in selectedRowIndices]
			return pbars

		def deleteSelectedRows(self):
			'''
			Removes Selected rows from the table and returns in a list of tuples.
			Each tuple represents a single deleted download. It contains the 'id' and 'priority' of the download.
			It ignores selected 'active' downloads.
			'''	
			# [1] Get properties of downloads to be removed		
			key_properties = []
			index_list = []
			for index in self.table.selectionModel().selectedRows():
				
				download_id = int(self.table.item(index.row(), 0).objectName().split('_')[0])
				download_priority = 0 if self.table.item(index.row(), 0).value() == '' else int(self.table.item(index.row(), 0).value())

				# check if file is an 'active download'
				pbar = getWidgetByObjectName('%d_status' % download_id)
				if not pbar.pause() and pbar.value() < 100:
					continue

				key_properties.append((download_id, download_priority))
				index_list.append(QPersistentModelIndex(index))

			# [2] Remove the downloads from the table
			for index in index_list:
				self.table.removeRow(index.row())
			return key_properties

		def findTableWidgetItem(self, itemName):
			''' finds a TableWidgetItem by name '''
			# returns a list of all QTableWidgetItems
			items = self.table.findItems('', Qt.MatchContains)
			for item in items:
				if item is not None and item.objectName() == itemName:
					return item


		def scrollToRow(self, file_id):
			item_p = self.findTableWidgetItem('%d_priority' % file_id)
			if not item_p:
				return 
			row = item_p.row()
			self.table.selectRow(row)
			self.table.scrollToItem(item_p)



class TableWidget(QTableWidget):

	def __init__(self, parent=None):
		super().__init__(parent=parent)
		self.parent = parent
		self.initUI()


	def initUI(self):
		self.table_column_count = 7
		self.setStyleSheet('''QTableWidget::item { selection-background-color: #F0F0F0; selection-color: black;} ''')
		self.verticalHeader().hide()
		self.setShowGrid(False)
		self.setWordWrap(False)
		self.setFocusPolicy(Qt.NoFocus)
		self.setEditTriggers(QAbstractItemView.NoEditTriggers) # prevent text-editing
		self.setSelectionBehavior(QAbstractItemView.SelectRows) # enables row selection

		# set column count
		self.setColumnCount(self.table_column_count)
		# self.setRowCount(5)

		# add column header labels
		self.setHorizontalHeaderLabels(['#', 'Name', 'Size', 'Status', 'Speed', 'ETA', 'Added'])

		''' Set Column Width '''
		header = self.horizontalHeader()
		# default column widths
		header.resizeSection(0, 35)
		header.resizeSection(1, 315)
		header.resizeSection(2, 100)
		header.resizeSection(3, 200)
		header.resizeSection(4, 100)
		header.resizeSection(5, 85)
		header.resizeSection(6, 100)
		# set column resize mode as user-interactive
		for i in range(1, self.table_column_count):
			if i == 1:
				header.setSectionResizeMode(i, QHeaderView.Stretch)
			elif i == 6:
				header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
			else:
				header.setSectionResizeMode(i, QHeaderView.Interactive)

		self.create_custom_menu()
		self.customContextMenuRequested.connect(self.display_menu)
		self.cellDoubleClicked.connect(self.open_file)
				
	def disable_invalid_options(self):
		files = self.getSelectedFiles()
		btns = self.parent.parent.btns[1:-1] # all btns except 'Add' and 'Settings' buttons
		if len(files) == 0:
			for btn in btns:
				btn.setEnabled(False)
		else:
			for btn in btns:
				btn.setEnabled(True)
	
	def display_menu(self, p):
		''' conditionally displays a Right-Click menu and its Actions '''
		if self.itemAt(p):
			files = self.getSelectedFiles()
			bool_enable_action = True
			for file in files:
				if file.status < 100:
					bool_enable_action = False

			self.menu.actions()[0].setEnabled(bool_enable_action) # disable 'Open'
			self.menu.actions()[1].setEnabled(bool_enable_action) # disable 'Open In Folder'
			self.menu.actions()[3].setEnabled(bool_enable_action) # disable 'Move' action

			self.menu.actions()[5].setEnabled(not bool_enable_action) # disable 'Move up'
			self.menu.actions()[6].setEnabled(not bool_enable_action) # disable 'Move down'
			self.menu.actions()[10].setEnabled(not bool_enable_action) # disable 'Start'
			self.menu.actions()[11].setEnabled(not bool_enable_action) # disable 'Pause'
			self.menu.popup(QCursor.pos())

	def create_custom_menu(self):
		self.setContextMenuPolicy(Qt.CustomContextMenu)
		self.menu = QMenu(self)

		act_start = QAction('Start', self)
		act_start.triggered.connect(self.call_resume)

		act_pause = QAction('Pause', self)
		act_pause.triggered.connect(self.call_pause)

		act_delete = QAction('Delete', self)
		act_delete.triggered.connect(self.delete)

		act_openfolder = QAction('Open Containing Folder', self)
		act_openfolder.triggered.connect(self.open_in_folder)

		act_open = QAction('Open', self)
		act_open.triggered.connect(self.open_file)

		act_restart = QAction('Restart', self)
		act_restart.triggered.connect(self.restart)

		act_moveto = QAction('Move', self)
		act_moveto.triggered.connect(self.move_file)

		act_properties = QAction('Properties', self)
		act_properties.triggered.connect(self.show_properties)

		act_copylink = QAction('Copy link', self)
		act_copylink.triggered.connect(self.copy_link)

		act_moveup = QAction('Move up', self)
		act_moveup.triggered.connect(self.move_up)

		act_movedown = QAction('Move down', self)
		act_movedown.triggered.connect(self.move_down)

		self.menu.addAction(act_open)
		self.menu.addAction(act_openfolder)
		self.menu.addSeparator()
		self.menu.addAction(act_moveto)
		self.menu.addSeparator()
		self.menu.addAction(act_moveup)
		self.menu.addAction(act_movedown)
		self.menu.addSeparator()
		self.menu.addAction(act_copylink)
		self.menu.addSeparator()
		self.menu.addAction(act_start)
		self.menu.addAction(act_pause)
		self.menu.addSeparator()
		self.menu.addAction(act_restart)
		self.menu.addSeparator()
		self.menu.addAction(act_delete)
		self.menu.addSeparator()
		self.menu.addAction(act_properties)

	def getSelectedFiles(self):
		selectedRowIndices = [index.row() for index in self.selectedIndexes()]
		selectedRowIndices = set(selectedRowIndices)
		rowIDs = [int(self.item(x, 0).objectName().split('_')[0]) for  x in selectedRowIndices]
		
		files = []
		for id_ in rowIDs:
			row = self.parent.parent.database.selectById(id_)
			if row is None:
				continue

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

			files.append(file)

		return files

	def move_file(self):
		''' Moves (or renames) a selected file to a new location '''
		file = self.getSelectedFiles()
		if file is None:
			return
		file = file[0]

		old_path = file.path + '/' + file.name

		# dlg = QFileDialog.getSaveFileUrl(self, 'Move To', old_path, )[0] 
		dlg = QFileDialog(caption='Move To')
		dlg.setFileMode(QFileDialog.AnyFile)
		dlg.setAcceptMode(QFileDialog.AcceptSave)
		dlg.setDirectoryUrl(QUrl(old_path))

		if dlg.exec_() == QDialog.Accepted:
			new_path = dlg.selectedFiles()[0]

			basename = os.path.basename(new_path)
			path = new_path.replace( '/' + basename, '')

			# if selected name is not new
			if new_path == old_path:
				return

			find = self.parent.parent.database.find(basename)
			if find:
				if find.getId() != file.getId():
					self.parent.parent.displayToast('New name is associated with another file in database.')
					return

			# Move files
			shutil.move(old_path, new_path)

			# Update record in database
			self.parent.parent.database.updateColumn(file.getId(), 'path', path)
			self.parent.parent.database.updateColumn(file.getId(), 'name', basename)
	
	def open_in_folder(self):
		file = self.getSelectedFiles()[0]
		fullpath = file.path + '/' + file.name
		if os.path.exists(fullpath):
			fullpath = fullpath.replace('/', '\\')
			s = r'explorer /select, "' + fullpath + '"'
			subprocess.Popen(s)
		else:
			if file.status < 100:
				self.parent.parent.displayToast('Download Incomplete.')
			else:
				self.parent.parent.displayToast('File has been moved.')

	def open_file(self):
		file = self.getSelectedFiles()[0]
		if file.status != 100:
			return
		fullpath = file.path + '/' + file.name
		if os.path.exists(fullpath):
			QDesktopServices.openUrl(QUrl.fromLocalFile(fullpath))
		else:
			if file.status < 100:
				self.parent.parent.displayToast('Download Incomplete.')
			else:
				self.parent.parent.displayToast('File has been moved.')

	def call_pause(self):
		self.parent.parent.pause_download()

	def call_resume(self):
		self.parent.parent.resume_download()

	def copy_link(self):
		file = self.getSelectedFiles()[0]
		pyperclip.copy(file.url)

		# Display a toast message
		self.parent.parent.displayToast('Link copied to clipboard.')

	# TO-DO
	def show_properties(self):
		file = self.getSelectedFiles()[0]
		dlg = PropertiesDialog(self, file)
		frame = dlg.frameGeometry()
		frame.moveCenter(self.parent.parent.frameGeometry().center())
		dlg.move(frame.topLeft())
		dlg.exec_()


	def restart(self):
		self.parent.parent.restart_download()

	def delete(self):
		self.parent.parent.delete_selected()

	def move_up(self):
		self.parent.moveCurrentRow(-1)

	def move_down(self):
		self.parent.moveCurrentRow(1)




class AddDownloadDialog(QDialog):

	def __init__(self, parent=None):
		super().__init__(parent=parent)
		self.uri = ''
		self.file = File()
		self.initUI()
		self.read_from_clipboard()

	def initUI(self):

		# descriptive label
		lbl = QLabel(self)
		lbl.setText('Enter download URL')
		lbl.move(20,20)

		# lineEdit for URL or file path
		self.lineEdit = QLineEdit(self)
		self.lineEdit.move(20,40)
		self.lineEdit.resize(467, 20)
		self.lineEdit.textChanged.connect(self.enable_btn_okay)

		# # button for opening files
		# self.btn_add_torrent = QPushButton(text='....', parent=self)
		# self.btn_add_torrent.move(455, 40)
		# self.btn_add_torrent.resize(32,22)
		# self.btn_add_torrent.clicked.connect(self.add_torrent_file)


		# Accepting and Rejecting Buttons
		self.btn_okay = QPushButton(text='Ok', parent=self)
		self.btn_okay.resize(50,30)
		self.btn_okay.move(437, 70)
		self.btn_okay.setEnabled(False)
		self.btn_okay.clicked.connect(self.verify)

		self.btn_cancel = QPushButton('Cancel',self)
		self.btn_cancel.resize(60,30)
		self.btn_cancel.move(370, 70)
		self.btn_cancel.clicked.connect(self.cancel)


		# Message Label
		self.lbl_error_msg = QLabel(parent=self)
		self.lbl_error_msg.setObjectName('lbl_error_msg')
		self.lbl_error_msg.setStyleSheet('''color: red; font: bold large "Times New Roman"''')
		self.lbl_error_msg.resize(70, 30)
		self.lbl_error_msg.move(20, 70)

		
		self.setWindowModality(Qt.ApplicationModal)
		self.setAcceptDrops(True)
		# enable title and close buttons only
		self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint| Qt.WindowMinimizeButtonHint)
		self.setWindowTitle('Add download')
		# self.setWindowIcon(QIcon(''))
		self.resize(500, 120)
		self.setMinimumSize(500, 120)
		self.setMaximumSize(500, 120)

		# self.show()

	def verify(self):
		isValidUrl = validate_uri(self.lineEdit.text())
		if isValidUrl is True:
			self.uri = self.lineEdit.text()
			self.accept()
		else:
			self.lbl_error_msg.setText('INVALID URL')


	def cancel(self):
		self.reject()


	def enable_btn_okay(self):
		if self.lineEdit.text():
			self.uri = self.lineEdit.text()
			self.btn_okay.setEnabled(True)
		else:
			self.btn_okay.setEnabled(False)

	def read_from_clipboard(self):
		# Django validation regex
		regex = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' #domain...
        r'localhost|' #localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

		match = re.match(regex, pyperclip.paste())
		if match:
			self.uri = match.group()

		if self.uri:
			# set lineEdit text to URL found from clipboard
			self.lineEdit.setText(self.uri)
			# highlight entire text 
			self.lineEdit.selectAll()


class DuplicateDownloadDialog(QDialog):

	KEEP_BOTH = 1
	KEEP_DUPLICATE_ONLY = 2 
	KEEP_EXISTING_ONLY = 3

	def __init__(self, parent=None, file=None):
		super().__init__(parent=parent)
		self.file = file
		self.instruction = 0
		self.initUI()

	def initUI(self):

		""" display file name """
		name = self.file.name
		if len(name) > 50:
			name = name[:47] + '...'

		lbl_filename = QLabel(name, self)
		lbl_filename.setWordWrap(False)
		lbl_filename.setStyleSheet(
			'''
			font-style: bold;
			font-size: 16px;
			font-family: "Times New Roman";
			''')
		lbl_filename.setMaximumHeight(30)
		lbl_filename.setMaximumWidth(350)
		
		lbl_msg = QLabel('exists.', self)
		lbl_msg.setFixedSize(30,30)

		hbox_msg = QHBoxLayout()
		hbox_msg.addStretch(1)
		hbox_msg.addWidget(lbl_filename)
		hbox_msg.addWidget(lbl_msg)
		hbox_msg.addStretch(1)

		""" Radio btns for selecting 'duplicate download' action """
		lbl_choice = QLabel('Do you wish to?', self)
		lbl_choice.setStyleSheet('''text-align: left center;''')

		self.rbtn_keep_both = QRadioButton(self)
		self.rbtn_keep_both.setText('Add duplicate with a numbered file name')
		self.rbtn_keep_both.setChecked(True)
		self.rbtn_keep_duplicate = QRadioButton(self)
		self.rbtn_keep_duplicate.setText('Add duplicate and overwrite existing file')
		self.rbtn_keep_existing = QRadioButton(self)
		self.rbtn_keep_existing.setText('If existing file is complete, show or resume')

		vbox_rbtns = QVBoxLayout()
		vbox_rbtns.addWidget(lbl_choice)
		vbox_rbtns.addWidget(self.rbtn_keep_both)
		vbox_rbtns.addWidget(self.rbtn_keep_duplicate)
		vbox_rbtns.addWidget(self.rbtn_keep_existing)

		hbox_rbtns = QHBoxLayout()
		hbox_rbtns.addStretch(1)
		hbox_rbtns.addLayout(vbox_rbtns)
		hbox_rbtns.addStretch(1)		

		""" OK and Cancel btns """
		btn_okay = QPushButton('OK', self)
		btn_okay.setFixedSize(60,30)
		btn_okay.setFocusPolicy(Qt.NoFocus)
		btn_okay.clicked.connect(self.accept_)

		btn_cancel = QPushButton('CANCEL', self)
		btn_cancel.setFixedSize(60,30)
		btn_cancel.setFocusPolicy(Qt.NoFocus)
		btn_cancel.clicked.connect(self.reject)


		""" Main Layout """
		hbox_btns = QHBoxLayout()
		hbox_btns.addStretch(1)
		hbox_btns.addWidget(btn_okay)
		hbox_btns.addWidget(btn_cancel)
		hbox_btns.addStretch(1)

		vbox = QVBoxLayout()
		vbox.addStretch(1)
		vbox.addLayout(hbox_msg)
		vbox.addStretch(1)
		vbox.addLayout(hbox_rbtns)
		vbox.addStretch(2)
		vbox.addLayout(hbox_btns)
		vbox.addStretch(1)

		
		self.setLayout(vbox)
		self.setWindowModality(Qt.ApplicationModal)
		self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)
		self.setWindowTitle('Duplicate download')
		self.setFixedSize(400, 200)
		self.show()

	def accept_(self):
		if self.rbtn_keep_both.isChecked():
			self.instruction = self.KEEP_BOTH
			name, ext = os.path.splitext(self.file.name) # separates filename from extension
			name += '_2' 
			self.file.name = name + ext
		elif self.rbtn_keep_duplicate.isChecked():
			self.instruction = self.KEEP_DUPLICATE_ONLY
		elif self.rbtn_keep_existing.isChecked():
			self.instruction = self.KEEP_EXISTING_ONLY

		self.accept()


class ProgressBar(QProgressBar):
	__pause = False

	def __init__(self, parent=None):
		QProgressBar.__init__(self)
		self.prefixFloat = self.value()
		self.initUI()
		self.valueChanged.connect(self.changeLooks)

	def setValue(self, value):
		self.prefixFloat = value
		QProgressBar.setValue(self, int(value))
		self.changeLooks()

	def initUI(self):
		self.style = '''
			QProgressBar { border: 2px solid white; border-radius 5px; text-align: center }
			QProgressBar:chunk {background-color: #86C43F; width:20px;}
		 '''
		self.setStyleSheet(self.style)

	def changeLooks(self):

		if self.value() == self.maximum():
			self.style = '''
			QProgressBar { border: 2px solid white; border-radius 5px; text-align: center }
			QProgressBar:chunk {background-color: #86C43F; width:20px;}
		 '''
			self.setFormat('Completed')
			self.setStyleSheet(self.style)
		elif self.value() >= 0 and self.value() < self.maximum():
			self.style = self.style = '''
			QProgressBar { border: 2px solid white; border-radius 5px; text-align: center }
			QProgressBar:chunk {background-color: #D4FF55; width:20px;}
		 '''
			self.setStyleSheet(self.style)
			if not self.__pause:
				self.setFormat('Downloading... %.01f%s' % (self.prefixFloat, '%'))
			else:
				self.setFormat('Paused %.01f%s' % (self.prefixFloat, '%'))
		else:
			self.style = '''
			QProgressBar { border: 2px solid white; border-radius 5px; text-align: center;  background-color: #FF552A}
			QProgressBar:chunk {background-color: red; width:20px;}'''
			self.setStyleSheet(self.style)
			self.setFormat('Moved')

	def setPause(self):
		self.__pause = True
		self.changeLooks()
		
	def setResume(self):
		self.__pause = False
		self.changeLooks()
		
	def pause(self):
		return self.__pause


class PropertiesDialog(QDialog):

	def __init__(self, parent=None, file=None):
		super().__init__(parent=None)
		self.parent = parent
		self.file = file
		self.initUI()

	def initUI(self):

		# Get file icon from OS
		path = self.file.path + '/' + self.file.name
		if not os.path.exists(path): # create a temp file to extract icon
			p = get_localAppData_folder() + '/QDM/foo/'
			if not os.path.exists(p):
				os.makedirs(p)
			temp_file = p + self.file.name 
			with open(temp_file, 'wb') as f:
				f.write(b'<empty'*100)
			path = temp_file
		fileInfo = QFileInfo(path)
		provider = QFileIconProvider()
		icon = provider.icon(fileInfo)

		# file icon
		lbl_icon = QLabel('', self)
		pixmap = icon.availableSizes()[1] # medium size
		lbl_icon.setPixmap(icon.pixmap(pixmap))

		# File name
		lbl_name = QLabel(format_string(self.file.name, 60), self)
		lbl_name.setMaximumWidth(400)
		lbl_name.setMinimumWidth(400)
		lbl_name.setStyleSheet('''font: bold 14px "Times New Roman"; color: #4E5764; ''')

		# Download status
		pbar = getWidgetByObjectName('%d_status' % self.file.getId())
		percent = pbar.prefixFloat
		isPaused = pbar.pause()
		status = ''
		if percent == 100:
			if os.path.exists(self.file.path + '/' + self.file.name):
				status = 'Completed'
			else:
				status = 'Moved'
		else:
			if isPaused:
				status = 'Paused %.02f%s' % (percent, '%')
			else:
				status = 'Downloading...'
		lbl_status = QLabel(status, self)

		# File size
		lbl_size = QLabel(format_size(self.file.size), self)

		# Output directory
		lbl_outputpath = QLabel(format_string(self.file.path, 75), self)

		# URL
		lbl_url = QLabel('', self)
		lbl_url.setOpenExternalLinks(True)
		lbl_url.setText('<a href={}>{}</a>'.format(self.file.url, format_string(self.file.url, 75)))

		vbox_icon = QVBoxLayout()
		vbox_icon.addStretch(1)
		vbox_icon.addWidget(lbl_icon)
		vbox_icon.addStretch(2)

		vbox_description = QVBoxLayout()
		vbox_description.addStretch(1)
		vbox_description.addWidget(lbl_name)
		vbox_description.addWidget(lbl_status)
		vbox_description.addWidget(lbl_size)
		vbox_description.addWidget(lbl_outputpath)
		vbox_description.addWidget(lbl_url)
		vbox_description.addStretch(2)

		hbox = QHBoxLayout()
		hbox.addStretch(1)
		hbox.addLayout(vbox_icon)
		hbox.addStretch(1)
		hbox.addLayout(vbox_description)
		hbox.addStretch(3)

		self.setLayout(hbox)

		self.setWindowModality(Qt.ApplicationModal)
		self.setAcceptDrops(True)
		self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
		self.setWindowTitle('Properties')
		self.setFixedSize(500, 150)
		self.show()


class DownloadFileInfo(QDialog):

	def __init__(self, parent=None, file=None):
		super().__init__(parent=None)
		self.parent = parent
		self.file = file
		self.initUI()
		if not self.parent.isActiveWindow():
			self.parent.activateWindow()
			self.activateWindow()
		

	def initUI(self):

		# 'Save to' label
		lbl_saveto = QLabel(self)
		lbl_saveto.setText('Save to')
		lbl_saveto.move(20,20)

		# lineEdit for 'Save to directory'
		self.edit_path = QLineEdit(self)
		self.edit_path.move(20,40)
		self.edit_path.resize(430, 20)
		

		if self.file:
			# Guess 'Category'
			self.guess_category()
			self.edit_path.setText(self.file.path)

		# button for opening files
		self.btn_select_dir = QPushButton(text='....', parent=self)
		self.btn_select_dir.move(455, 40)
		self.btn_select_dir.resize(32,22)
		self.btn_select_dir.setFocusPolicy(Qt.NoFocus)
		

		# 'Filename' label
		self.lbl_filename = QLabel(self)
		self.lbl_filename.setText('File name')
		self.lbl_filename.move(20, 70)

		# lineEdit for 'Filename'
		self.edit_filename = QLineEdit(self)
		self.edit_filename.move(20,90)
		self.edit_filename.resize(465, 20)
		
		if self.file and self.file.name:
			self.edit_filename.setText(self.file.name)

		# 'Download Url label'
		self.lbl_url = QLabel(self)
		self.lbl_url.move(20, 130)
		if self.file and self.file.url:
			url = self.file.url 
			if len(url) > 60:
				url = url[:60] + '...'
			self.lbl_url.setText('Url: %s' % url)

		# 'File size' label
		self.lbl_size = QLabel(self)
		self.lbl_size.setStyleSheet(''' text-align: right; ''')
		self.lbl_size.move(400, 130)
		if self.file and self.file.size:
			size = format_size(self.file.size)
			self.lbl_size.setText('Size: %s' % size)

		# Download and Rejecting Buttons
		self.btn_download = QPushButton(text='Download', parent=self)
		self.btn_download.resize(80,30)
		self.btn_download.move(407, 155)
		self.btn_download.setFocus()
		
		self.btn_cancel = QPushButton('Cancel',self)
		self.btn_cancel.resize(60,30)
		self.btn_cancel.move(340, 155)

		# add-to-top-of-queue checkbox
		self.check_push = QCheckBox('Add to top of queue', self)
		self.check_push.move(20, 155)
		
		# Event handling
		self.edit_filename.textChanged.connect(self.enable_btn_download)
		self.btn_download.clicked.connect(self.verify_inputs)
		self.btn_select_dir.clicked.connect(self.select_directory)
		self.btn_cancel.clicked.connect(self.cancel)
		self.edit_path.textChanged.connect(self.enable_btn_download)

		self.setWindowModality(Qt.ApplicationModal)
		self.setAcceptDrops(True)
		# enable title and close buttons only
		self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint| Qt.WindowMinimizeButtonHint)
		self.setWindowTitle('New File')
		self.setFixedSize(500, 200)
		
		self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
		self.activateWindow()

		self.show()

	def verify_inputs(self):
		if os.path.exists(self.edit_path.text()):
			self.file.path = self.edit_path.text()
			self.file.name = self.edit_filename.text()
			if self.check_push.isChecked():
				self.file.setPriority(1)
			self.accept()
		else:
			pass

	def cancel(self):
		self.uri = ''
		self.reject()

	def guess_category(self):
	
		_, ext = os.path.splitext(self.file.name)
		ext = ext.replace('.', '')
		settings = self.parent.settings

		for idx, cat in enumerate(settings.value('categories').split(',')):
			key_extension = 'category/%s/extensions' % cat
			key_path = 'category/%s/path' % cat

			# skip the 'general' category
			if idx == 0:
				continue

			extensions = settings.value(key_extension).split(' ')
			if ext in extensions:
				self.file.path = settings.value(key_path)
				return

		# if extension is not categorized, save as 'general'
		self.file.path = settings.value('category 0 path')


	def select_directory(self):
		dlg = QFileDialog(caption='Select Folder')
		dlg.setFileMode(QFileDialog.DirectoryOnly)
		settings = QSettings('ndersam', 'qdm')
		dlg.setDirectory(self.file.path)

		# for first download in a certain category
		if not os.path.exists(self.file.path):
			os.makedirs(self.file.path)

		# Center dialog
		qr = dlg.frameGeometry()
		qr.moveCenter(self.frameGeometry().center())
		dlg.move(qr.topLeft())

		if dlg.exec_() == QDialog.Accepted:
			directory = dlg.selectedFiles()[0]
			self.edit_path.setText(directory)

	def enable_btn_download(self):
		if self.edit_path.text() and self.edit_filename.text():
			self.uri = self.edit_path.text()
			self.btn_download.setEnabled(True)
		else:
			self.btn_download.setEnabled(False)


class TableWidgetItem(QTableWidgetItem):

	SIZE = 'size'
	PRIORITY = 'priority'
	SPEED = 'speed'
	ETA = 'eta'

	def __init__(self, text, type_=None):
		super().__init__(text)
		self.__objectName = ''
		self.type = type_
		self.value_ = None
		if self.type:
			self.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
		self.setText(text)


	def setObjectName(self, name):
		self.__objectName = name 


	def objectName(self):
		return self.__objectName

	def setText(self, text):
		''' Overridden to give unique formatting to TableWidgetItem displaying different item types, e.g size, eta '''
		if self.type:
			if self.type == self.SIZE:
				text += ' ' * 7
			elif self.type == self.PRIORITY:
				self.value_ = text
				text  += ' ' * 3
			elif self.type == self.SPEED:
				text += ' ' * 3
			elif self.type == self.ETA:
				text += ' ' * 4
		QTableWidgetItem.setText(self, text)

	def value(self):
		return self.value_


class BrowserThread(QThread):
	''' Handles download urls sent from browser '''
	signal = pyqtSignal(File)

	def __init__(self, application=None):
		QThread.__init__(self)
		self.app = application
		self.queue = queue.Queue()
		self.file = File()

	def __del__(self):
		self.wait()

	def run(self):
		try:
			self.read_thread_func()
		except Exception as e:
			pass

	# Thread that reads message from Chrome browser
	def read_thread_func(self):
		message_number = 0
		try:
			while True:
				# Read the message length (first 4 bytes)
				text_length_bytes = sys.stdin.buffer.read(4)

				if len(text_length_bytes) == 0:
					if self.queue:
						self.queue.put(None)
				else:
					# Unpack message length as 4 byte integer.
					text_length = struct.unpack('i', text_length_bytes)[0]

					# Read the text (JSON object) of the message.
					binary = sys.stdin.buffer.read(text_length)
					text = binary.decode('utf-8')

					dic = json.loads(binary)
					url = dic["finalUrl"]
					

					t = ExtractInfoThread(url)
					t.done_.connect(self.onReceive)
					t.start()

					if self.queue:
						self.queue.put(text)
					else:
						pass
		except Exception as e:
			pass

	@pyqtSlot(File)
	def onReceive(self, file):
		if self.app:
			self.app.restore_window()
			self.app.continue_to_download(file)
			
			# self.signal.emit(file)

	@pyqtSlot()
	def stop(self):
		self.quit()



class Toast(QDialog):
    def __init__(self, parent=None, msg='', timeout=3):
    	super().__init__(parent=parent)
    	self.parent = parent
    	self.msg = msg
    	self.time_to_wait = timeout
    	self.timer = QTimer(self)
    	self.timer.setInterval(1000)
    	self.timer.timeout.connect(self.changeContent)
    	self.initUI()
    	self.timer.start()

    def initUI(self):
    	self.lbl = QLabel('\t' + self.msg, self)
    	self.resize(self.parent.table.width() // 3,30) 
    	self.lbl.setAlignment(Qt.AlignCenter)
    	
    	self.lbl.setStyleSheet(''' color: #FFFFD4; font-size: 12px;
    		border-style: solid; border-color: rgba(166, 81, 251, 40%);
    		border-width: 1px; border-radius: 5px; 
    	background-color: rgba(166, 81, 251, 60%);''')
    	self.setAttribute(Qt.WA_TranslucentBackground)
    	self.setWindowFlags(Qt.FramelessWindowHint)
    	self.setWindowIcon(QIcon(QPixmap('imgs/transparent.png')))
    	if self.parent:
    		self.moveBottomCenter()
  
    def moveBottomLeft(self):
    	x = 27
    	y = self.parent.height() - self.height() - 27
    	self.move(x, y)

    def moveBottomCenter(self):
    	x = self.parent.width() // 2 - self.frameGeometry().center().x()
    	y = self.parent.height() - self.height() - 27 
    	self.move(x,y)

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()

    def changeContent(self):
        self.time_to_wait -= 1
        if self.time_to_wait <= 0:
            self.accept()

    def paintEvent(self, e):
    	''' add some translucency '''
    	color = self.palette().light().color()
    	color.setAlpha(200)
    	p = QPainter(self)
    	p.fillRect(self.rect(), color)

    def resizeEvent(self, e):
    	self.lbl.resize(self.width(), self.height())


    # def paintEvent(self, event=None):
    # 	# painter = QPainter(self)

    # 	# painter.setOpacity(.9)
    # 	# painter.setBrush(Qt.white)
    # 	# painter.setPen(QPen(Qt.white))
    # 	# painter.drawRect(self.rect())
    # 	canvas = QPixmap()
    # 	canvas.fill(Qt.transparent)

    # 	p = QPainter(self)
    # 	p.setOpacity(.3)
    # 	p.setBrush(QBrush(Qt.white))
    # 	p.setPen(QPen(Qt.transparent))
    # 	# p.drawRect(self.rect())
    # 	# p.start()
    # 	p.drawPixmap(self.rect(), canvas)



class Preferences(QDialog):
	''' QDM preferences dialog '''
	def __init__(self, parent=None):
		super(Preferences, self).__init__()
		self.parent = parent
		self.settings = self.parent.settings
		self.initUI()

	def initUI(self):
		self.ui = Ui_Form()
		self.ui.setupUi(self)

		""" Navigation Buttons """
		self.config_nav_buttons()

		""" Browser Integration """
		self.config_browsers()

		""" Windows Integration """
		self.config_windows_integration()

		""" Directories """
		self.config_directories()

		""" Notifications """
		self.config_notifications()

		""" UI configurations """
		self.config_ui()

		""" Network configuations """
		self.config_network()

		# Center dialog
		qr = self.frameGeometry()
		parent_center = self.parent.geometry().center()
		qr.moveCenter(parent_center)
		self.move(qr.topLeft())		

		# Other Settings
		self.setWindowModality(Qt.ApplicationModal)
		self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint) 

	def config_windows_integration(self):
		''' Settings for integrating with Windows OS '''		
		self.ui.chbx_start_at_boot.setChecked(self.settings.value('on_system_boot'))
		self.ui.chbx_start_mini.setChecked(self.settings.value('on_system_boot/minimized'))
		self.ui.chbx_start_mini.setEnabled(self.ui.chbx_start_at_boot.isChecked())
		

		self.ui.chbx_start_at_boot.toggled.connect(self.ui.chbx_start_mini.setEnabled)
		

	def config_directories(self):
		''' Manages 'directory' settings '''

		# [1] Populate list of categories  (into the 'combobox')
		categories = self.settings.value('categories').split(',')
		for cat in categories:
			self.ui.combo_categories.addItem(cat)
			
		# [2] Configure other widgets
		self.ui.edit_category_path.setReadOnly(True)
		self.ui.edit_temp_dir.setText(self.settings.value('temp_download_dir'))

		# [3] Add Event handlers
		self.ui.combo_categories.currentIndexChanged.connect(self.onCategoryClicked)
		self.ui.btn_browse_category_path.clicked.connect(self.browse_save_path)
		self.ui.btn_browse_temp_dir.clicked.connect(self.browse_temp_dir)
		self.ui.btn_add_category.clicked.connect(self.add_new_category)
		self.ui.btn_del_category.clicked.connect(self.remove_category)
		self.ui.edit_extensions.textEdited.connect(self.save_extensions)


		self.onCategoryClicked(0)


	def onCategoryClicked(self, index):
		''' Handler for 'combo_categories' currentIndexChanged signal '''

		cat = self.settings.value('categories').split(',')[index]
		key_extension = 'category/%s/extensions' % cat
		default_extensions = ''
		key_path = 'category/%s/path' % cat
		default_path = self.settings.value('category/General/path')

		# if 'General' Category
		if cat == 'General':
			self.ui.btn_del_category.setEnabled(False)
			self.ui.edit_extensions.setReadOnly(True)
		else:
			self.ui.btn_del_category.setEnabled(True)
			self.ui.edit_extensions.setReadOnly(False)
 
		# if (category) extension key doesn't exist, create new entry and set default value
		if self.settings.value(key_extension) is None:
			self.settings.setValue(key_extension, default_extensions)

		# if (category) path key doesn't exist, create new entry and set default value
		if self.settings.value(key_path) is None:
			self.settings.setValue(key_path, default_path)

		self.ui.edit_extensions.setText(self.settings.value(key_extension))
		self.ui.edit_category_path.setText(self.settings.value(key_path))
		
	def browse_save_path(self):
		dlg = QFileDialog(caption='Select Folder for %s' % self.ui.combo_categories.currentText())
		dlg.setFileMode(QFileDialog.DirectoryOnly)
		dlg.setDirectory(self.ui.edit_category_path.text())

		# Center dialog
		qr = dlg.frameGeometry()
		qr.moveCenter(self.frameGeometry().center())
		dlg.move(qr.topLeft())

		if dlg.exec_() == QDialog.Accepted:
			new_path = dlg.selectedFiles()[0]
			key_path = 'category/%s/path' % self.ui.combo_categories.currentText()
			self.settings.setValue(key_path, new_path)
			self.ui.edit_category_path.setText(new_path)

	def browse_temp_dir(self):
		dlg = QFileDialog(caption='Select Temporary Download Folder')
		dlg.setFileMode(QFileDialog.DirectoryOnly)
		dlg.setDirectory(self.ui.edit_temp_dir.text())

		# Center dialog
		qr = dlg.frameGeometry()
		qr.moveCenter(self.parent.geometry().center())
		dlg.move(qr.topLeft())

		if dlg.exec_() == QDialog.Accepted:
			new_path = dlg.selectedFiles()[0]
			self.settings.setValue('temp_download_dir', new_path)
			self.ui.edit_temp_dir.setText(new_path)

	def add_new_category(self):
		dlg = AddNewCategoryDialog(self)
		if dlg.exec_() == QDialog.Accepted:
			category = dlg.category
			category = category.replace(' ', '_')
			path = dlg.path
			extensions = dlg.extensions

			self.ui.combo_categories.addItem(category)

			categories =  self.settings.value('categories', "General,Compressed,Documents,Programs,Audio,Video")
			categories += ',' + category
			self.settings.setValue('categories', categories)
			self.settings.setValue('category %d' % (self.ui.combo_categories.count() - 1), extensions)
			self.settings.setValue('category %d path' % (self.ui.combo_categories.count() - 1), path)

	def remove_category(self):
		''' Removes the current 'Category' shown in the combo box '''

		idx = self.ui.combo_categories.currentIndex()
		text = self.ui.combo_categories.currentText()

		msg = 'Are you sure you want to delete the category "{}"'.format(text)
		confirmation = QMessageBox.question(self, 'Deletion of Category', msg, QMessageBox.No | QMessageBox.Yes, QMessageBox.No)
		if confirmation == QMessageBox.No:
			return
		self.ui.combo_categories.removeItem(idx)
		categories =  self.settings.value('categories', "General,Compressed,Documents,Programs,Audio,Video")
		categories = categories.replace(','+text,'')
		path = self.settings.setValue('categories', categories) 

	def save_extensions(self, text):
		idx = self.ui.combo_categories.currentIndex()
		cat = self.settings.value('categories').split(',')[idx]
		key_extension = 'category/%s/extensions' % cat
		extensions = self.ui.edit_extensions.text()
		self.settings.setValue(key_extension, extensions)

	def config_browsers(self):
		''' Configure browser integration '''
		self.ui.rbtn_alt_no_catch.setChecked(True)
		self.ui.chbx_chrome.setChecked(True)

	def config_notifications(self):
		''' Manages how windows notifies of completed downloads '''
		self.ui.chbx_enable_notifications.setChecked(self.settings.value('allow_notifications'))
		
		self.ui.chbx_notify_only_inactive.setChecked(self.settings.value('notify_only_inactive'))
		self.ui.chbx_notify_only_inactive.setEnabled(self.ui.chbx_enable_notifications.isChecked())

		self.ui.chbx_enable_notifications.toggled.connect(lambda state: self.settings.setValue('allow_notifications', int(state)))
		self.ui.chbx_enable_notifications.toggled.connect(lambda state: self.ui.chbx_notify_only_inactive.setEnabled(state))
		self.ui.chbx_notify_only_inactive.toggled.connect(lambda state: self.settings.setValue('notify_only_inactive', int(state)))

	def config_ui(self):

		self.ui.chbx_confirm_exit.setChecked(self.settings.value('confirm_exit'))
		self.ui.chbx_confirm_exit.toggled.connect(lambda state: self.settings.setValue('confirm_exit',int(state)))
		
		self.ui.chbx_confirm_delete.setChecked(self.settings.value('delete_downloads/confirm'))
		self.ui.chbx_confirm_delete.toggled.connect(lambda state: self.settings.setValue('delete_downloads/confirm', int(state)))

		self.ui.chbx_close_minimizes.setChecked(self.settings.value('close_button_minimizes'))
		self.ui.chbx_close_minimizes.toggled.connect(lambda state: self.settings.setValue('close_button_minimizes', int(state)))

		self.ui.chbx_on_tray_clicked.setChecked(self.settings.value('restore_on_tray_clicked'))
		self.ui.chbx_on_tray_clicked.toggled.connect(lambda state: self.settings.setValue('restore_on_tray_clicked', int(state)))

		self.ui.chbx_minimize_minimizes.setChecked(self.settings.value('minimize_button_minimizes'))
		self.ui.chbx_minimize_minimizes.toggled.connect(lambda state: self.settings.setValue('minimize_button_minimizes', int(state)))

	def config_network(self):
		''' Manages proxy settings '''
		choice = self.settings.value('proxy/choice')

		if choice == 'system':
			self.ui.rbtn_system_proxy.setChecked(True)
		elif choice == 'none':
			self.ui.rbtn_no_proxy.setChecked(True)
		elif choice == 'manual':
			self.ui.rbtn_manual_proxy.setChecked(True)

		self.ui.rbtn_manual_proxy.clicked.connect(lambda x : self.set_proxy('manual'))
		self.ui.rbtn_no_proxy.clicked.connect(lambda x: self.set_proxy('none'))
		self.ui.rbtn_system_proxy.clicked.connect(lambda x: self.set_proxy('system'))

		proxies = self.settings.value('proxy/config/manual')
		http = proxies['HTTP']
		https = proxies['HTTPS']
		ftp = proxies['FTP']

		# HTTP
		self.ui.edit_http_address.setText(http['Address'])
		self.ui.edit_http_user.setText(http['Username'])
		self.ui.edit_http_port.setText(http['Port'])
		self.ui.edit_http_password.setText(http['Password'])

		self.ui.edit_http_address.textEdited.connect(self.update_manual_proxy)
		self.ui.edit_http_user.textEdited.connect(self.update_manual_proxy)
		self.ui.edit_http_port.textEdited.connect(self.update_manual_proxy)
		self.ui.edit_http_password.textEdited.connect(self.update_manual_proxy)

		# HTTPS
		self.ui.edit_https_address.setText(https['Address'])
		self.ui.edit_https_user.setText(https['Username'])
		self.ui.edit_https_port.setText(https['Port'])
		self.ui.edit_https_password.setText(https['Password'])

		self.ui.edit_https_address.textEdited.connect(self.update_manual_proxy)
		self.ui.edit_https_user.textEdited.connect(self.update_manual_proxy)
		self.ui.edit_https_port.textEdited.connect(self.update_manual_proxy)
		self.ui.edit_https_password.textEdited.connect(self.update_manual_proxy)

		# FTP
		self.ui.edit_ftp_address.setText(ftp['Address'])
		self.ui.edit_ftp_user.setText(ftp['Username'])
		self.ui.edit_ftp_port.setText(ftp['Port'])
		self.ui.edit_ftp_password.setText(ftp['Password'])

		self.ui.edit_ftp_address.textEdited.connect(self.update_manual_proxy)
		self.ui.edit_ftp_user.textEdited.connect(self.update_manual_proxy)
		self.ui.edit_ftp_port.textEdited.connect(self.update_manual_proxy)
		self.ui.edit_ftp_password.textEdited.connect(self.update_manual_proxy)

	def set_proxy(self, choice):
		''' Sets proxy choice '''
		if choice not in ['system', 'none', 'manual']:
			return 
		self.settings.setValue('proxy/choice', choice)

	def update_manual_proxy(self):
		''' Updates manual configuration entered from the text box '''
		http_address = self.ui.edit_http_address.text()
		http_user = self.ui.edit_http_user.text()
		http_port = self.ui.edit_http_port.text()
		http_password = self.ui.edit_http_password.text()

		https_address = self.ui.edit_https_address.text()
		https_user = self.ui.edit_https_user.text()
		https_port = self.ui.edit_https_port.text()
		https_password = self.ui.edit_https_password.text()

		ftp_address = self.ui.edit_ftp_address.text()
		ftp_user = self.ui.edit_ftp_user.text()
		ftp_port = self.ui.edit_ftp_port.text()
		ftp_password = self.ui.edit_ftp_password.text()

		proxies = {
					'HTTP':	{'Address':http_address, 'Port':http_port, 'Username':http_user, 'Password':http_password},
					'HTTPS':{'Address':https_address, 'Port':https_port, 'Username':https_user, 'Password':https_password},
					'FTP':	{'Address':ftp_address, 'Port':ftp_port, 'Username':ftp_user, 'Password':ftp_password},
				}
		proxies = QVariant(proxies)
		self.settings.setValue('proxy/config/manual', proxies)

	def config_nav_buttons(self):
		self.lbl_navs = [
						self.ui.lbl_nav_browser,
						self.ui.lbl_nav_directories,
						self.ui.lbl_nav_gen,
						self.ui.lbl_nav_network,
						self.ui.lbl_nav_ui
						]
		for lbl in self.lbl_navs:
			lbl.hide()

			
		self.ui.btn_nav_ui.clicked.connect(self.nav_ui)
		self.ui.btn_nav_gen.clicked.connect(self.nav_general)
		self.ui.btn_nav_browser.clicked.connect(self.nav_browser)
		self.ui.btn_nav_directories.clicked.connect(self.nav_directories)
		self.ui.btn_nav_network.clicked.connect(self.nav_network)

		self.ui.scrollArea.verticalScrollBar().valueChanged.connect(self.onScrollArea)
		self.nav_general()

	def onScrollArea(self, val):
		# 'General'
		if val < 140:
			for lbl in self.lbl_navs:
				if lbl == self.ui.lbl_nav_gen:
					lbl.show()
				else:
					lbl.hide()
		# 'User Interface'
		elif val < 415:
			for lbl in self.lbl_navs:
				if lbl == self.ui.lbl_nav_ui:
					lbl.show()
				else:
					lbl.hide()
		# 'Directories'
		elif val < 760:
			for lbl in self.lbl_navs:
				if lbl == self.ui.lbl_nav_directories:
					lbl.show()
				else:
					lbl.hide()
		# 'Browser'
		elif val < 1070:
			for lbl in self.lbl_navs:
				if lbl == self.ui.lbl_nav_browser:
					lbl.show()
				else:
					lbl.hide()
		# 'Network'
		else:
			for lbl in self.lbl_navs:
				if lbl == self.ui.lbl_nav_network:
					lbl.show()
				else:
					lbl.hide()



	def nav_ui(self):
		self.ui.scrollArea.ensureWidgetVisible(self.ui.group_UI,50,70)
		for lbl in self.lbl_navs:
			if lbl == self.ui.lbl_nav_ui:
				lbl.show()
			else:
				lbl.hide()

	def nav_general(self):
		self.ui.scrollArea.ensureWidgetVisible(self.ui.group_General,50,70)
		# self.ui.lbl_nav_gen.show()
		for lbl in self.lbl_navs:
			if lbl == self.ui.lbl_nav_gen:
				lbl.show()
			else:
				lbl.hide()

	def nav_browser(self):
		self.ui.scrollArea.ensureWidgetVisible(self.ui.group_browser,50,70)
		for lbl in self.lbl_navs:
			if lbl == self.ui.lbl_nav_browser:
				lbl.show()
			else:
				lbl.hide()

	def nav_directories(self):
		self.ui.scrollArea.ensureWidgetVisible(self.ui.group_directories,50,70)
		# self.ui.lbl_nav_ui.show()
		for lbl in self.lbl_navs:
			if lbl == self.ui.lbl_nav_directories:
				lbl.show()
			else:
				lbl.hide()

	def nav_network(self):
		self.ui.scrollArea.ensureWidgetVisible(self.ui.group_network,50,70)
		# self.ui.lbl_nav_ui.show()
		for lbl in self.lbl_navs:
			if lbl == self.ui.lbl_nav_network:
				lbl.show()
			else:
				lbl.hide()


class DeleteConfirmationDialog(QDialog):
	ONLY_LIST = 0
	EVERYTHING = 1
	def __init__(self, parent=None):
		super().__init__(parent=None)
		self.parent = parent
		self.result = self.ONLY_LIST
		self.initUI()

	def initUI(self):
		# layout
		vbox = QVBoxLayout(self)

		lbl_msg = QLabel('Are you sure you want to delete the selected download(s)?',self)
		
		self.rbtn_only_list = QRadioButton(self)
		self.rbtn_only_list.setText('Remove only from list')

		self.rbtn_only_list.setChecked(True)
		self.rbtn_remove_all = QRadioButton(self)
		self.rbtn_remove_all.setText('Remove everything (Careful!)')

		self.chbx_remember_setting = QCheckBox(self)
		self.chbx_remember_setting.setText('Don\'t show this dialog again')

		self.rbtn_only_list.toggled.connect(self.set_result)
		self.rbtn_remove_all.toggled.connect(self.set_result)

		btn_cancel = QPushButton('Cancel', self)
		btn_cancel.setFocus()
		btn_cancel.setMaximumWidth(50)
		btn_cancel.clicked.connect(self.reject)
		
		btn_okay = QPushButton('OK', self)
		btn_okay.clearFocus()
		btn_okay.setMaximumWidth(50)
		btn_okay.clicked.connect(self.save)

		hbox2 = QHBoxLayout()
		hbox2.addWidget(self.chbx_remember_setting)
		hbox2.addStretch(1)
		hbox2.addWidget(btn_okay)
		hbox2.addWidget(btn_cancel)

		vbox.addWidget(lbl_msg)
		vbox.addWidget(self.rbtn_only_list)
		vbox.addWidget(self.rbtn_remove_all)
		vbox.addStretch(1)
		vbox.addLayout(hbox2)
		self.setLayout(vbox)

		
		self.setFixedSize(400,120)

		# center
		qr = self.frameGeometry()
		parent_center = self.parent.frameGeometry().center()
		qr.moveCenter(parent_center)
		self.move(qr.topLeft())

		self.setWindowModality(Qt.ApplicationModal)
		self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
		self.setWindowTitle('Delete Confirmation')

		self.show()

	def set_result(self):
		if self.rbtn_only_list.isChecked():
			self.result = self.ONLY_LIST
		elif self.rbtn_remove_all.isChecked():
			self.result = self.EVERYTHING
			

	def save(self):
		self.set_result()
		if self.chbx_remember_setting.isChecked():
			if self.parent:
				self.parent.settings.setValue('delete_downloads/remove_everything', self.result)
				self.parent.settings.setValue('delete_downloads/confirm', 0)
		self.accept()


class AddNewCategoryDialog(QDialog):

	def __init__(self, parent=None):
		super().__init__(parent=None)
		self.parent = parent
		self.initUI()

	def initUI(self):

		lbl_category = QLabel('Category name', self)

		self.edit_category_name = QLineEdit(self)
		self.edit_category_name.setPlaceholderText('e.g. music')
		self.edit_category_name.textChanged.connect(self.verify)

		lbl_extension = QLabel('Associated extensions', self)
		self.edit_extensions = QLineEdit(self)
		self.edit_extensions.setPlaceholderText('space-separated list of extensions e.g. mp3 mp4 m4a')
		self.edit_extensions.textChanged.connect(self.verify)

		lbl_path = QLabel('Save future downloads to ...', self)
		self.edit_path = QLineEdit(self)
		self.edit_path.setReadOnly(True)
		self.edit_path.textChanged.connect(self.verify)

		btn_browse = QPushButton('...', self)
		btn_browse.clicked.connect(self.browse_save_path)
		btn_browse.setMaximumWidth(30)
		btn_browse.setFocusPolicy(Qt.NoFocus)

		self.btn_okay = QPushButton('OK', self)
		self.btn_okay.setMaximumWidth(50)
		self.btn_okay.setFocusPolicy(Qt.NoFocus)
		self.btn_okay.setEnabled(False)
		self.btn_okay.clicked.connect(self.accept)

		hbox = QHBoxLayout()
		hbox.addWidget(self.edit_path)
		hbox.addWidget(btn_browse)

		hbox2 = QHBoxLayout()
		hbox2.addStretch(1)
		hbox2.addWidget(self.btn_okay)

		vbox = QVBoxLayout(self)
		vbox.addWidget(lbl_category)
		vbox.addWidget(self.edit_category_name)
		vbox.addWidget(lbl_extension)
		vbox.addWidget(self.edit_extensions)
		vbox.addWidget(lbl_path)
		vbox.addLayout(hbox)
		vbox.addLayout(hbox2)


		self.setLayout(vbox)
		self.setFixedSize(400,200)

		# center
		qr = self.frameGeometry()
		parent_center = self.parent.frameGeometry().center()
		qr.moveCenter(parent_center)
		self.move(qr.topLeft())

		self.setWindowModality(Qt.ApplicationModal)
		self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
		self.setWindowTitle('New Category')
		self.show()

	def browse_save_path(self):
		dlg = QFileDialog(caption='Select Output Folder')
		dlg.setFileMode(QFileDialog.DirectoryOnly)
		dlg.setDirectory(get_download_folder())

		# Center dialog
		qr = dlg.frameGeometry()
		qr.moveCenter(self.frameGeometry().center())
		dlg.move(qr.topLeft())

		if dlg.exec_() == QDialog.Accepted:
			path = dlg.selectedFiles()[0]
			self.edit_path.setText(path)

	def verify(self):

		# [1] Verify that all editText widget's aren't empty
		if not (self.edit_category_name.text() and self.edit_extensions.text() and self.edit_path.text()):
			return 

		# [2] Attempt to catch 'bad' characters
		foul_chars = [',', '\\', '/', ':', '*', '?', '"', '<', '>', '|']
		for char in foul_chars:
			if char in list(self.edit_category_name.text()):
				return

		if ',' in list(self.edit_extensions.text()):
			# display toast message
			return

		self.category = self.edit_category_name.text()
		self.extensions = self.edit_extensions.text()
		self.path = self.edit_path.text()
		self.btn_okay.setEnabled(True)


class Tray(QSystemTrayIcon):

	def __init__(self, icon, parent=None):
		super().__init__(icon=icon, parent=parent)

		menu = QMenu(parent)
		self.parent =  parent

		act_restore = QAction('Restore', menu)
		act_restore.triggered.connect(self.restore)

		self.act_launchAtStartUp = QAction('Launch at startup ', self)
		self.act_launchAtStartUp.setCheckable(True)
		if self.parent.settings.value('on_system_boot') is None:
			self.parent.settings.setValue('on_system_boot', 1)
		self.act_launchAtStartUp.setChecked(bool(self.parent.settings.value('on_system_boot')))
		self.act_launchAtStartUp.toggled.connect(self.update_start_at_boot)

		act_about = QAction('About', self)
		act_about.triggered.connect(self.show_about_dlg)

		act_quit = QAction('Quit', self)
		act_quit.triggered.connect(self.quit)
		
		menu.addAction(act_restore)
		menu.addAction(self.act_launchAtStartUp)
		menu.addSeparator()
		menu.addAction(act_about)
		menu.addSeparator()
		menu.addAction(act_quit)
		self.setContextMenu(menu)

	def update_start_at_boot(self, val):
		self.parent.settings.setValue('on_system_boot', int(val))
		

	def show_about_dlg(self):
		dlg_about = AboutDialog()
		dlg_about.exec_()

	def quit(self):
		self.parent.bool_exit = True
		self.parent.close()

	def restore(self):
		self.parent.show()
		if self.parent.isMinimized():
			self.parent.showNormal()
		self.parent.activateWindow()

	
class AboutDialog(QDialog):

	def __init__(self, parent=None):
		super().__init__(parent=parent)
		self.initUI()

	def initUI(self):
		self.setFixedSize(400,300)
		self.setWindowModality(Qt.ApplicationModal)
		self.center()
		self.setWindowFlags(Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
		self.setWindowTitle('About QDM')
		self.show()

	def center(self):
		qr = self.frameGeometry()
		cp = QDesktopWidget().availableGeometry().center()
		qr.moveCenter(cp)
		self.move(qr.topLeft())

if __name__ == '__main__':
	
	app = QApplication(sys.argv)
	ex = PropertiesDialog()
	sys.exit(app.exec_())