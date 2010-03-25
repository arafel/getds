#!/usr/bin/python

import sys
import feedparser
import string
import os.path
import urllib

from datetime import datetime

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

# Get page
def getPage(url):
    f = open("listing.html")
    page = f.readlines()
    f.close()
    return page

# Get RSS
def getRss():
    # "http://www.deafstation.org/deafstationDev/getAllPC.do?latestNews=1&preferredClientId=4"
    f = open("ds.rss")
    rss = f.readlines()
    f.close()
    return rss

def findStories(feed):
    stories = []
    for e in feed.entries:
        stories.append(e.title)
    #print "findStories returning", stories
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
        #print page[i]
        chunks = string.split(page[i])
        if len(chunks) < 9:
            continue

        # Check it's a video
        if chunks[2] != 'alt="[VID]"':
            print "Not a video, skipping"
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

    #print "findVideos returning", videos
    return videos

def makePrefix(feed):
    e = feed.entries[0]
    # Basic sanity check
    if e.title[:4] == "News":
        # Usually, Python's nice. This bit, less so. Ew.
        datelumps = string.split(e.title[5:])
        day = datelumps[0]
        while len(day) and day[-1] not in string.digits:
            day = day[:-1]
        datelumps[0] = day
        date = "%s %s %s" % (datelumps[0], datelumps[1], datelumps[2])
        dt = datetime.strptime(date, "%d %b %Y")
        prefix = dt.strftime("News %Y %m %d")
    else:
        raise Exception

    return prefix

def makeOutDir(datestring):
    dir = string.replace(datestring, " ", "_")
    return dir

# Main
print "Getting RSS"
rss = getRss()
feed = feedparser.parse(''.join(rss))
baseurl = getBaseUrl(feed)
print "Getting page"
page = getPage(baseurl)
videos = findVideos(feed, page)
stories = findStories(feed)

# Check we have the same amount of items and videos
print videos, stories
print len(videos), len(stories)
if len(videos) != len(stories):
    print "We don't have the same number of stories and videos."
    raise Exception

prefix = makePrefix(feed)
outDir = makeOutDir(feed.entries[0].title)
os.mkdir(outDir)

# For each video, build the output filename and get it
for index in range(len(videos)):
    outputName = "%s/%s - %i - %s.mov" % (outDir, prefix, index + 1, stories[index])
    url = "%s/%s" % (baseurl, videos[index])
    print "Retrieve %s into %s" % (url, outputName)
    (filename, headers) = urllib.urlretrieve(url, outputName)
