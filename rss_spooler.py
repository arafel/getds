#!/usr/bin/python

import daemon, lockfile
import os, sys

def testfunc():
	print "testfunc in"
	time.sleep(1)
	print "testfunc out"

home = os.getenv("HOME")
workingdir = home + "/src/getds/"

context = daemon.DaemonContext(
                    working_directory=workingdir,
		    pidfile=lockfile.FileLock(workingdir + "rss.pid"))

print context

print "Starting daemony bits."
#with context:
#	testfunc()
print "after testfunc() call"
