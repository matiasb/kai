# *-* coding: UTF-8 *-*
import re

from functools import wraps

from PyQt4 import QtGui, QtCore
from PyQt4.Qt import QObject

from ninja_ide.core import plugin


STYLES = """
QListView {
    border: 1px solid #1e1e1e;
}
"""


class DocumentCompleter(QtGui.QCompleter):
    """StringList Simple Completer."""

    def __init__(self, parent=None):
        words = []
        QtGui.QCompleter.__init__(self, words, parent)
        self.popup().setAlternatingRowColors(True)
        self.popup().setStyleSheet(STYLES)


class Autocompleter(plugin.Plugin):
    """Simple Autocompleter plugin."""
    # end of word
    eow = "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-="

    def initialize(self):
        """Ninja-ide plugin initializer."""
        self.editor_s = self.locator.get_service('editor')
        tab_manager = self.editor_s._main.actualTab

        self.completer = DocumentCompleter()
        # to-do: make these configurable settings
        self.completer.setCompletionMode(QtGui.QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseSensitive)

        # init current tabs, if any
        for i in xrange(tab_manager.count()):
            editor = tab_manager.widget(i)
            self._add_completer(editor)

        # set completer for current tab
        editor = self.editor_s.get_editor()
        if editor is not None:
            self.completer.setWidget(editor)

        # on file open, init completer
        self.editor_s.fileOpened.connect(self._set_completer_on_open)

        # on key press, check to show completer
        self.editor_s.editorKeyPressEvent.connect(self.key_press)

        # on tab change, update completer
        self.editor_s.currentTabChanged.connect(self._set_completer)

        QObject.connect(self.completer,
            QtCore.SIGNAL("activated(const QString&)"), self.insert_completion)

    def _set_completer(self, filename):
        """Set completer widget to current tab editor."""
        editor = self.editor_s.get_editor()
        self.completer.setWidget(editor)

    def _set_completer_on_open(self, filename):
        """Set completer widget to new tab (on open) editor."""
        editor = self.editor_s.get_editor()
        self._add_completer(editor)
        self.completer.setWidget(editor)

    def _add_completer(self, editor):
        """Set up completer for the editor."""
        if getattr(editor, '_autocompleter_set', False):
            return

        # HACK: decorator to avoid editor keypress when activating completion
        def check_completer_activation(completer, function):
            @wraps(function)
            def _inner(event):
                if completer and completer.popup().isVisible():
                    if event.key() in (
                            QtCore.Qt.Key_Enter,
                            QtCore.Qt.Key_Return,
                            QtCore.Qt.Key_Escape,
                            QtCore.Qt.Key_Tab,
                            QtCore.Qt.Key_Backtab):
                        event.ignore()
                        return
                return function(event)
            return _inner

        editor.keyPressEvent = check_completer_activation(self.completer,
                                                          editor.keyPressEvent)
        editor._autocompleter_set = True

    def update_model(self):
        """Update StringList alternatives for the completer."""
        data = self.editor_s.get_text()
        current = self.text_under_cursor()
        words = set(re.split('\W+', data))
        if current in words:
            words.remove(current)
        self.completer.model().setStringList(sorted(words))

    def insert_completion(self, completion):
        """Insert chosen completion."""
        editor = self.editor_s.get_editor()
        tc = editor.textCursor()
        extra = len(self.completer.completionPrefix())
        tc.movePosition(QtGui.QTextCursor.Left)
        tc.movePosition(QtGui.QTextCursor.EndOfWord)
        tc.insertText(completion[extra:])
        editor.setTextCursor(tc)

    def text_under_cursor(self):
        """Return the word under the cursor for possible completion search."""
        editor = self.editor_s.get_editor()
        if editor is not None:
            tc = editor.textCursor()
            tc.select(QtGui.QTextCursor.WordUnderCursor)
            prefix = tc.selectedText()
            if prefix and prefix[0] in self.eow:
                tc.movePosition(QtGui.QTextCursor.WordLeft, n=2)
                tc.select(QtGui.QTextCursor.WordUnderCursor)
                prefix = tc.selectedText()
            return prefix
        return None

    def key_press(self, event):
        """Check for completer activation."""
        completionPrefix = self.text_under_cursor()

        if completionPrefix is None:
            return

        is_shortcut = (event.modifiers() == QtCore.Qt.ControlModifier and
                       event.key() == QtCore.Qt.Key_Space)

        # to-do: make prefix length to show completer a setting
        should_hide = not event.text() or len(completionPrefix) < 3
        if not is_shortcut and should_hide:
            self.completer.popup().hide()
            return
        else:
            self.update_model()

        if (completionPrefix != self.completer.completionPrefix()):
            self.completer.setCompletionPrefix(completionPrefix)
            popup = self.completer.popup()
            popup.setCurrentIndex(
                self.completer.completionModel().index(0, 0))

        editor = self.editor_s.get_editor()
        # HACK: need signal/hook for splits from ninja
        if self.completer.widget() != editor:
            self.completer.setWidget(editor)
        cr = editor.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0)
            + self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)

    def finish(self):
        """Shutdown the plugin."""

    def get_preferences_widget(self):
        """Return a widget for customize yor plugin."""
