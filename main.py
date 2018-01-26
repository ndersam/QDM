import sys

from PyQt5.QtWidgets import QApplication

from gui import Application

app = QApplication(sys.argv)
ex = Application()
sys.exit(app.exec_())