#!/usr/bin/python3
"""
MQTT publish BAFX3608 readings
"""
import sys
import getopt
import paho.mqtt.client as mqtt
import bafx3608

MQTT_CLIENT_NAME = 'bafx3608-a'
MQTT_BROKER_NAME = 'test.mosquitto.org'
MQTT_PUB_TOPIC_NAME = 'bafx3608/a'
MQTT_SUB_TOPIC_NAME = 'bafx3608-config/#'
MQTT_CONNECTED = False

def main():
    """
    main program
    """
    def mqtt_on_connect(_client, _userdata, _flags, retcode):
        """MQTT on connect callback"""
        print('Connect with return code='+str(retcode))
        global MQTT_CONNECTED
        if retcode == 0:
            MQTT_CONNECTED = True
            mqttbafx.subscribe(MQTT_SUB_TOPIC_NAME)
        else:
            MQTT_CONNECTED = False

    def mqtt_on_message(_client, _userdata, _message):
        """MQTT on message callback"""

    def mqtt_on_disconnect(_client, _userdata, retcode):
        """MQTT on disconnect callback"""
        print('Disconnect with return code='+str(retcode))
        global MQTT_CONNECTED
        MQTT_CONNECTED = False

    help_cli = f'{sys.argv[0]} --range=[0..4] --fast=[0,1] --max=[0,1] --weight=[A,C]'

    out_range = 0
    out_fast = 1
    out_weight = 0
    out_max = 0

    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['range=', 'fast=', 'weight=', 'max='])
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

    def reading_callback_raw(bafxdata):
        """
        callback
        """
        if MQTT_CONNECTED:
            mqttbafx.publish(MQTT_PUB_TOPIC_NAME, bafxdata)

    mqttbafx = mqtt.Client(MQTT_CLIENT_NAME)
    mqttbafx.on_connect = mqtt_on_connect
    mqttbafx.on_message = mqtt_on_message
    mqttbafx.on_disconnect = mqtt_on_disconnect
    mqttbafx.connect(MQTT_BROKER_NAME)
    mqttbafx.loop_start()

    meter = bafx3608.Bafx3608(out_fast, out_max, out_weight, out_range)

    meter.cb_on_reading_raw = reading_callback_raw
    meter.loop_forever()

if __name__ == "__main__":
    main()
