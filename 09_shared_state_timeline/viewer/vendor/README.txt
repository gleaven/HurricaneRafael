Map library for map_view.html

The page looks for the map library in this order:
  1. vendor/leaflet/leaflet.js and vendor/leaflet/leaflet.css (this folder) - not shipped; see below
  2. Leaflet 1.9.4 from cdnjs.cloudflare.com (needs internet)
  3. the small built-in stand-in inside map_view.html (no internet needed)

With neither 1 nor 2 the page still opens and works: pan, zoom, time scrubbing, every layer and the
built-in chart (land, channels, anchorages, all streets). Only satellite imagery is unavailable,
and the page says so in the basemap control.

To get the full library on a machine without internet, copy the Leaflet 1.9.4 distribution files
leaflet.js and leaflet.css (and its images/ folder) into vendor/leaflet/. Leaflet is BSD-2-Clause.
It could not be downloaded in the build environment, which is why the folder is empty.
Satellite tiles always need internet; the built-in chart does not.
