#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)
import tkinter as tk
from tkinter import filedialog as tkFileDialog
# from tkinter.filedialog import askopenfilename
from twisted.internet import reactor, task
from weigh.tk_extra import MyDialog
from weigh.twisted_py3_tksupport import install, uninstall
from weigh.task import WeighTask


class MainWindow():
    def __init__(self, session):
        self.session = session  # SQLAlchemy session
        self.root = tk.Tk()  # tkinter root window
        self.hidden = tk.Toplevel()
        self.task = WeighTask(self)  # Whisker task using twisted
        self.running = False

        install(self.root)  # install Twisted support for tkinter
        self.hidden.withdraw()

        self.root.title("Whisker Weighbridge")
        self.root.geometry("500x400")
        tk.Button(self.root, text="Test dialog",
                  command=lambda: self.test_dialog()).pack()
        tk.Button(self.root, text="Open file",
                  command=lambda: self.open_file()).pack()
        tk.Button(self.root, text="Connect",
                  command=lambda: self.connect()).pack()
        tk.Button(self.root, text="Quit",
                  command=lambda: self.quit()).pack()

        self.looper = task.LoopingCall(lambda: self.tick())
        self.looper.start(1.0)
        reactor.run()

    def tick(self):
        logger.info("tick {}".format("running" if self.running else ""))

    def test_dialog(self):
        if not self.running:
            d = MyDialog(self.root)
            logger.info("DIALOGUE RESULT: {}".format(d.result))
        else:
            MyDialog(self.root, modal=False)

    def open_file(self):
        # filename = askopenfilename()
        tkFileDialog.Open(parent=self.hidden).show()
        logger.info("Filename: {}".format(filename))

    def quit(self):
        uninstall()  # close down Twisted support
        self.root.destroy()
        reactor.stop()

    def connect(self):
        self.running = True
        self.task.connect("wombatvmxp", 3233)

    def task_ended(self):
        logger.debug("Task ended.")
        self.quit()

    def mainloop(self):
        ouch
