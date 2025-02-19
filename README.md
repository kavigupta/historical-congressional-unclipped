
# Historical congressional district maps without the coastline fuss

Jeffrey B. Lewis, Brandon DeVine, and Lincoln Pritcher with Kenneth C. Martis has a collection of historical congressional district maps that are useful for research. However, the maps are not in a format that is easy to use because they include extremely detailed coastlines. This repository contains the same maps with the coastlines removed.

Original source: [Lewis et al](https://cdmaps.polisci.ucla.edu/)

## Data

It is downloaded when you run the script, from the original source. We make the following changes other than unclipping:

    - RI-01 in the 28th-42nd congresses, which is overlaps MA for some reason.
    - Similarly, GA-09 overlaps SC in the 89th-92nd congresses.
    - NY-15 and NY-16 in the 53rd-57th congresses, which overlap each other. We allocate the overlap, Roosevelt Island, to NY-15, 
        arbitrarily (it doesn't really matter, as it's a small island).
    - TN-06 and TN-07 both contain Memphis in the 95th-97th congresses. We allocate the overlap to TN-06, because,
        according to the wikipedia, `In 1972, he entered the GOP primary for the newly reconfigured 6th Congressional District.[2] The district had been significantly redrawn by the state legislature, which shifted several Republican-trending portions near Memphis into the Sixth and removed several solidly Democratic areas.[citation needed]` (https://en.wikipedia.org/wiki/Robin_Beard)[link]. Not the most reliable source, but it's the best I was willing to pull.

## Unclipping technique

We create a "north america" shapefile (US / Canada / Mexico) by taking a Canada / Mexico shapefile and merging it with the 114th congress US shapefile, removing internal holes/boundaries manually. (this is presented in the `north-america` folder). We then
buffer each district by 30 arcseconds and simplify to 15 arcseconds. We then take the difference between land and the original district, and take the difference between the buffered district, and this difference. In effect, we add some buffering, but only in the water.

In symbols, we have:

```
out = buffer_and_simplify(district) - (land - district)
```

## Outputs

Outputs are placed in the file `unclipped_congress`.
