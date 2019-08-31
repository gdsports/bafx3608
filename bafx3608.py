#!/usr/bin/python3
"""
Many thanks for inspiration from https://github.com/ciembor/gm1356

Example of reading from a BAFX3608 Sound Pressure Level meter connected via USB to
a Raspberry Pi running Raspbian. The GM1356 meter appears to be identical except
for case color and brand name.

$ sudo apt update
$ sudo apt install python3-libusb1

Create a file named /etc/udev/rules.d/99-bafxspl.rules
$ sudo echo 'SUBSYSTEMS=="usb",ATTRS{idProduct}=="74e3",ATTRS{idVendor}=="64bd",\
  GROUP="plugdev",MODE="0666"' >/etc/udev/rules.d/99-bafxspl.rules
Activate the new udev rule.
$ sudo udevadm control --reload
Connect the meter. If the meter is plugged in, unplug then plug in.

Once this program is displaying dB values do something interesting such as
MQTT publish, database insert, HTTP POST, etc.

Make a loudness or applause meter by flashing an RGB LED string or grid based
the dB value.
#######################################################################
MIT License

Copyright (c) 2019 gdsports625@gmail.com

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
#######################################################################
"""
import time
import sys
import struct
import getopt
import threading
import usb1

class Bafx3608:
    """BAFX3608 Sound Pressure Level meter USB driver"""
    USBVendorID = 0x64bd
    USBProductID = 0x74e3
    OUT_ENDPOINT = 0x02
    IN_ENDPOINT = 0x81

    RANGE = ['30-130', '30-80', '50-100', '60-110', '80-130', 'invalid', 'invalid', 'invalid']
    WEIGHT = ['A', 'C']
    MAXMODE = ['   ', 'Max']
    FASTMODE = ['Slow', 'Fast']

    def __init__(self, fast=True, maxmode=False, weightC=False, dBrange=0):
        self.options = (fast << 6) | (maxmode << 5) | (weightC << 4) | dBrange
        self.thread_id = -1
        self.cb_on_reading = None
        self.cb_on_reading_str = None
        self.cb_on_reading_raw = None
        self.handle = None

    def set_config_usb(self):
        """
        set_config_usb() writes BAFX3600 meter options over USB
        """
        # Write meter options
        command = bytearray([0x56, self.options, 0, 0, 0, 0, 0, 0])
        while True:
            try:
                self.handle.interruptWrite(Bafx3608.OUT_ENDPOINT, command, 10)
                break
            except usb1.USBErrorTimeout:
                pass

    def set_config(self, fast=True, maxmode=False, weight_c=False, db_range=0):
        """
        set_config(fast=True, maxmode=False, bool weight_c=False, db_range=0)
        """
        self.options = (fast << 6) | (maxmode << 5) | (weight_c << 4) | db_range
        self.set_config_usb()

    def get_config(self):
        """
        get_config() return BAFX3608 options as bitmap
        """
        return self.options

    def loop_start(self):
        """
        Start thread reading from meter
        """
        if self.thread_id == -1:
            self.thread_id = threading.Thread(target=self.usb_poll_thread)
            self.thread_id.start()

    def loop_forever(self):
        """
        Read from meter blocking. Does not return.
        """
        self.usb_poll_thread()

    def _eval_data(self, usbdata, fast_mode):
        if usbdata is not None and len(usbdata) > 2:
            decibels, options = struct.unpack_from('>HB', usbdata)
            decibels = decibels / 10
            if decibels <= 130.0:
                fast_mode = (options & (1<<6)) != 0
                max_mode = (options & (1<<5)) != 0
                ac_mode = (options & (1<<4)) != 0
                inrange = options & 0x07
                if self.cb_on_reading_raw is not None:
                    self.cb_on_reading_raw(usbdata[:3])
                if self.cb_on_reading is not None:
                    self.cb_on_reading(decibels, fast_mode, max_mode, ac_mode,\
                            inrange)
                if self.cb_on_reading_str is not None:
                    db_str = f"{decibels:5.1f}"
                    fast_mode_str = f"{self.FASTMODE[fast_mode]}"
                    max_mode_str = f"{self.MAXMODE[max_mode]}"
                    self.cb_on_reading_str(db_str, fast_mode_str, max_mode_str, \
                            f"{self.WEIGHT[ac_mode]}", f"{self.RANGE[inrange]}")
        return fast_mode

    def usb_poll_thread(self):
        """
        Meter reading thread
        """
        self.handle = usb1.USBContext().openByVendorIDAndProductID(
            Bafx3608.USBVendorID,
            Bafx3608.USBProductID,
            skip_on_error=True,
            )
        if self.handle is None:
            # Device not present, or user is not allowed to access device.
            print('Device not present')
            sys.exit(1)
        if self.handle.kernelDriverActive(0):
            self.handle.detachKernelDriver(0)
        self.handle.claimInterface(0)

        try:
            self.set_config_usb()

            # Read sound levels from meter
            command = bytearray([0xb3, 0xaa, 0xbb, 0xcc, 0x00, 0x00, 0x00, 0x00])
            fast_mode = True
            while True:
                try:
                    self.handle.interruptWrite(Bafx3608.OUT_ENDPOINT, command, 20)
                    data = self.handle.interruptRead(Bafx3608.IN_ENDPOINT, 8, 10)
                    fast_mode = self._eval_data(data, fast_mode)
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
                self.handle.releaseInterface(0)
                self.handle.close()
            except usb1.USBErrorNoDevice:
                pass

def main():
    """
    main program
    """
    help_cli = f'{sys.argv[0]} --range=[0..4] --fast=[0,1] --max=[0,1] --weight=[A,C]'

    out_range = 0
    out_fast = 1
    out_weight = 0
    out_max = 0

    try:
        opts, _args = getopt.getopt(sys.argv[1:], '', ['range=', 'fast=', 'weight=', 'max='])
    except getopt.GetoptError:
        print(help_cli)
        sys.exit(2)
    try:
        for opt, arg in opts:
            if opt == '--range':
                out_range = int(arg) & 0x07
            elif opt == '--fast':
                out_fast = int(arg) & 0x01
            elif opt == '--weight':
                out_weight = 0
                if arg in ('C', 'c'):
                    out_weight = 1
            elif opt == '--max':
                out_max = int(arg) & 0x01
    except ValueError:
        print(help_cli)
        sys.exit(2)

    def reading_callback_str(decibels, _fast, maxmode, weight_c, db_range):
        """
        callback
        """
        print(decibels, "dB" + weight_c, maxmode, db_range)

    meter = Bafx3608(out_fast, out_max, out_weight, out_range)

    meter.cb_on_reading_str = reading_callback_str
    meter.cb_on_reading = None
    meter.cb_on_reading_raw = None
    meter.loop_forever()

if __name__ == "__main__":
    main()
