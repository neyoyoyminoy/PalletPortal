'''
this is the mode select screen that i have from my GUIv037

it is making the colors consistent with the new colors of blue, red, magenta
'''

import os, re, sys, time
from pathlib import Path
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QStackedWidget, QTextEdit, QListWidget, QListWidgetItem
import spidev
import sys

class MenuScreen(QWidget):
    shipSelected=pyqtSignal(); viewOrderSelected=pyqtSignal()
    def __init__(self):
        super().__init__(); self.setFocusPolicy(Qt.StrongFocus)
        self.opts=["Ship","View Order"]; self.idx=0
        lay=QVBoxLayout(self)
        #t=QLabel("Select "); t.setAlignment(Qt.AlignCenter); t.setFont(QFont("Arial",36)) #title font
        #t.setStyleSheet("color:#0c2340;background-color:#f15a22;font-weight:bold;"); lay.addWidget(t)
        self.top=QLabel(self.opts[0]); self.bot=QLabel(self.opts[1])
        for l in(self.top,self.bot): l.setAlignment(Qt.AlignCenter); l.setFont(QFont("Arial",32)); l.setMargin(12); lay.addWidget(l)
        self._refresh()
    def _refresh(self):
        sel="border:4px solid #000000;border-radius:16px;"; norm="border:none;" #selection outline/border; border is black in hex and 16 pixels wide
        self.top.setStyleSheet(sel if self.idx==0 else norm)
        self.bot.setStyleSheet(sel if self.idx==1 else norm)
    def keyPressEvent(self,e):
        k=e.key()
        if k in(Qt.Key_Return,Qt.Key_Enter): self.idx=(self.idx-1)%2; self._refresh(); e.accept(); return
        if k==Qt.Key_Control: self.idx=(self.idx+1)%2; self._refresh(); e.accept(); return
        if k==Qt.Key_V:
            (self.shipSelected if self.idx==0 else self.viewOrderSelected).emit(); e.accept(); return
        super().keyPressEvent(e)
