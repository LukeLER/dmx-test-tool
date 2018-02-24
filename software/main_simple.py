#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DMX Test Tool

Copyright (C) 2018 Lukas Lauer <lukas@lauersystems.de>

main.py: Entrypoint for this Software

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public
License along with this program; if not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330,
Boston, MA 02111-1307, USA.
"""

import sip
sip.setapi('QString', 2)
sip.setapi('QVariant', 2)

import os
import sys

import math

import time
import signal
import subprocess
import threading
from datetime import datetime

from PyQt4.QtCore import pyqtSignal, Qt, QObject, QTimer, QEvent, QSize, QPoint, QLine
from PyQt4.QtGui import QApplication, QMainWindow, QIcon, QMessageBox, QStyle, \
                        QStyleOptionSlider, QSlider, QFont, QWidget, QImage, QPainter, QPen, QColor, QSpinBox

from tinkerforge.ip_connection import IPConnection
from tinkerforge.bricklet_dmx import BrickletDMX

from ui_mainwindow import Ui_MainWindow

HOST = "localhost"
PORT = 4223

UID_DMX = "Dao"

class MainWindow(QMainWindow, Ui_MainWindow):
    qtcb_ipcon_enumerate = pyqtSignal(str, str, 'char', type((0,)), type((0,)), int, int)
    qtcb_ipcon_connected = pyqtSignal(int)
    qtcb_frame_started = pyqtSignal()
    qtcb_frame = pyqtSignal(object, int)

    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)

        self.setupUi(self)
        self.setWindowTitle('DMX Test Tool by LauerSystems')

        # create and setup ipcon

        self.ipcon = IPConnection()
        self.ipcon.connect(HOST, PORT)
        self.ipcon.register_callback(IPConnection.CALLBACK_ENUMERATE,
                                     self.qtcb_ipcon_enumerate.emit)
        self.ipcon.register_callback(IPConnection.CALLBACK_CONNECTED,
                                     self.qtcb_ipcon_connected.emit)

        self.dmx = BrickletDMX(UID_DMX, self.ipcon)
        self.label_image.setText("Started!")

        #Configs
        self.wait_for_first_read = True
        
        self.qtcb_frame_started.connect(self.cb_frame_started)
        self.qtcb_frame.connect(self.cb_frame)
        
        self.dmx.set_dmx_mode(BrickletDMX.DMX_MODE_MASTER)
        print("DMX Mode [0=Master; 1=Slave]: "+str(self.dmx.get_dmx_mode()))
        self.dmx.set_frame_duration(200)
        print("Frame Duration [ms]: "+str(self.dmx.get_frame_duration()))
        
        self.address_spinboxes = []
        self.address_slider = []
        print("Config Ende")

        for i in range(20):
            spinbox = QSpinBox()
            spinbox.setMinimum(0)
            spinbox.setMaximum(255)
            
            slider = QSlider(Qt.Horizontal)
            slider.setMinimum(0)
            slider.setMaximum(255)

            spinbox.valueChanged.connect(slider.setValue)
            slider.valueChanged.connect(spinbox.setValue)
            
            def get_frame_value_changed_func(i):
                return lambda x: self.frame_value_changed(i, x)
            slider.valueChanged.connect(get_frame_value_changed_func(i))
            
            self.address_table.setCellWidget(i, 0, spinbox)
            self.address_table.setCellWidget(i, 1, slider)
            
            self.address_spinboxes.append(spinbox)
            self.address_slider.append(slider)
            print("Erzeuge Set: "+str(i))

        self.address_table.horizontalHeader().setStretchLastSection(True)
        self.address_table.show()
        
        self.current_frame = [0]*512
        
        print(self.current_frame)
        
        self.dmx.register_callback(self.dmx.CALLBACK_FRAME_STARTED, self.qtcb_frame_started.emit)
        self.dmx.register_callback(self.dmx.CALLBACK_FRAME, self.qtcb_frame.emit)
        self.dmx.set_frame_callback_config(True, False, True, False)

    def frame_value_changed(self, line, value):
        self.current_frame[line] = value
        print("Value Changed")
        print(self.current_frame)
        self.dmx.write_frame(self.current_frame)
        #self.dmx_overview.draw_line(line, value, None, True)
        
    def mode_changed(self, index, update=True):
        if index == 0:
            for spinbox in self.address_spinboxes:
                spinbox.setReadOnly(False)
            for slider in self.address_slider:
                slider.setEnabled(True)
                
            self.frame_duration_label.setVisible(True)
            self.frame_duration_unit.setVisible(True)
            self.frame_duration_spinbox.setVisible(True)
        else:
            for spinbox in self.address_spinboxes:
                spinbox.setReadOnly(True)
            for slider in self.address_slider:
                slider.setEnabled(False)
                
            self.frame_duration_label.setVisible(False)
            self.frame_duration_unit.setVisible(False)
            self.frame_duration_spinbox.setVisible(False)
            
        if update:
            self.dmx.set_dmx_mode(index)
        
    def frame_duration_changed(self, value):
        self.dmx.set_frame_duration(value)
        
    def handle_new_frame(self, frame):
        for i, value in enumerate(frame):
            self.address_spinboxes[i].setValue(value)
            self.frame_value_changed(i, value)
            
        self.wait_for_first_read = False
        
    def cb_get_frame_duration(self, frame_duration):
        self.frame_duration_spinbox.blockSignals(True)
        self.frame_duration_spinbox.setValue(frame_duration)
        self.frame_duration_spinbox.blockSignals(False)
    
    def cb_get_dmx_mode(self, mode):
        self.mode_combobox.blockSignals(True)
        self.mode_combobox.setCurrentIndex(mode)
        self.mode_changed(mode, False)
        self.mode_combobox.blockSignals(False)
        
        if mode == self.dmx.DMX_MODE_MASTER:
            self.dmx.read_frame, None, self.cb_read_frame, self.increase_error_count
        
    def cb_read_frame(self, frame):
        self.handle_new_frame(frame.frame)

    def cb_frame_started(self):
        if not self.wait_for_first_read:
            self.dmx.write_frame, self.current_frame, None, self.increase_error_count
        
    def cb_frame(self, frame, frame_number):
        if frame == None:
            return

        self.handle_new_frame(frame)

    def cb_ipcon_enumerate(self, uid, connected_uid, position,
                           hardware_version, firmware_version,
                           device_identifier, enumeration_type):
        if self.ipcon.get_connection_state() != IPConnection.CONNECTION_STATE_CONNECTED:
            # ignore enumerate callbacks that arrived after the connection got closed
            return

    def cb_ipcon_connected(self, connect_reason):
        try:
            self.ipcon.enumerate()
        except:
            pass

def main():

    os.system('xset s off') # disable screensaver
    os.system('xset -dpms') # disable display power management 
    args = sys.argv

    application = QApplication(args)

    main_window = MainWindow()

    #Show as fullscreen
    if '-fullscreen' in sys.argv:
        main_window.showFullScreen()
    else:
        main_window.show()

    sys.exit(application.exec_())

if __name__ == "__main__":
    main()
