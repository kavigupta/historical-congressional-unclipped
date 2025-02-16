
# Historical congressional district maps without the coastline fuss

Jeffrey B. Lewis, Brandon DeVine, and Lincoln Pritcher with Kenneth C. Martis has a collection of historical congressional district maps that are useful for research. However, the maps are not in a format that is easy to use because they include extremely detailed coastlines. This repository contains the same maps with the coastlines removed.

Original source: [Lewis et al](https://cdmaps.polisci.ucla.edu/)

## Data

It is downloaded when you run the script, from the original source.

## Unclipping technique

We create a "north america" shapefile (US / Canada / Mexico) by taking a Canada / Mexico shapefile and merging it with the 114th congress US shapefile, removing internal holes/boundaries manually. (this is presented in the `north-america` folder). We then
buffer each district by 30 arcseconds and simplify to 15 arcseconds. We then take the difference between land and the original district, and take the difference between the buffered district, and this difference. In effect, we add some buffering, but only in the water.

In symbols, we have:

```
out = buffer_and_simplify(district) - (land - district)
```

## Outputs

Outputs are placed in the file `unclipped_congress`.
