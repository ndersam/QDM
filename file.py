from collections import OrderedDict

class File:

	def __init__(self, id_=0):
		self.name = ''
		self.url = ''
		self.path = ''
		self.size = ''
		self.eta = u'\u221E'
		self.speed = 0
		self.date_added = ''
		self.status = 0
		self.__id = id_ # Unique download id..
		self.__priority = 0 
		self.__resume_capable = 1
		self.type = ''

	def __str__(self):
		s = self.name + ', ' + self.url + ', ' + self.path + ', ' + str(self.size) + ', ' + str(self.status)
		return s

	def setPriority(self, priority):
		self.__priority = priority

	def priority(self):
		return self.__priority

	def getId(self):
		return self.__id

	def setId(self, id_):
		self.__id = id_

	def properties(self):
		x = OrderedDict({'id':self.__id,
							'priority': self.__priority,
							'name':self.name, 
							'url':self.url, 
							'path':self.path, 
							'size':self.size,
							'eta':self.eta, 
							'speed':self.speed,
							'date_added': self.date_added, 
							'status': self.status,
							'resume': self.__resume_capable})
		return x

	def canResume(self):
		return self.__resume_capable

	def setResume(self, val):
		self.__resume_capable = bool(val)



class Update:
	# Types of recipients
	TABLE_ITEM = 1
	WIDGET = 2
	
	# valid instructions
	PAUSE = 'pause'
	CANCELLED = 'cancelled'
	COMPLETE = 'complete'

	def __init__(self, id_, receiver_name, type_, msg, instruction=None):
		''' object for updating ui elements during download '''
		if type_ not in [self.TABLE_ITEM, self.WIDGET]:
			raise Exception
		if instruction and instruction not in [self.PAUSE, self.CANCELLED, self.COMPLETE]:
			raise Exception
		self.type = type_
		self.id = id_
		self.name = receiver_name
		self.msg = msg
		self.instruction = instruction

	def __str__(self):
		return '%s : {%s}' % (self.name, str(self.msg))