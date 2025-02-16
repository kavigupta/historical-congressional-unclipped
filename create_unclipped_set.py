import shutil
import tempfile
import requests
import subprocess
import geopandas as gpd
from permacache import permacache

import shapely
import tqdm

# count goes from 1 to 114
URL = "https://cdmaps.polisci.ucla.edu/shp/districts{count:03d}.zip"


def load_shapefile(count):
    url = URL.format(count=count)
    response = requests.get(url)
    with tempfile.NamedTemporaryFile(suffix=".zip") as temp:
        temp.write(response.content)
        temp.flush()
        subprocess.run(["unzip", temp.name])
    file = gpd.read_file(f"districtShapes/districts{count:03d}.shp")
    shutil.rmtree("districtShapes")
    return file


@permacache("historical-congressional-unclipped/create_unclipped_set/land_shapefile_2")
def land_shapefile():
    df = gpd.read_file("north-america/usa.shp")
    assert df.shape[0] == 1
    return df.iloc[0].geometry


def bounds_overlap(bounds1, bounds2):
    lon1, lat1, lon2, lat2 = bounds1
    lon3, lat3, lon4, lat4 = bounds2
    lon_does_overlap = not (lon1 < lon2 < lon3 < lon4 or lon3 < lon4 < lon1 < lon2)
    lat_does_overlap = not (lat1 < lat2 < lat3 < lat4 or lat3 < lat4 < lat1 < lat2)
    return lon_does_overlap and lat_does_overlap


def relevant_chunk_of_land(geo):
    """
    Return the chunk of land within geo's bounding box. Intersection of land and bounding box of geo.
    """
    geo_bounding_box = shapely.geometry.box(*geo.bounds)
    return land_shapefile().intersection(geo_bounding_box)


def buffer_geometry(data, idx, buffer):
    geom = data.iloc[idx].geometry
    buffered_geom = geom.buffer(buffer).simplify(buffer / 2)
    buffered_geom = buffered_geom.difference(
        relevant_chunk_of_land(geom).difference(geom)
    )
    idxs = []
    for idx_other in range(data.shape[0]):
        if idx == idx_other:
            continue
        if not bounds_overlap(data.bounds_tuples[idx], data.bounds_tuples[idx_other]):
            continue
        if buffered_geom.intersection(data.geometry[idx_other]).area > 0:
            idxs.append(idx_other)
    for idx_other in idxs:
        for _ in range(5):
            try:
                buffered_geom = buffered_geom.difference(data.geometry[idx_other])
                break
            except shapely.errors.GEOSException:
                print("Buffered geom is invalid. Attempting to buffer it.")
                buffered_geom = buffered_geom.buffer(0)
                continue
        else:
            import IPython

            IPython.embed()
    return buffered_geom.buffer(0)


def buffer_all(data, buffer, unmanipulated_indices):
    data = data.copy()
    data = data[data.geometry.apply(lambda x: x is not None)].reset_index(drop=True)
    data["bounds_tuples"] = data.geometry.apply(lambda x: x.bounds)
    pbar = tqdm.trange(data.shape[0])
    for idx in pbar:
        if idx in unmanipulated_indices:
            continue
        pbar.set_postfix_str(f"{data.iloc[idx].STATENAME} {data.iloc[idx].DISTRICT}")
        data.loc[idx, "geometry"] = buffer_geometry(data, idx, buffer)
    del data["bounds_tuples"]
    data.geometry = data.geometry.buffer(0)
    return data


@permacache(
    "historical-congressional-unclipped/create_unclipped_set/unclipped_congress"
)
def unclipped_congress(number):
    data = load_shapefile(number)
    data = buffer_all(data, 1 / 120, [])
    return data


def output_unclipped_congresses():
    for i in range(1, 1 + 114):
        unclipped_congress(i).to_file(
            filename=f"unclipped_congresses/{i:03d}.shp.zip", driver="ESRI Shapefile"
        )


if __name__ == "__main__":
    output_unclipped_congresses()
