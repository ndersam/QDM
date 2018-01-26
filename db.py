from collections import OrderedDict
import sqlite3 as lite
import sys

from file import *


class DownloadDatabase:

		# Constants
		__table_name__ = 'downloads'
		__db__ = 'qdm.db'
		__columns__ = 'name, url, path, size, eta, speed, date_added, status, priority, resume'
		__list_of_columns__ = ['id', 'name', 'url', 'path', 'size', 'eta', 'speed', 'date_added', 'status', 'priority', 'resume']
		__key__ = 'name'

		def __init__(self):
			try:
				# Create connection
				self.conn = None
				self.create_connection()

				cur = self.conn.cursor()
				# Create table (if it doesn't exist)
				cur.execute(
					'''
					CREATE TABLE IF NOT EXISTS downloads 
					(id INTEGER PRIMARY KEY, 
					name TEXT UNIQUE, 
					url TEXT,  
					path TEXT, 
					size INT, 
					eta TEXT, 
					speed REAL, 
					date_added TEXT, 
					status INT,
					priority INT,
					resume INT)
					'''
					)
				self.conn.commit()
			except lite.Error as e:
				print('Error %s' % e.args[0])
				sys.exit(1)

			# prepare cursor for fetching data from table	
			self.__load_cursor__ = None
			self.loaded_completed = False
			self.__fetch_active_downloads__()

		def update(self, file):
			''' updates a file's properties '''
			try:
				row = self.find(file.name)
				cur = self.conn.cursor()
				if row:
					for column in self.__list_of_columns__:
						# if new entry is same as old entry, skip
						if row[column] == file.properties[column]:
							continue
						s = 'UPDATE {} SET {}=? WHERE {}=?;'.format(self.__table_name__, column, self.__key__)
						print(s)
						cur.execute(s, (file.properties[column], file.properties[self.__key__]))
					self.conn.commit()
			except lite.Error as e:
				print('\nError %s' % e.args[0])
				print('In update')
				sys.exit(1)

		def updateColumn(self, id_, fieldname, entry):
			''' Updates the field of a record with id, id_ '''
			s = 'UPDATE ' + self.__table_name__ + ' SET ' + fieldname + '=? WHERE id =?;'
			try:
				cur = self.conn.cursor()
				cur.execute(s, (entry, id_))
				self.conn.commit()
				return True 
			except lite.Error as e:
				raise e

		def insert(self, newfile):
			''' inserts a new record into database 	'''
			row = [newfile.name, newfile.url, newfile.path, newfile.size, newfile.eta, newfile.speed, newfile.date_added, newfile.status, newfile.priority(), int(newfile.canResume())]
			
			# insert sql command
			columns = 'name, url, path, size, eta, speed, date_added, status, priority, resume'
			s = '?' + ', ?' * (len(self.__list_of_columns__) - 2)
			s = 'INSERT INTO ' + self.__table_name__ + '(' + columns + ') ' + 'VALUES(' + s + ');'

			try:
				cur = self.conn.cursor()
				cur.execute(s, row)
				self.conn.commit()
			except lite.Error as e:
				print('\nError %s' % e.args[0])
				print('In insert')
				sys.exit(1)			
			
		def find(self, filename):
			''' find a record in the database based on filename '''
			try:
				cur = self.conn.cursor()
				s = 'SELECT * FROM ' + self.__table_name__  +' WHERE ' + self.__key__ + '=?;' 
				cur.execute(s, (filename,))
				row = cur.fetchone()

				if  row is None:
					return None
			
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
				return file
			except lite.Error as e:
				print(e.args[0].__str__())
				s = e.args[0].__str__().split(':')[0]
				if s == 'no such column':
					return None 
				print('\nError %s' % e.args[0])
				sys.exit(1)

		def create_connection(self):
			try:
				self.conn = lite.connect(self.__db__)
			except lite.Error as e:
				raise e
			

		def __fetch_active_downloads__(self):
			try:
				s = 'SELECT * FROM ' + self.__table_name__ + ' WHERE priority > 0 ORDER BY priority ASC;'
				self.__load_cursor__ = self.conn.cursor()
				self.__load_cursor__.execute(s)
			except lite.Error as e:
				raise e

		def __fetch_completed_downloads__(self):
			try:
				s = 'SELECT * FROM ' + self.__table_name__ + ' WHERE priority = 0 ORDER BY id desc;'
				self.__load_cursor__ = self.conn.cursor()
				self.__load_cursor__.execute(s)
			except lite.Error as e:
				raise e
		
		def fetchone(self):
		
			row = self.__load_cursor__.fetchone()
			if row is None:
				if not self.loaded_completed:
					self.__fetch_completed_downloads__()
					self.loaded_completed = True
					row = self.__load_cursor__.fetchone()
				else:
					return None

			if row:
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
				return file

			return None

		def close_connection(self):
			if self.conn:
				self.conn.close()

		def delete(self, name):
			''' deletes record by 'name' column '''
			try:
				s = 'DELETE FROM ' + self.__table_name__ + ' WHERE name = ?;'
				cur = self.conn.cursor()
				cur.execute(s, (name,))
				self.conn.commit()
				print(name + ' deleted')
				return True
			except lite.Error as e:
				raise e
			except Exception as e:
				print(e.args[0])


		def getMaxId(self):
			try:
				s = 'SELECT * FROM ' + self.__table_name__ + ' ORDER BY id DESC LIMIT 1'
				cur = self.conn.cursor()
				cur.execute(s)
				row = cur.fetchone()
				if row:
					return row[0]
				return 0
			except lite.Error as e:
				print(e.args[0])


		def getLeastPriorityNumber(self):
			try:
				s = 'SELECT * FROM ' + self.__table_name__ + ' ORDER BY priority DESC LIMIT 1'
				cur = self.conn.cursor()
				cur.execute(s)
				row = cur.fetchone()
				if row:
					return row[-2]
				return 0
			except lite.Error as e:
				raise e

		def selectById(self, id_):
			s = 'SELECT * FROM ' + self.__table_name__ + ' WHERE id =? LIMIT 1;'
			try:
				self.__load_cursor__ = self.conn.cursor()
				self.__load_cursor__.execute(s, (id_,))
				row = self.__load_cursor__.fetchone()
				return row
			except lite.Error as e:
				raise e