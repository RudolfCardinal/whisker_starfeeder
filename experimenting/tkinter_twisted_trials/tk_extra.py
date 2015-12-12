#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)
from tkinter import *  # noqa
import tkinter.messagebox as messagebox


class Dialog(Toplevel):
    # Adapted from http://effbot.org/tkinterbook/tkinter-dialog-windows.htm
    def __init__(self, parent, title=None, modal=True):
        Toplevel.__init__(self, parent)

        self.parent = parent
        self.modal = modal
        self.result = None

        self.transient(parent)
        if title:
            self.title(title)
        body = Frame(self)
        body.pack(padx=5, pady=5)
        self.buttonbox()

        self.initial_focus = self.body(body)
        if not self.initial_focus:
            self.initial_focus = self

        self.grab_set()  # make modal by redirecting input from others
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.geometry("+%d+%d" % (parent.winfo_rootx() + 50,
                                  parent.winfo_rooty() + 50))
        self.initial_focus.focus_set()
        if self.modal:
            self.wait_window(self)  # wait for the window to be destroyed

    def body(self, master):
        """Create dialog body. Optionally, return widget that should have
        initial focus. This method should be overridden."""
        pass

    def buttonbox(self):
        """Add standard button box. Override if you don't want the standard
        buttons."""
        box = Frame(self)
        if self.modal:
            w = Button(box, text="OK", width=10, command=self.ok,
                       default=ACTIVE)
            w.pack(side=LEFT, padx=5, pady=5)
        w = Button(box, text="Cancel", width=10, command=self.cancel)
        w.pack(side=LEFT, padx=5, pady=5)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        box.pack()

    def ok(self, event=None):
        if not self.validate():
            self.initial_focus.focus_set()  # put focus back
            return
        self.withdraw()
        self.update_idletasks()
        self.apply()
        self.cancel()

    def cancel(self, event=None):
        # put focus back to the parent window
        self.parent.focus_set()
        self.destroy()

    def validate(self):
        """Override. Return True if OK. Return False (and tell user) if not."""
        return True  # OK

    def apply(self):
        """Override this."""
        pass


class MyDialog(Dialog):
    def body(self, master):
        Label(master, text="First:").grid(row=0, sticky="E")
        Label(master, text="Second:").grid(row=1, sticky="E")
        self.e1 = Entry(master)
        self.e1.grid(row=0, column=1, sticky="W")
        self.e2 = Entry(master)
        self.e2.grid(row=1, column=1, sticky="W")
        return self.e1  # initial focus

    def validate(self):
        try:
            first = int(self.e1.get())
            second = int(self.e2.get())
            self.result = first, second
            return True
        except ValueError:
            messagebox.showwarning(
                "Bad input",
                "Illegal values, please try again"
            )
            return False

    def apply(self):
        first = int(self.e1.get())
        second = int(self.e2.get())
        self.result = first, second
