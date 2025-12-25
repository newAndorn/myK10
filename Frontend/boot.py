# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()



# import time
# import ubinascii
# import machine
# import micropython
# import network
# import esp
# 
# esp.osdebug(None)
# import gc
# gc.enable()
# 
# ssid = 'andorn12'
# password = 'GardenRoute11'
# 
# station = network.WLAN(network.STA_IF)
# 
# station.active(True)
# station.connect(ssid, password)
# 
# # wait until connected
# while station.isconnected() == False:
#   pass
# 
# print('Connection successful')
# print(station.ifconfig())