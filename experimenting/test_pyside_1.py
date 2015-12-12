#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
import PySide

logger.info("PySide version: {}".format(PySide.__version__))
logger.info("QtCore version: {}".format(PySide.QtCore.qVersion()))

import sys
from PySide.QtCore import *
from PySide.QtGui import *
from PySide.QtDeclarative import QDeclarativeView

# # Create a Qt application
# app = QApplication(sys.argv)
# # Create a Label and show it
# label = QLabel("<font color=red size=40>Hello World</font>")
# label.show()
# # Enter Qt application main loop
# app.exec_()
# sys.exit()


# # Create Qt application and the QDeclarative view
# app = QApplication(sys.argv)
# view = QDeclarativeView()
# # Create an URL to the QML file
# url = QUrl('view.qml')
# # Set the QML file and show
# view.setSource(url)
# view.show()
# # Enter Qt main loop
# sys.exit(app.exec_())



# class ExampleApp(QDialog):
#     ''' An example application for PyQt. Instantiate
#         and call the run method to run. '''
#     def __init__(self):
#         # create a Qt application --- every PyQt app needs one
#         self.qt_app = QApplication(sys.argv)
#
#         # The available greetings
#         self.greetings = ['hello', 'goodbye', 'heyo']
#
#         # Call the parent constructor on the current object
#         QDialog.__init__(self, None)
#
#         # Set up the window
#         self.setWindowTitle('PyQt Example')
#         self.setMinimumSize(300, 200)
#
#         # Add a vertical layout
#         self.vbox = QVBoxLayout()
#
#         # The greeting combo box
#         self.greeting = QComboBox(self)
#         # Add the greetings
#         list(map(self.greeting.addItem, self.greetings))
#
#         # The recipient textbox
#         self.recipient = QLineEdit('world', self)
#
#         # The Go button
#         self.go_button = QPushButton('&Go')
#         # Connect the Go button to its callback
#         self.go_button.clicked.connect(self.print_out)
#
#         # Add the controls to the vertical layout
#         self.vbox.addWidget(self.greeting)
#         self.vbox.addWidget(self.recipient)
#         # A very stretchy spacer to force the button to the bottom
#         self.vbox.addStretch(100)
#         self.vbox.addWidget(self.go_button)
#
#         # Use the vertical layout for the current window
#         self.setLayout(self.vbox)
#
#     def print_out(self):
#         ''' Print a greeting constructed from
#             the selections made by the user. '''
#         print('%s, %s!' % (self.greetings[self.greeting.currentIndex()].title(),
#                            self.recipient.displayText()))
#
#     def run(self):
#         ''' Run the app and show the main form. '''
#         self.show()
#         self.qt_app.exec_()
#
# app = ExampleApp()
# app.run()



qt_app = QApplication(sys.argv)

class LayoutExample(QWidget):
    ''' An example of PySide absolute positioning; the main window
        inherits from QWidget, a convenient widget for an empty window. '''

    def __init__(self):
        # Initialize the object as a QWidget and
        # set its title and minimum width
        QWidget.__init__(self)
        self.setWindowTitle('Dynamic Greeter')
        self.setMinimumWidth(400)

        # Create the QVBoxLayout that lays out the whole form
        self.layout = QVBoxLayout()

        # Create the form layout that manages the labeled controls
        self.form_layout = QFormLayout()

        self.salutations = ['Ahoy',
                            'Good day',
                            'Hello',
                            'Heyo',
                            'Hi',
                            'Salutations',
                            'Wassup',
                            'Yo']

        # Create and fill the combo box to choose the salutation
        self.salutation = QComboBox(self)
        self.salutation.addItems(self.salutations)
        # Add it to the form layout with a label
        self.form_layout.addRow('&Salutation:', self.salutation)

        # Create the entry control to specify a
        # recipient and set its placeholder text
        self.recipient = QLineEdit(self)
        self.recipient.setPlaceholderText("e.g. 'world' or 'Matey'")

        # Add it to the form layout with a label
        self.form_layout.addRow('&Recipient:', self.recipient)

        # Create and add the label to show the greeting text
        self.greeting = QLabel('', self)
        self.form_layout.addRow('Greeting:', self.greeting)

        # Add the form layout to the main VBox layout
        self.layout.addLayout(self.form_layout)

        # Add stretch to separate the form layout from the button
        self.layout.addStretch(1)

        # Create a horizontal box layout to hold the button
        self.button_box = QHBoxLayout()

        # Add stretch to push the button to the far right
        self.button_box.addStretch(1)

        # Create the build button with its caption
        self.build_button = QPushButton('&Build Greeting', self)

        # Connect the button's clicked signal to show_greeting
        self.build_button.clicked.connect(self.show_greeting)

        # Add it to the button box
        self.button_box.addWidget(self.build_button)

        # Add the button box to the bottom of the main VBox layout
        self.layout.addLayout(self.button_box)

        # Set the VBox layout as the window's main layout
        self.setLayout(self.layout)

    @Slot()
    def show_greeting(self):
        ''' Show the constructed greeting. '''
        self.greeting.setText('%s, %s!' %
                              (self.salutations[self.salutation.currentIndex()],
                               self.recipient.text()))

    def run(self):
        # Show the form
        self.show()
        # Run the qt application
        qt_app.exec_()

# Create an instance of the application window and run it
app = LayoutExample()
app.run()
