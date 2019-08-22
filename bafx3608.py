#!/usr/bin/python3
#
# Many thanks for inspiration from https://github.com/ciembor/gm1356
#
# Example of reading from a BAFX3608 Sound Pressure Level meter connected via USB to
# a Raspberry Pi running Raspbian. The GM1356 meter appears to be identical except
# for case color and brand name.
#
# $ sudo apt update
# $ sudo apt install python3-libusb1
#
# Create a file named /etc/udev/rules.d/99-bafxspl.rules
# $ sudo echo 'SUBSYSTEMS=="usb",ATTRS{idProduct}=="74e3",ATTRS{idVendor}=="64bd",GROUP="plugdev",MODE="0666"' >/etc/udev/rules.d/99-bafxspl.rules
# Activate the new udev rule.
# $ sudo udevadm control --reload
# Connect the meter. If the meter is plugged in, unplug then plug in.
#
# Once this program is displaying dB values do something interesting such as
# MQTT publish, database insert, HTTP POST, etc.
#
# Make a loudness or applause meter by flashing an RGB LED string or grid based
# the dB value.
#########################################################################
# MIT License
#
# Copyright (c) 2019 gdsports625@gmail.com
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#########################################################################

import usb1
import time
import sys
import getopt
import struct

USBVendorID=0x64bd
USBProductID=0x74e3
OUT_ENDPOINT=0x02
IN_ENDPOINT=0x81
RANGE=['30-130', '30-80', '50-100', '60-110', '80-130', 'invalid', 'invalid', 'invalid']
WEIGHT=['A', 'C']
MAXMODE=['   ', 'Max']
HELP=f'{sys.argv[0]} --range=[0..4] --fast=[0,1] --max=[0,1] --weight=[A,C]'

outRange = 0
outFast = 1
outWeight = 0
outMax = 0

try:
    opts, args = getopt.getopt(sys.argv[1:], '', ['range=','fast=','weight=','max='])
except getopt.GetoptError:
    print(HELP)
    sys.exit(2)
try:
    for opt, arg in opts:
        if opt == '--range':
            outRange = int(arg) & 0x07;
        elif opt == '--fast':
            outFast = int(arg) & 0x01;
        elif opt == '--weight':
            outWeight = 0
            if arg in ('C', 'c'):
                outWeight = 1
        elif opt == '--max':
            outMax = int(arg) & 0x01;
except ValueError:
    print(HELP)
    sys.exit(2)

with usb1.USBContext() as context:
    handle = context.openByVendorIDAndProductID(
            USBVendorID,
            USBProductID,
            skip_on_error=True,
            )
    if handle is None:
        # Device not present, or user is not allowed to access device.
        print('Device not present')
        sys.exit(1)
    kernelDriver = handle.kernelDriverActive(0)
    if kernelDriver:
        handle.detachKernelDriver(0)
    handle.claimInterface(0)

    try:
        # Write meter options
        options = (outFast << 6) | (outMax << 5) | (outWeight << 4) | outRange
        command = bytearray([0x56, options, 0, 0, 0, 0, 0, 0])
        while True:
            try:
                handle.interruptWrite(OUT_ENDPOINT, command, 10)
                break
            except usb1.USBErrorTimeout:
                pass

        # Read sound levels from meter
        command = bytearray([0xb3, 0xaa, 0xbb, 0xcc, 0x00, 0x00, 0x00, 0x00])
        fast_mode = True
        max_mode = False
        ac_mode = False
        while True:
            try:
                handle.interruptWrite(OUT_ENDPOINT, command, 20)
                data = handle.interruptRead(IN_ENDPOINT, 8, 10)
                if data is not None:
                    if len(data) > 2:
                        dB, options = struct.unpack_from('>HB', data)
                        dB = dB / 10
                        if dB <= 130.0:
                            fast_mode = (options & (1<<6)) != 0
                            max_mode  = (options & (1<<5)) != 0
                            ac_mode   = (options & (1<<4)) != 0
                            inrange = options & 0x07
                            print(f"{dB:5.1f} dB{WEIGHT[ac_mode]} {MAXMODE[max_mode]} {RANGE[inrange]}")
                            # Insert interesting IOT actions of your choice such as
                            # MQTT publish, database insert, HTTP POST, etc.
            except usb1.USBErrorTimeout:
                pass
            except usb1.USBErrorOverflow:
                pass
            except usb1.USBErrorPipe:
                pass
            except usb1.USBErrorNoDevice:
                break
            if fast_mode:
                time.sleep(0.250)
            else:
                time.sleep(1.0)
    finally:
        try:
            handle.releaseInterface(0)
            handle.close()
        except usb1.USBErrorNoDevice:
            pass
