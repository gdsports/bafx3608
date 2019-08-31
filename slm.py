#!/usr/bin/python3
"""
MQTT subscribe to BAFX3608 readings.
"""
import struct
import paho.mqtt.client as mqtt

RANGE = ['30-130', '30-80', '50-100', '60-110', '80-130', 'invalid', 'invalid', 'invalid']
WEIGHT = ['A', 'C']
MAXMODE = ['   ', 'Max']

# Do not use for production! Test and demo OK.
BROKER_URL = "test.mosquitto.org"
BROKER_PORT = 1883

def main():
    """main program"""
    def on_connect(_client, _userdata, _flags, retcode):
        """MQTT on connect callback"""
        print("Connected With Result Code "+str(retcode))
        client.subscribe("bafx3608/#")

    def on_message(_client, _userdata, message):
        """MQTT on message callback"""
        data = message.payload
        if data is not None and len(data) > 2:
            decibel, options = struct.unpack_from('>HB', data)
            decibel = decibel / 10
            if decibel <= 130.0:
                #fast_mode = (options & (1<<6)) != 0
                max_mode = (options & (1<<5)) != 0
                ac_mode = (options & (1<<4)) != 0
                inrange = options & 0x07
                print(f"{decibel:5.1f} dB{WEIGHT[ac_mode]} " \
                    + f"{MAXMODE[max_mode]} {RANGE[inrange]}")

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER_URL, BROKER_PORT, 60)

    client.loop_forever()

if __name__ == "__main__":
    main()
