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

def convertTitleToDate(title):
    # Usually, Python's nice. This bit, much less so. Ew.
    datelumps = string.split(title[5:])
    day = datelumps[0]
    while len(day) and day[-1] not in string.digits:
        day = day[:-1]
    datelumps[0] = day
    date = "%s %s %s" % (datelumps[0], datelumps[1], datelumps[2])
    return date

def isDateCurrent(feed):
    date = convertTitleToDate(feed.entries[0].title)
    dt = datetime.strptime(date, "%d %b %Y")
    now = datetime.utcnow()
    if dt.day == now.day and dt.month == now.month and dt.year == now.year:
        return True
    else:
        return False

# Get RSS
def getRss():
    rssurl = "http://www.deafstation.org/deafstationDev/getAllPC.do?latestNews=1&preferredClientId=4"

    doneOnce = False
    print "Getting RSS"
    while 1:
        if os.path.exists(RSSFILE):
            f = open(RSSFILE)
            rss = f.readlines()
            f.close()
            feed = feedparser.parse(''.join(rss))

        if os.path.exists(RSSFILE) and isDateCurrent(feed):
            # Update this - if the local copy is current, we don't need 
            # to pull the RSS again.
            updateLastChecked()
            break
        elif doneOnce:
            print "\tLooks like feed hasn't updated yet."
            # Hold off for a bit to avoid flooding the website.
            updateLastChecked()
            raise Exception
        else:
            print "\tRetrieving new copy."
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
    videos = []
    for i in range(pagelen - 1, pagelen - 30, -1):
        chunks = string.split(page[i])
        if len(chunks) < 9:
            continue

        # Check it's a video
        if chunks[2] != 'alt="[VID]"':
            continue

        # Check it's big enough. If it is, pop it on the list.
        filesize = convertSize(chunks[-1])
        if filesize > (10 * 1024 * 1024):
            tmp = string.split(chunks[5], '"')
            filename = tmp[1]
            # Check if this is the headline
            videos.append(filename)
            if filename == headlineFile:
                break

    # Do this so they actually go the right way around, 
    # since we processed in reverse...
    videos.reverse()
    return videos

def makePrefix(feed):
    e = feed.entries[0]
    # Basic sanity check
    if e.title[:4] == "News":
        date = convertTitleToDate(e.title)
        dt = datetime.strptime(date, "%d %b %Y")
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
if shouldCheckNow() == False:
    print "Not checking just yet. Maybe too soon after last check?"
    sys.exit(0)

(rss, feed, cached) = getRss()
prefix = makePrefix(feed)
outDir = makeOutDir(feed.entries[0].title)
if checkAlreadyDownloaded(outDir):
    print "Already seem to have downloaded for this day."
    sys.exit(0)

# Right - we still need to do stuff, so here we go.
baseurl = getBaseUrl(feed)
page = getPage(baseurl, cached)
videos = findVideos(feed, page)
stories = findStories(feed)

# Check we have the same amount of items and videos
if len(videos) != len(stories):
    print "We don't have the same number of stories and videos."
    raise Exception

# For each video, build the output filename and get it
allOkay = True
for index in range(len(videos)):
    outputName = "%s/%s - %i - %s.mov" % (outDir, prefix, index + 1, stories[index])
    url = "%s/%s" % (baseurl, videos[index])
    print "Retrieve story '%s'" % stories[index]
    (filename, headers) = urllib.urlretrieve(url, outputName)

if allOkay:
    print "All downloaded okay, marking done."
    markAlreadyDownloaded(outDir)
