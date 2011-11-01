#!/usr/bin/env python

import dbus
import gobject
import subprocess

import os
from configobj import ConfigObj

class DeviceListener:
	def __init__(self):
		bus = dbus.SystemBus()

		obj = bus.get_object("org.freedesktop.UDisks", "/org/freedesktop/UDisks")
		udisks = dbus.Interface(obj, "org.freedesktop.UDisks")

		def handle_device(device_obj_name):
			obj = bus.get_object("org.freedesktop.UDisks", device_obj_name)
			props = dbus.Interface(obj, dbus.PROPERTIES_IFACE)
			i="org.freedesktop.UDisks.Device"
			if props.Get(i, "DeviceIsMounted"):
				paths = props.Get(i, "DeviceMountPaths")
				if paths:
					p = paths[0]
					f = os.path.join(p, ".sync.cfg")
					if os.path.exists(f):
						cfg = ConfigObj(f)
						self.sync_device(cfg, p)

		# Listen for changes (have to wait for device to be mounted)
		udisks.connect_to_signal('DeviceChanged', handle_device)

		for dev in udisks.EnumerateDevices():
			handle_device(dev)

	def sync_device(self, cfg, device_mount_path):
		src = cfg['host_path'] + os.sep # Trailing slash prevents rsync creating src in dest
		dest = os.path.join(device_mount_path, cfg['device_path'])

		print 'syncing from "%s" to "%s"' % (src, dest)
		ec = subprocess.call(['rsync', '-r', src, dest])
		print "Done (exit code=%d)" % ec

if __name__ == '__main__':
	from dbus.mainloop.glib import DBusGMainLoop
	DBusGMainLoop(set_as_default=True)
	loop = gobject.MainLoop()
	DeviceListener()

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Keyboard interrupt. Exiting."

