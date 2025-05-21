from dataclasses import dataclass
import sys
import argparse
import json
from datetime import datetime
import requests
import html.entities
import os

@dataclass
class Waypoint:
	lat:float
	lng:float
	elevation:float
	ts:datetime
	name:str
	type:str

@dataclass
class Rtept:
	lat:float
	lng:float
	elevation:float
	ts:datetime

@dataclass
class Gpx:
	startTime:datetime
	endTime:datetime
	startLat:float
	startLng:float
	endLat:float
	endLng:float
	distance:float

entityTable = {k: '&{};'.format(v) for k, v in html.entities.codepoint2name.items()}

def getFromRest(url):
	try:
		response = requests.get(url)
		response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
		data = response.json()  # Parse the JSON response body
		return data
	except requests.exceptions.RequestException as e:
		print(f"An error occurred: {e}")
	except ValueError:
		print("Failed to decode JSON response")

def extractLatLng(latLng):

	lat,lng = float(latLng.split(',')[0].replace('°','')), float(latLng.split(',')[1].replace('°',''))
	try :
		elevation = float(getFromRest('https://maps.googleapis.com/maps/api/elevation/json?locations={lat}%2C{lng}&key={key}'.format(lat = lat, lng=lng, key=os.environ['GOOGLE_MAPS_API_KEY']))['results'][0]['elevation'])
	except IndexError:
		elevation = None
	return lat,lng, elevation

def extractLatLngAndPlace(latLng, placeId):

	lat,lng,elevation = extractLatLng(latLng)
	place = getFromRest('https://places.googleapis.com/v1/places/{placeId}?fields=id,displayName,types,editorialSummary&key={key}'.format(placeId = placeId, key=os.environ['GOOGLE_MAPS_API_KEY']))
	return lat,lng, elevation, place

def extractVisit(segment, wptList):
	lat, lng,elevation,place = extractLatLngAndPlace(segment['visit']['topCandidate']['placeLocation']['latLng'], segment['visit']['topCandidate']['placeId'])
	ts = segment['startTime']
	wpt = Waypoint(lat, lng, elevation, datetime.fromisoformat(ts), place['displayName']['text'], place['types'][0])
	wptList.append(wpt)

def extractRte(segment, rteptList):
	for rtePtSegment in segment['timelinePath']:
		rteptList.append(extractRtept(rtePtSegment))

def extractRtept(segment):
	lat, lng,elevation = extractLatLng(segment['point'])
	ts = segment['time']
	rtePt = Rtept(lat, lng, elevation, datetime.fromisoformat(ts))
	return rtePt

def extractGpx(segment, gpxList):
	startTime = datetime.fromisoformat(segment['startTime'])
	endTime = datetime.fromisoformat(segment['endTime'])
	startLat, startLng,startElevation = extractLatLng(segment['activity']['start']['latLng'])
	endLat, endLng,endElevation = extractLatLng(segment['activity']['end']['latLng'])
	distance = float(segment['activity']['distanceMeters'])
	gpx = Gpx(startTime, endTime, startLat, startLng, endLat, endLng, distance)
	gpxList.append(gpx)

def printWptList(wptList):
	for wpt in wptList:
		if wpt.elevation:
			wptStr = '<wpt lat="{lat}" lon="{lng}">\n<ele>{elevation}</ele>\n<time>{ts}</time>\n<name>{name}</name>\n<sym>{symbol}</sym>\n<type><![CDATA[{type}]]></type>\n</wpt>\n'
			print(wptStr.format(lat=wpt.lat, lng=wpt.lng, elevation=wpt.elevation, ts=wpt.ts.isoformat(), name=wpt.name.translate(entityTable), type=wpt.type, symbol=wpt.type))
		else:
			wptStr = '<wpt lat="{lat}" lon="{lng}">\n<time>{ts}</time>\n<name>{name}</name>\n<sym>{symbol}</sym>\n<type><![CDATA[{type}]]></type>\n</wpt>\n'
			print(wptStr.format(lat=wpt.lat, lng=wpt.lng, ts=wpt.ts.isoformat(), name=wpt.name.translate(entityTable), type=wpt.type, symbol=wpt.type))

def printRteptList(name, rteptList):
	print('<trk>\n<name>{name}</name>\n<trkseg>'.format(name=name.translate(entityTable)))
	for rtept in rteptList:
		if rtept.elevation:
			rteptStr = '<trkpt lat="{lat}" lon="{lng}">\n<ele>{elevation}</ele>\n<time>{ts}</time>\n</trkpt>\n'
			print(rteptStr.format(lat=rtept.lat, lng=rtept.lng, elevation=rtept.elevation, ts=rtept.ts.isoformat()))
		else:
			rteptStr = '<trkpt lat="{lat}" lon="{lng}">\n<time>{ts}</time>\n</trkpt>\n'
			print(rteptStr.format(lat=rtept.lat, lng=rtept.lng, ts=rtept.ts.isoformat()))
	print('</trkseg>\n</trk>\n')

def printGpxList(name, gpxList):
	minLat, maxLat, minLng, maxLng,ts = extractBounds(gpxList)
	gpxStr = '<gpx version="1.0" creator="AvasthiConverter - https://www.indiabytheroad.com" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.topografix.com/GPX/1/0" xsi:schemaLocation="http://www.topografix.com/GPX/1/0 http://www.topografix.com/GPX/1/0/gpx.xsd">\n<time>{ts}</time>\n<bounds minlat="{minlat}" minlon="{minlng}" maxlat="{maxlat}" maxlon="{maxlng}"/>\n<metadata>\n<name>{filename}</name>\n<author>\n<name>indiabytheroadconverter</name>\n<link href="https://www.indiabytheroad.com"/>\n</author>\n</metadata>'
	print(gpxStr.format(filename=name, ts=ts.isoformat(), minlat=minLat, minlng=minLng, maxlat=maxLat, maxlng=maxLng))

def extractBounds(gpxList):
	lats = []
	lngs = []
	tss = []
	for gpx in gpxList:
		lats.append(gpx.startLat)
		lats.append(gpx.endLat)
		lngs.append(gpx.startLng)
		lngs.append(gpx.endLng)
		tss.append(gpx.startTime)
	return min(lats), max(lats), min(lngs), max(lngs), min(tss)

def traverseThroughFile(segment, wptList, rteptList, gpxList):
	if 'visit' in segment:
		pass
		extractVisit(segment, wptList)
	elif 'activity'  in segment:
		pass
		extractGpx(segment, gpxList)
	elif 'timelinePath' in segment:
		extractRte(segment, rteptList)
		pass

def convert(args):
	with open(args.json, 'r') as file:
		data = json.load(file)

		wptList = []
		rteptList = []
		gpxList = []
		print('<?xml version="1.0" encoding="UTF-8"?>')
		for segment in data['semanticSegments']:
			traverseThroughFile(segment, wptList, rteptList, gpxList)
		printGpxList(args.json.split('.')[0], gpxList)
		printWptList(wptList)
		printRteptList(args.json.split('.')[0], rteptList)
		print('</gpx>')


if __name__=="__main__":
	parser = argparse.ArgumentParser("convertTimelineToGPX")
	parser.add_argument("--json", dest='json', help="Name of the json file")
	args = parser.parse_args()
	convert(args)
