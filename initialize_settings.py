from PyQt5.QtCore import QSettings, QVariant, QSize
from paths import get_download_folder, get_localAppData_folder

def default_settings():
	''' Application default settings '''
	settings = QSettings('ndersam', 'qdm')

	''' Windows Integration '''
	if settings.value('on_system_boot') is None:
		settings.setValue('on_system_boot', 1)

	if settings.value('on_system_boot/minimized') is None:
		settings.setValue('on_system_boot/minimized', 1)

	''' File Categories '''
	if settings.value('categories') is None:
		categories = 'General,Compressed,Documents,Programs,Audio,Video'
		settings.setValue('categories', categories)

		lst = categories.split(',')

		for idx, cat in enumerate(lst):
			key_extension = 'category/%s/extensions' % cat
			key_path = 'category/%s/path' % cat
			default_path = get_download_folder()
			default_extension_values = ''

			if cat == 'General':
				default_extension_values = 'The file types that are not listed in any other category'	
			else:		
				default_path += '/' + cat
	 
				# if 'Compressed' Category
				if cat == 'Compressed':
					default_extension_values = 'zip rar r0* r1* arj gz sit sitx sea ace bz2 7z'

				# if 'Documents' Category
				elif cat == 'Documents':
					default_extension_values = 'doc pdf ppt pps docx pptx'

				# if 'Programs' Category
				elif cat == 'Programs':
					default_extension_values = 'exe msi'

				# if 'Audio' Category
				elif cat == 'Audio':
					default_extension_values = 'mp3 wav wma mpa ram ra aac aif m4a'

				# if 'Video' Category
				elif cat == 'Video':
					default_extension_values = 'avi mpg mpe mpeg asf wmv mov qt rm mp4 flv m4v webm ogv ogg mkv'

			
			settings.setValue(key_extension, default_extension_values)
			settings.setValue(key_path, default_path)


	# Temporary Storage Directory
	if settings.value('temp_download_dir') is None:
		settings.setValue('temp_download_dir', get_localAppData_folder() + '/QDM/tmp')


	''' Browser Integration '''
	if settings.value('auto_start_caught_downloads') is None:
		settings.setValue('auto_start_caught_downloads', 0)


	''' Notifications '''
	if settings.value('allow_notifications') is None:
		settings.setValue('allow_notifications', 1)

	if settings.value('notify_only_inactive') is None:
		settings.setValue('notify_only_inactive', 1)

	''' Download Settings '''
	if settings.value('queue_size') is None:
		settings.setValue('queue_size', 6)

	''' User Interface '''
	if settings.value('delete_downloads/confirm') is None:
		settings.setValue('delete_downloads/confirm', 1)

	if settings.value('delete_downloads/remove_everything') is None:
		settings.setValue('delete_downloads/remove_everything', 0)

	if settings.value('confirm_exit') is None:
		settings.setValue('confirm_exit', 0)

	if settings.value('window_size') is None:
		settings.setValue('window_size', QVariant(QSize(1000, 600)))

	''' System Tray '''
	if settings.value('close_button_minimizes') is None:
		settings.setValue('close_button_minimizes', 1)

	if settings.value('minimize_button_minimizes') is None:
		settings.setValue('minimize_button_minimizes', 0)

	if settings.value('restore_on_tray_clicked') is None:
		settings.setValue('restore_on_tray_clicked', 1)

	''' Network Settings '''
	if settings.value('proxy/choice') is None:
		settings.setValue('proxy/choice', 'system')

	if settings.value('proxy/config/manual') is None:
		proxies = {'HTTP':{'Address':'', 'Port':'', 'Username':'', 'Password':''},
					'HTTPS': {'Address':'', 'Port':'', 'Username':'', 'Password':''},
					'FTP': {'Address':'', 'Port':'', 'Username':'', 'Password':''}}
		proxies = QVariant(proxies)
		settings.setValue('proxy/config/manual', proxies)

	if settings.value('proxy/config/none') is None:
		proxies = {'HTTP':{'Address':'', 'Port':0, 'Username':'', 'Password':''},
					'HTTPS': {'Address':'', 'Port':0, 'Username':'', 'Password':''},
					'FTP': {'Address':'', 'Port':0, 'Username':'', 'Password':''}}
		proxies = QVariant(proxies)
		settings.setValue('proxy/config/none', proxies)





if __name__ == '__main__':
	default_settings()