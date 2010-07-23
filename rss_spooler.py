#!/usr/bin/python

from __future__ import with_statement

import daemon, lockfile
import feedparser
import os, sys, time, string
import urllib
import logging

from datetime import datetime

import rss_spooler as spooler

home = os.getenv("HOME")
workingdir = home + "/src/getds/"
#workingdir = ""

LOG_FILENAME = workingdir + "rss_spool.log"
logging.basicConfig(filename=LOG_FILENAME, level=logging.DEBUG)

spooldir = "stored_rss" + os.sep

RSSURL = "http://www.deafstation.org/deafstationDev/getAllPC.do?latestNews=1&preferredClientId=4"

# This file will contain the date of the last RSS file we successfully
# downloaded.
LAST_RSS_DAT_FILE = workingdir + "rss_spooler.dat"

# Returns time object
def get_today_rss_filename():
	today = datetime.today()
	datechunk = today.__str__()[:10]
	string.replace(datechunk, "-", "_")
	filename = "%sds_%s.rss" % (spooldir, datechunk)
	logging.debug("Built filename %s" % filename)
	return filename

def today_is_weekend():
	tmp = datetime.today()
	return (tmp.weekday == 5 or tmp.weekday == 6)

def get_rss_date(title):
	# Usually, Python's nice. This bit, much less so. Ew.
	datelumps = string.split(title[5:])
	day = datelumps[0]
	while len(day) and day[-1] not in string.digits:
		day = day[:-1]
	datelumps[0] = day
	date = string.join(datelumps)
	return date

def rss_is_from_today(rss_file):
	f = open(rss_file)
	rss = f.readlines()
	f.close()
	feed = feedparser.parse(''.join(rss))

	date = get_rss_date(feed.entries[0].title)
	dt = datetime.strptime(date, "%d %B %Y")
	now = datetime.utcnow()
	logging.debug("Comparing day %i/%i, month %i/%i, year %i/%i" % \
		(dt.day, now.day, dt.month, now.month, dt.year, now.year))
	if dt.day == now.day and dt.month == now.month and dt.year == now.year:
		return True
	else:
		return False

# Download the RSS file into a given filename
def get_rss(outfile):
            urllib.urlretrieve(RSSURL, outfile)

def calculate_sleep_time(have_updated):
	tmptime = datetime.today()
	sleep_days = 0
	if have_updated or today_is_weekend():
		logging.info("Sleeping until 9am next working day.")
		day = tmptime.weekday() + 1
		if day >= 5:
			logging.info("Today must be Friday. Switching to Monday.")
			sleep_days = 6 - tmptime.weekday()
			day = 0
		else:
			sleep_days = 1
		return sleep_days * (24 * 60 * 60)
	else:
		logging.info("Sleeping for an hour.")
		return (60 * 60)

# This should return true if we haven't successfully downloaded an RSS file
# matching today's date, and today is a weekday.
def need_to_check_rss():
	if today_is_weekend():
		return False

	now = datetime.utcnow()
	try:
		f = open(LAST_RSS_DAT_FILE, "r")
		tmp = f.readline()
		f.close()
		then = datetime.fromtimestamp(string.atof(tmp))
		if now.year != then.year or now.month != then.month \
				or now.day != then.day:
			return True
		else:
			return False
	except Exception, e:
		logging.exception("Oh, we got an exception:")
		return True

	return False

# This updates the "last updated" file with a timestamp. We can then feed that
# timestamp into the datetime module to recreate when we last downloaded.
def update_last_updated():
	tmpstring = "%f" % time.time()
	f = open(LAST_RSS_DAT_FILE, "w")
	f.write(tmpstring)
	logging.debug("Last updated %s" % tmpstring)
	f.close()
	return None

def rss_spool_main():
	feed_current = False
	tmpfile = "tmp.bin"
	logging.info("Need to check feed?")
	if need_to_check_rss():
		logging.info("Yes.")
		logging.info("Downloading RSS")
		get_rss(tmpfile)
		logging.info("Downloaded RSS")
		logging.info("Is RSS feed from today?",)
		if rss_is_from_today(tmpfile):
			logging.info("Yes.")
			update_last_updated()
			feed_is_current = True
			new_file = get_today_rss_filename()
			logging.debug("Moving RSS file to " + new_file)
			os.rename(tmpfile, new_file)
		else:
			logging.info("No.")
	else:
		logging.info("No.")
		feed_is_current = True

	return feed_is_current

def rss_spool_loop():
	logging.info("Entering main loop.")
	while 1:
		logging.info("Calling main.")
		feed_is_current = rss_spool_main()
		logging.info("Main says feed is" + feed_is_current + "current.")
		sleep_time = calculate_sleep_time(feed_is_current)
		logging.info("Sleeping for %i seconds." % sleep_time)
        # Yes, this is evil, I should do it properly.
        logging._handlers.items()[0][0].flush()
		time.sleep(sleep_time)

def start_daemon():
	context = daemon.DaemonContext(
			working_directory=workingdir,
		pidfile=lockfile.FileLock(workingdir + "rss.pid"))

	print "Starting daemony bits."
	with context:
		rss_spool_loop()
	print "after rss() call"

if __name__ == "__main__":
	#rss_spool_main()
    rss_spool_loop()
	#start_daemon()
