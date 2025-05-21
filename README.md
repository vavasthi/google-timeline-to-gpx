# Google-Timeline-ToGpx
This utility converts a google timeline JSON file to a GPX file. It uses google places and elevation API to find elevation and place names. For that purpose you need to get a Google Map API Key and set it in the environment variable **GOOGLE_MAPS_API_KEY**
```
python convertTimelineToGPX.py --json=Timeline.json
```