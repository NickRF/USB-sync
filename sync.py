#!/usr/bin/env python

import dbus
import gobject
import subprocess

import os
from configobj import ConfigObj

DEVICE_INTERFACE = "org.freedesktop.UDisks.Device"

class DeviceListener:
	def __init__(self):
		self.bus = dbus.SystemBus()

		obj = self.bus.get_object("org.freedesktop.UDisks", "/org/freedesktop/UDisks")
		udisks = dbus.Interface(obj, "org.freedesktop.UDisks")

		def handle_device(device_obj_name):
			obj = self.bus.get_object("org.freedesktop.UDisks", device_obj_name)
			props = dbus.Interface(obj, dbus.PROPERTIES_IFACE)
			
			# TODO: Proper way of determining if object exists...
			try:
				mounted = props.Get(DEVICE_INTERFACE, "DeviceIsMounted")
			except dbus.exceptions.DBusException:
				return

			if mounted:
				paths = props.Get(DEVICE_INTERFACE, "DeviceMountPaths")
				if paths:
					p = paths[0]
					f = os.path.join(p, ".sync.cfg")
					if os.path.exists(f):
						cfg = ConfigObj(f)
						self.sync_device(obj, cfg, p)

		# Don't unmount existing devices
		self.allow_unmount = False

		# Sync any existing devices
		for dev in udisks.EnumerateDevices():
			handle_device(dev)
		
		# No we can unmount
		self.allow_unmount = True

		# Listen for changes (have to wait for device to be mounted)
		udisks.connect_to_signal('DeviceChanged', handle_device)

	def sync_device(self, device_object, cfg, device_mount_path):
		src = cfg['host_path'] + os.sep # Trailing slash prevents rsync creating src in dest
		dest = os.path.join(device_mount_path, cfg['device_path'])

		print 'syncing from "%s" to "%s"' % (src, dest)
		ec = subprocess.call(['rsync', '-r', src, dest])
		print "Done (exit code=%d)" % ec

		if self.allow_unmount: # Unmounting disabled when doing initial scan
			device = dbus.Interface(device_object, DEVICE_INTERFACE)
			unmount = cfg.get('unmount')
			eject = cfg.get('eject')

			# Grab drive before we unmount
			drive_object = self.get_drive_object(device_object)
			drive = dbus.Interface(drive_object, DEVICE_INTERFACE)

			if unmount or eject:
				print "Unmounting %s" % device_mount_path
				dbus_retry(lambda: device.FilesystemUnmount([]))

			if eject: # TODO: needs to happen after processing all partitions
				print "Ejecting %s" % drive_object.object_path
				# Grab physical device for this partition
				dbus_retry(lambda: drive.DriveDetach([]))

	def get_drive_object(self, partition_object):
		props = dbus.Interface(partition_object, dbus.PROPERTIES_IFACE)
		drive_name = props.Get(DEVICE_INTERFACE, "PartitionSlave")
		return self.bus.get_object("org.freedesktop.UDisks", drive_name)
		drive = dbus.Interface(drive_object, DEVICE_INTERFACE)

def dbus_retry(f, max_tries=3):
	tries = 0
	while True:
		tries += 1
		try:
			f()
			return
		except dbus.exceptions.DBusException:
			if tries >= max_tries:
				raise
			print "Caught exception, retrying"
		
if __name__ == '__main__':
	from dbus.mainloop.glib import DBusGMainLoop
	DBusGMainLoop(set_as_default=True)
	loop = gobject.MainLoop()
	DeviceListener()

	try:
		loop.run()
	except KeyboardInterrupt:
		print "Keyboard interrupt. Exiting."

