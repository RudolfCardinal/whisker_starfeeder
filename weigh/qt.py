#!/usr/bin/env python3
# weigh/qt.py

from collections import Counter
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
import threading

from PySide.QtCore import (
    Signal,
    Slot,
    QAbstractListModel,
    QModelIndex,
    Qt,
    # QVariant,  # non-existent in PySide?
)
from PySide.QtGui import (
    QAbstractItemView,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QItemSelection,
    QItemSelectionModel,
    QListView,
    QMessageBox,
    QRadioButton,
    QVBoxLayout,
)

from weigh.lang import get_caller_name


# =============================================================================
# Constants
# =============================================================================

NOTHING_SELECTED = -1  # e.g. http://doc.qt.io/qt-4.8/qbuttongroup.html#id


# =============================================================================
# Helper functions
# =============================================================================

def reversedict(d):
    return {v: k for k, v in d.items()}


def contains_duplicates(values):
    return [k for k, v in Counter(values).items() if v > 1]


# =============================================================================
# Exceptions
# =============================================================================

class ValidationError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

    def __str__(self):
        return self.message


class EditCancelledException(Exception):
    pass


# =============================================================================
# StatusMixin - emit status to logger and Qt signals
# =============================================================================

class StatusMixin(object):
    """
    Add this to a QObject to provide easy Python logging and Qt signal-based
    status/error messaging.

    Uses the same function names as Python logging, for predictability.
    """
    status_sent = Signal(str, str)
    error_sent = Signal(str, str)

    def __init__(self, name, logger, thread_info=True, caller_info=True):
        # Somewhat verbose names to make conflict with a user class unlikely.
        self._statusmixin_name = name
        self._statusmixin_logger = logger
        self._statusmixin_debug_thread_info = thread_info
        self._statusmixin_debug_caller_info = caller_info

    def _process_status_message(self, msg):
        callerinfo = ''
        if self._statusmixin_debug_caller_info:
            callerinfo = "{}:".format(get_caller_name(back=1))
        threadinfo = ''
        if self._statusmixin_debug_thread_info:
            # msg += (
            #     " [QThread={}, name={}, ident={}]".format(
            #         QThread.currentThread(),
            #         # int(QThread.currentThreadId()),
            #         threading.current_thread().name,
            #         threading.current_thread().ident,
            #     )
            # )
            threadinfo = " [thread {}]".format(threading.current_thread().name)
        return "{}:{} {}{}".format(self._statusmixin_name, callerinfo, msg,
                                   threadinfo)

    def debug(self, msg):
        self._statusmixin_logger.debug(self._process_status_message(msg))

    def error(self, msg):
        self._statusmixin_logger.error(self._process_status_message(msg))
        self.error_sent.emit(msg, self._statusmixin_name)

    def warning(self, msg):
        # warn() is deprecated; use warning()
        self._statusmixin_logger.warning(self._process_status_message(msg))
        self.error_sent.emit(msg, self._statusmixin_name)

    def info(self, msg):
        self._statusmixin_logger.info(self._process_status_message(msg))
        self.status_sent.emit(msg, self._statusmixin_name)

    def status(self, msg):
        # Don't just call info, because of the stack-counting thing
        # in _process_status_message
        self._statusmixin_logger.info(self._process_status_message(msg))
        self.status_sent.emit(msg, self._statusmixin_name)


# =============================================================================
# Framework for a config-editing dialogue
# =============================================================================

class TransactionalEditDialogMixin(object):
    """
    Mixin for a config-editing dialogue.
    Wraps the editing in a SAVEPOINT transaction.
    The caller must still commit() afterwards, but any rollbacks are automatic.
    """
    ok = Signal()

    def __init__(self, session, obj, layout, readonly=False):
        # Store variables
        self.obj = obj
        self.session = session

        # Add OK/cancel buttons to layout thus far
        if readonly:
            ok_cancel_buttons = QDialogButtonBox(
                QDialogButtonBox.Cancel,
                Qt.Horizontal,
                self)
            ok_cancel_buttons.rejected.connect(self.reject)
        else:
            ok_cancel_buttons = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                Qt.Horizontal,
                self)
            ok_cancel_buttons.accepted.connect(self.ok_clicked)
            ok_cancel_buttons.rejected.connect(self.reject)

        # Build overall layout
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(layout)
        main_layout.addWidget(ok_cancel_buttons)

        # Pass in data
        self.object_to_dialog(self.obj)

    @Slot()
    def ok_clicked(self):
        try:
            self.dialog_to_object(self.obj)
            self.accept()
        except Exception as e:
            QMessageBox.about(self, "Invalid data", str(e))
            # ... str(e) will be a simple message for ValidationError

    def edit_in_nested_transaction(self):
        """
        Pops up the dialog, allowing editing.
        - Does so within a database transaction.
        - If the user clicks OK *and* the data validates, commits the
          transaction.
        - If the user cancels, rolls back the transaction.
        - We want it nestable, so that the config dialog box can edit part of
          the config, reversibly, without too much faffing around.
        """
        """
        - We could nest using SQLAlchemy's support for nested transactions,
          which works whether or not the database itself supports nested
          transactions via the SAVEPOINT method.
        - With sessions, one must use autocommit=True and the subtransactions
          flag; these are virtual transactions handled by SQLAlchemy.
        - Alternatively one can use begin_nested() or begin(nested=True), which
          uses SAVEPOINT.
        - The following databases support the SAVEPOINT method:
            MySQL with InnoDB
            SQLite, from v3.6.8 (2009)
            PostgreSQL
        - Which is better? The author suggests SAVEPOINT for most applications.
          https://groups.google.com/forum/#!msg/sqlalchemy/CaZyyMx7_8Y/otM0BzDyaigJ  # noqa
          ... including, for subtransactions: "When a rollback is issued, the
          subtransaction will directly roll back the innermost real
          transaction, however each subtransaction still must be explicitly
          rolled back to maintain proper stacking of subtransactions."
          ... i.e. it's not as simple as you might guess.
        - See
          http://docs.sqlalchemy.org/en/latest/core/connections.html
          http://docs.sqlalchemy.org/en/latest/orm/session_transaction.html
          http://stackoverflow.com/questions/2336950/transaction-within-transaction  # noqa
          http://stackoverflow.com/questions/1306869/are-nested-transactions-allowed-in-mysql  # noqa
          https://en.wikipedia.org/wiki/Savepoint
          http://www.sqlite.org/lang_savepoint.html
          http://stackoverflow.com/questions/1654857/nested-transactions-with-sqlalchemy-and-sqlite  # noqa

        - Let's use the SAVEPOINT technique.

        - No. Even this fails:

        with self.session.begin_nested():
            self.config.port = 5000

        - We were aiming for this:

        try:
            with self.session.begin_nested():
                result = self.exec_()  # enforces modal
                if result == QDialog.Accepted:
                    logger.debug("Config changes accepted;  will be committed")
                else:
                    logger.debug("Config changes cancelled")
                    raise EditCancelledException()
        except EditCancelledException:
            logger.debug("Config changes rolled back.")
        except:
            logger.debug("Exception within nested transaction. "
                         "Config changes will be rolled back.")
            raise
            # Other exceptions will be handled as normal.

        - No... the commit fails, and this SQL is emitted:
            SAVEPOINT sa_savepoint_1
            UPDATE table SET field=?
            RELEASE SAVEPOINT sa_savepoint_1  -- sensible
            ROLLBACK TO SAVEPOINT sa_savepoint_1  -- not sensible
            -- raises sqlite3.OperationalError: no such savepoint: sa_savepoint_1  # noqa

        - May be this bug:
            https://www.mail-archive.com/sqlalchemy@googlegroups.com/msg28381.html  # noqa
            http://bugs.python.org/issue10740
            https://groups.google.com/forum/#!topic/sqlalchemy/1QelhQ19QsE

        - The bugs are detailed in sqlalchemy/dialects/sqlite/pysqlite.py; see
          "Serializable isolation / Savepoints / Transactional DDL"

        - We work around it by adding hooks to the engine as per that advice;
          see db.py

        """
        # A context manager provides cleaner error handling than explicit
        # begin_session() / commit() / rollback() calls.
        # The context manager provided by begin_nested() will commit, or roll
        # back on an exception.
        try:
            with self.session.begin_nested():
                result = self.exec_()  # enforces modal
                if result == QDialog.Accepted:
                    return result
                else:
                    raise EditCancelledException()
        except EditCancelledException:
            logger.debug("Dialog changes will be rolled back.")
            return result
            # ... and swallow that exception silently.
        # Other exceptions will be handled as normal.

        # NOTE that this releases a savepoint but does not commit() the main
        # session; the caller must still do that.


# =============================================================================
# Framework for list boxes
# =============================================================================


# For stuff where we want to display a list (e.g. of strings) and edit items
# with a dialog:
# - view is a QListView (itself a subclass of QAbstractItemView):
#   ... or perhaps QAbstractItemView directly
#   http://doc.qt.io/qt-5/qlistview.html#details
#   http://doc.qt.io/qt-4.8/qabstractitemview.html
# - model is perhaps a subclass of QAbstractListModel:
#   http://doc.qt.io/qt-5/qabstractlistmodel.html#details
#
# Custom editing:
# - ?change the delegate?
#   http://www.saltycrane.com/blog/2008/01/pyqt4-qitemdelegate-example-with/
#   ... no, can't be a modal dialog
#       http://stackoverflow.com/questions/27180602
#       https://bugreports.qt.io/browse/QTBUG-11908
# - ?override the edit function of the view?
#   http://stackoverflow.com/questions/27180602
#   - the edit function is part of QAbstractItemView
#     http://doc.qt.io/qt-4.8/qabstractitemview.html#public-slots
#   - but then, with the index (which is a QModelIndex, not an integer), we
#     have to fetch the model with self.model(), then operate on it somehow;
#     noting that a QModelIndex fetches the data from its model using the
#     data() function, which we are likely to have bastardized to fit into a
#     string. So this is all a bit convoluted.
#   - Ah! Not if we use row() then access the raw data directly from our mdoel.


class GenericListModel(QAbstractListModel):
    """
    Takes a list and provides a view on it using str().
    Note that it MODIFIED THE LIST PASSED TO IT.
    """
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.listdata = data

    def rowCount(self, parent=QModelIndex()):
        """Qt override."""
        return len(self.listdata)

    def data(self, index, role):
        """Qt override."""
        if index.isValid() and role == Qt.DisplayRole:
            return str(self.listdata[index.row()])
        return None

    def item_deletable(self, rowindex):
        return True


class ModalEditListView(QListView):
    selection_changed = Signal(QItemSelection, QItemSelection)
    # ... selected (set), deselected (set)
    selected_maydelete = Signal(bool, bool)
    # ... selected

    def __init__(self, session, modal_dialog_class, *args, **kwargs):
        super().__init__(*args)
        self.readonly = kwargs.pop('readonly', False)
        self.modal_dialog_class = modal_dialog_class
        self.session = session
        # self.setEditTriggers(QAbstractItemView.DoubleClicked)
        # ... probably only relevant if we do NOT override edit().
        # Being able to select a single row is the default.
        # Otherwise see SelectionBehavior and SelectionMode.
        self.selection_model = None

    def edit(self, index, trigger, event):
        if trigger != QAbstractItemView.DoubleClicked:
            return False
        self.edit_by_modelindex(index)
        return False

    def edit_by_modelindex(self, index):
        if index is None:
            return
        model = self.model()
        item = model.listdata[index.row()]
        win = self.modal_dialog_class(self.session, item,
                                      readonly=self.readonly)
        win.edit_in_nested_transaction()

    def insert_at_index(self, object, index=None):
        # index: None for end, 0 for start
        model = self.model()
        if index is None:
            index = len(model.listdata)
        if index < 0 or index > len(model.listdata):
            raise ValueError("Bad index")
        # http://stackoverflow.com/questions/4702972
        model.beginInsertRows(QModelIndex(), 0, 0)
        model.listdata.insert(index, object)
        model.endInsertRows()
        self.go_to(index)

    def insert_at_start(self, object):
        self.insert_at_index(object, 0)

    def insert_at_end(self, object):
        self.insert_at_index(object, None)

    def get_selected_modelindex(self):
        """Returns a QModelIndex or None."""
        selected_indexes = self.selectedIndexes()
        if not selected_indexes or len(selected_indexes) > 1:
            logger.warning("get_selected_modelindex: 0 or >1 selected")
            return None
        return selected_indexes[0]

    def get_selected_row_index(self):
        """Returns an integer or None."""
        selected_modelindex = self.get_selected_modelindex()
        return selected_modelindex.row()

    def remove_selected(self):
        row_index = self.get_selected_row_index()
        self.remove_by_index(row_index)

    def remove_by_index(self, row_index):
        if row_index is None:
            return
        model = self.model()
        if row_index < 0 or row_index > len(model.listdata):
            raise ValueError("Invalid index {}".format(row_index))
        model.beginRemoveRows(QModelIndex(), row_index, row_index)
        del model.listdata[row_index]
        model.endRemoveRows()

    def edit_selected(self):
        selected_modelindex = self.get_selected_modelindex()
        self.edit_by_modelindex(selected_modelindex)

    def edit_by_index(self, row_index):
        if row_index is None:
            return
        model = self.model()
        if row_index < 0 or row_index > len(model.listdata):
            raise ValueError("Invalid index {}".format(row_index))
        model.beginRemoveRows(QModelIndex(), row_index, row_index)
        del model.listdata[row_index]
        model.endRemoveRows()

    def go_to(self, index):
        model = self.model()
        modelindex = model.index(index)
        self.setCurrentIndex(modelindex)

    def setModel(self, model):
        if self.selection_model:
            self.selection_model.selectionChanged.disconnect()
        super().setModel(model)
        self.selection_model = QItemSelectionModel(model)
        self.selection_model.selectionChanged.connect(self._selection_changed)
        self.setSelectionModel(self.selection_model)

    def _selection_changed(self, selected, deselected):
        self.selection_changed.emit(selected, deselected)
        selected_model_indexes = selected.indexes()
        selected_row_indexes = [mi.row() for mi in selected_model_indexes]
        is_selected = bool(selected_row_indexes)
        model = self.model()
        may_delete = is_selected and all([model.item_deletable(ri)
                                          for ri in selected_row_indexes])
        self.selected_maydelete.emit(is_selected, may_delete)

    def add_in_nested_transaction(self, new_object, at_index=None):
        # at_index: None for end, 0 for start
        try:
            with self.session.begin_nested():
                self.session.add(new_object)
                win = self.modal_dialog_class(self.session, new_object)
                result = win.edit_in_nested_transaction()
                if result != QDialog.Accepted:
                    raise EditCancelledException()
                self.insert_at_index(new_object, at_index)
                return result
        except EditCancelledException:
            logger.debug("Add operation will be rolled back.")
            return result


# =============================================================================
# Framework for radio buttons
# =============================================================================

class RadioGroup(object):
    def __init__(self, value_text_tuples, default=None):
        # There's no reason for the caller to care about the internal IDs
        # we use. So let's make them up here as positive integers.
        self.default_value = default
        if not value_text_tuples:
            raise ValueError("No values passed to RadioGroup")
        if contains_duplicates([x[0] for x in value_text_tuples]):
            raise ValueError("Duplicate values passed to RadioGroup")
        possible_values = [x[0] for x in value_text_tuples]
        if self.default_value not in possible_values:
            self.default_value = possible_values[0]
        self.bg = QButtonGroup()  # exclusive by default
        self.buttons = []
        self.map_id_to_value = {}
        self.map_value_to_button = {}
        for i, (value, text) in enumerate(value_text_tuples):
            id = i + 1  # start with 1
            button = QRadioButton(text)
            self.bg.addButton(button, id)
            self.buttons.append(button)
            self.map_id_to_value[id] = value
            self.map_value_to_button[value] = button

    def get_value(self):
        buttongroup_id = self.bg.checkedId()
        if buttongroup_id == NOTHING_SELECTED:
            return None
        return self.map_id_to_value[buttongroup_id]

    def set_value(self, value):
        if value not in self.map_value_to_button:
            value = self.default_value
        button = self.map_value_to_button[value]
        button.setChecked(True)

    def add_buttons_to_layout(self, layout):
        for button in self.buttons:
            layout.addWidget(button)
