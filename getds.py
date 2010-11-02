#!/usr/bin/python

import sys
import feedparser
import string
import os.path
import urllib

from datetime import datetime

RSSFILE = "/home/paul/src/getds/ds.rss"
LISTINGFILE = "/home/paul/src/getds/listing.html"
LASTCHECKFILE = "/home/paul/src/getds/lastcheck.var"
MINIMUM_GAP = (60 * 60)

# Take a filesize as returned by their webserver and convert it to bytes
def convertSize(insize):
    mult = 1
    if insize[-1] == 'M':
        mult = 1024 * 1024
        insize = insize[:-1]
    elif insize[-1] == 'K':
        mult = 1024
        insize = insize[:-1]
    insize = float(insize)

    return insize * mult

def shouldCheckNow():
    now = datetime.utcnow()

    # First do the easy bits - Deafstation's only updated Monday->Friday, so if
    # it's the weekend then don't bother.
    day = now.weekday()
    if day == 5 or day == 6:
        print "It's the weekend, DeafStation doesn't update."
        return False

    try:
        f = open(LASTCHECKFILE)
        timestamp = f.readline()
        f.close()
        if len(timestamp) == 0:
            print "Empty timestamp; been playing around again?"
            return True
        else:
            last_check = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            gap = now - last_check
            if gap.seconds < MINIMUM_GAP:
                print "Only %i minutes since last check, waiting for %i." % \
                        ((gap.seconds / 60), MINIMUM_GAP)
            else:
                print "%i minutes since last check, let's try again." % \
                        (gap.seconds / 60)
                return True
    except IOError, e:
        print "Couldn't open file", LASTCHECKFILE, "- assuming clean run"
        return True

    return False

def updateLastChecked():
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print "Setting last checked time to", now
    f = open(LASTCHECKFILE, "wa")
    f.write(now)
    f.close()

# Get page
def getPage(url, cached):
    print "Getting page"
    listingurl = "http://www.deafstation.org/deafstationDev_video/home/deafstation/published/"
    if not cached or not os.path.exists(LISTINGFILE):
        print "\tGetting fresh copy of listing."
        urllib.urlretrieve(listingurl, LISTINGFILE)

    f = open(LISTINGFILE)
    page = f.readlines()
    f.close()
    return page

# DS use some really random date stuff. Try to keep all the madness is one
# place.
def parseDate(str):
	dt = None
	# print "parseDate trying to deal with string '%s'" % str
	try:
		dt = datetime.strptime(str, "%d %B %Y")
	except:
		try:
			dt = datetime.strptime(str, "%d %B %Y")
		except:
			# print "Nope, strptime not working. Pulling it apart..."
			chunks = string.split(str)
			# Normalise month
			chunks[1] = chunks[1][:3]
			str = string.join(chunks)
			try:
				dt = datetime.strptime(str, "%d %b %Y")
			except:
				# print "No, I give up. Can't do date."
				pass
	
	return dt

def convertTitleToDate(title):
    # Usually, Python's nice. This bit, much less so. Ew.
    datelumps = string.split(title[5:])
    day = datelumps[0]
    while len(day) and day[-1] not in string.digits:
        day = day[:-1]
    datelumps[0] = day
    date = string.join(datelumps)
    return date

def isFeedCurrent(feed):
    date = convertTitleToDate(feed.entries[0].title)
    dt = parseDate(date)
    if not dt:
        print "Couldn't parse date."
        return False

    now = datetime.utcnow()
    print "Comparing day %i/%i, month %i/%i, year %i/%i" % \
        (dt.day, now.day, dt.month, now.month, dt.year, now.year)
    if dt.day == now.day and dt.month == now.month and dt.year == now.year:
        return True
    else:
        return False

# Get RSS
def getRss():
    rssurl = "http://www.deafstation.org/deafstationDev/getAllPC.do?latestNews=1&preferredClientId=4"

    doneOnce = False
    while 1:
        if os.path.exists(RSSFILE):
            f = open(RSSFILE)
            rss = f.readlines()
            f.close()
            feed = feedparser.parse(''.join(rss))

        if os.path.exists(RSSFILE) and isFeedCurrent(feed):
            # Update this - if the local copy is current, we don't need 
            # to pull the RSS again.
            updateLastChecked()
            break
        elif doneOnce:
            print "Looks like feed hasn't updated yet."
            # Hold off for a bit to avoid flooding the website.
            updateLastChecked()
            rss = None
            feed = None
            break
        elif not shouldCheckNow():
            # Hold off for a bit to avoid flooding the website.
            print "Checked too recently, not re-checking yet."
            rss = None
            feed = None
            break
        else:
            print "Retrieving new copy of RSS feed."
            urllib.urlretrieve(rssurl, RSSFILE)
            doneOnce = True

    return (rss, feed, not doneOnce)

def findStories(feed):
    stories = []
    for e in feed.entries:
        stories.append(e.title)
    return stories

# Find current headline
def getHeadlineFile(feed):
    e = feed.entries[0]
    # Basic sanity check
    if e.title[:4] == "News":
        return os.path.split(e.summary)

def getBaseUrl(feed):
    (urlpath, headlineFile) = getHeadlineFile(feed)
    return urlpath

# Find videos
def findVideos(feed, page):
    (urlpath, headlineFile) = getHeadlineFile(feed)
    pagelen = len(page)
    for thresh_loop in range(10, 3, -1):
        videos = []
        threshold = thresh_loop * (1024 * 1024)
        #print "Checking for threshold %iM" % thresh_loop

        # It's unlikely to be 100 lines back...
        for i in range(pagelen - 1, pagelen - 101, -1):
            chunks = string.split(page[i])
            if len(chunks) < 9:
                continue

            # Check it's a video
            if chunks[2] != 'alt="[VID]"':
                continue

            # Check it's big enough. If it is, pop it on the list.
            filesize = convertSize(chunks[-1])
            if filesize > threshold:
                tmp = string.split(chunks[5], '"')
                filename = tmp[1]
                # Check if this is the headline
                videos.append(filename)
                #print "Comparing", filename, "to headline file", headlineFile
                if filename == headlineFile:
                    print "It matches."
                    break

        if i != (pagelen - 100):
            break

    # Do this so they actually go the right way around, 
    # since we processed in reverse...
    if videos:
        videos.reverse()

    return videos

def findVideos2(page, date):
    # Assume date in dd-mm-yyyy format
    pagelen = len(page)
    videos = []
    findingOurDate = True
    findingNextDate = False

    for i in range(pagelen - 1, 0, -1):
        chunks = string.split(page[i])
        if len(chunks) < 9:
            continue

        # Check it's a video
        if chunks[2] != 'alt="[VID]"':
            continue

        # Check it's big enough. If it is, pop it on the list.
        filesize = convertSize(chunks[-1])
        if filesize > (5 * 1024 * 1024):
            filedate = chunks[6]
            print "File date", filedate

            tmp = string.split(chunks[5], '"')
            filename = tmp[1]
            # Check if this is the headline
            if findingOurDate and filedate == date:
                print "Dates %s and %s match, starting collection" % (filedate, date)
                findingOurDate = False
                findingNextDate = True
                print "Appending %s" % filename
                videos.append(filename)
            elif findingNextDate:
                if filedate != date:
                    print "We found the previous entry"
                    break
                else:
                    print "Looking for next date, %s == %s, appending %s" % (filedate, date, filename)
                    videos.append(filename)
            else:
                print "Boring, skipping filedate", filedate
                print "findingNextDate %s findingOurDate %s" % (findingNextDate, findingOurDate)

    # Do this so they actually go the right way around, 
    # since we processed in reverse...
    videos.reverse()
    return videos

def makePrefix(feed):
    e = feed.entries[0]
    # Basic sanity check
    if e.title[:4] == "News":
        date = convertTitleToDate(e.title)
        dt = parseDate(date)
        prefix = dt.strftime("News %Y %m %d")
    else:
        raise Exception

    return prefix

def makeOutDir(datestring):
    dir = string.replace(datestring, " ", "_")
    try:
        os.mkdir(dir)
    except OSError:
        # Got OS error, assuming directory already there
        pass
    return dir

def checkAlreadyDownloaded(dir):
    filename = "%s/finished" % dir
    try:
        f = open(filename)
        line = f.readline()
        f.close()
        return True
    except:
        # Assuming not already downloaded!
        pass

    return False

def markAlreadyDownloaded(dir):
    outputName = "%s/finished" % dir
    f = open(outputName, "wa")
    f.write("I've finished.\n")
    f.close()

# Main
(rss, feed, cached) = getRss()
# Slight hack here; want to make this nicer.
if rss == None:
    sys.exit(0)
prefix = makePrefix(feed)
outDir = makeOutDir(feed.entries[0].title)

# Right - we still need to do stuff, so here we go.
baseurl = getBaseUrl(feed)
page = getPage(baseurl, cached)
videos = findVideos(feed, page)
#videos = findVideos2(page, "14-May-2010")
stories = findStories(feed)

# Check we have the same amount of items and videos
if len(videos) != len(stories):
    print "We don't have the same number of stories and videos."
    print "We have", len(stories), "stories and", len(videos), "videos."
    print "Stories:\n\t%s" % string.join(stories, '\n\t')
    print "Videos:\n\t%s" % string.join(videos, '\n\t')
    print "Limiting retrieval."
    if len(videos) > len(stories):
        videos = videos[:len(stories)]
    else:
        stories = stories[:len(videos)]

if checkAlreadyDownloaded(outDir):
    print "Already seem to have downloaded for this day."
    sys.exit(0)

# For each video, build the output filename and get it
allOkay = True
for index in range(len(videos)):
    escaped_story = string.replace(stories[index], os.sep, "_")
    outputName = "%s/%s - %i - %s.mov" % (outDir, prefix, index + 1, escaped_story)
    url = "%s/%s" % (baseurl, videos[index])
    print "Retrieve story '%s'" % stories[index]
    (filename, headers) = urllib.urlretrieve(url, outputName)

if allOkay:
    print "All downloaded okay, marking done."
    markAlreadyDownloaded(outDir)
