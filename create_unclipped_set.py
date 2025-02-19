import os
import shutil
import subprocess
import tempfile
import traceback

import geopandas as gpd
import numpy as np
import requests
import shapely
import tqdm
from permacache import permacache

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

    clip_district_to_state(file, "Rhode Island", "1", "28", "42")
    clip_district_to_state(file, "Georgia", "9", "89", "92")
    fix_overlap(file, "New York", "15", "16", "53", "57")
    fix_overlap(file, "Tennessee", "6", "7", "95", "97")
    return file


def clip_district_to_state(df, state_title, district, start, end):
    directory = os.path.dirname(os.path.abspath(__file__))
    dist_table = df[
        (df.STATENAME == state_title)
        & (df.DISTRICT == district)
        & (df.STARTCONG == start)
        & (df.ENDCONG == end)
    ]
    if dist_table.shape[0] == 0:
        return
    assert dist_table.shape[0] == 1
    [idx] = dist_table.index
    dist_geo = df.loc[idx].geometry
    state = (
        gpd.read_file(f"{directory}/{state_title}/{state_title}.shp").iloc[0].geometry
    )
    dist_geo_proper = dist_geo.intersection(state)
    assert dist_geo_proper.area > 0.90 * dist_geo.area
    assert dist_geo_proper.area < dist_geo.area
    df.loc[idx, "geometry"] = dist_geo_proper


def fix_overlap(df, state, district_1, district_2, start_cong, end_cong):
    """
    Fix the overlap between two districts in the same state. Allocates to
    the first district
    """
    dist_table_1 = df[
        (df.STATENAME == state)
        & (df.DISTRICT == district_1)
        & (df.STARTCONG == start_cong)
        & (df.ENDCONG == end_cong)
    ]
    dist_table_2 = df[
        (df.STATENAME == state)
        & (df.DISTRICT == district_2)
        & (df.STARTCONG == start_cong)
        & (df.ENDCONG == end_cong)
    ]
    if dist_table_1.shape[0] == 0 or dist_table_2.shape[0] == 0:
        return
    assert dist_table_1.shape[0] == 1
    assert dist_table_2.shape[0] == 1
    [idx_1] = dist_table_1.index
    [idx_2] = dist_table_2.index
    geo_1 = df.loc[idx_1].geometry
    geo_2 = df.loc[idx_2].geometry
    overlap = geo_1.intersection(geo_2)
    df.loc[idx_2, "geometry"] = geo_2.difference(overlap)


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


cea = dict(proj="cea")


def safe_intersects(geom1, geom2, safe_option):
    try:
        return geom1.intersects(geom2)
    except Exception as e:
        return safe_option


def buffer_geometry(data, idx, buffer):
    geom = data.iloc[idx].geometry

    overlap_mask = compute_overlap_mask(data, idx, geom)

    # check that the intersections are largely contains

    buffered_geom = geom.buffer(buffer).simplify(buffer / 2)
    buffered_geom = buffered_geom.difference(
        relevant_chunk_of_land(geom).difference(geom)
    )
    buffered_geom = buffered_geom.buffer(0)
    assert buffered_geom.is_valid
    buffered_bounds = buffered_geom.bounds
    idxs = []
    for idx_other in range(data.shape[0]):
        if idx == idx_other:
            continue
        if not bounds_overlap(buffered_bounds, data.bounds_tuples[idx_other]):
            continue
        if overlap_mask[idx_other]:
            # they already intersected. We do not want to difference them
            # this happens in situations where, for example, one district is
            # TN-at large and the other is TN-06. This happens in the 43rd
            # congress, and in a bunch of later congresses
            continue
        if not safe_intersects(
            buffered_geom, data.geometry[idx_other], safe_option=True
        ):
            continue
        if buffered_geom.intersection(data.geometry[idx_other]).area > 0:
            idxs.append(idx_other)
    for idx_other in idxs:
        try:
            buffered_geom = buffered_geom.difference(data.geometry[idx_other])
        except shapely.errors.GEOSException:
            buffered_geom = buffered_geom.buffer(0)
            buffered_geom = buffered_geom.difference(data.geometry[idx_other])

    return buffered_geom.buffer(0)


def compute_overlap_mask(data, idx, geom):
    overlap_overall = np.zeros(data.shape[0], dtype=bool)

    assert data.index[idx] == idx

    intersects_mask = np.array(
        [safe_intersects(geom, x, safe_option=True) for x in data.geometry]
    )
    data = data[intersects_mask]

    areas = data.geometry.to_crs(cea).area

    assert data.shape[0] == intersects_mask.sum()

    intersections_with_this = data.geometry.intersection(geom).to_crs(cea).area

    overlap_inter_over_min = intersections_with_this / np.minimum(areas, areas.loc[idx])

    overlap_mask = overlap_inter_over_min > 1e-2

    assert (
        overlap_inter_over_min[overlap_mask].min() > 0.5
    ), f"{data.loc[idx]}; {overlap_inter_over_min[overlap_mask]}"

    overlap_overall[intersects_mask] = overlap_mask

    return overlap_overall


def buffer_all(data, buffer, unmanipulated_indices):
    data = data.copy()
    data = data[data.geometry.apply(lambda x: x is not None)].reset_index(drop=True)
    data["bounds_tuples"] = data.geometry.apply(lambda x: x.bounds)
    pbar = tqdm.trange(data.shape[0])
    for idx in pbar:
        if idx in unmanipulated_indices:
            continue
        pbar.set_postfix_str(f"{data.iloc[idx].STATENAME} {data.iloc[idx].DISTRICT}")
        buffered_geo = buffer_geometry(data, idx, buffer)
        assert buffered_geo is not None
        assert buffered_geo.is_valid
        assert buffered_geo.area >= 0.999 * data.iloc[idx].geometry.area, (
            f"Buffered area is smaller than original area for {data.iloc[idx].STATENAME} {data.iloc[idx].DISTRICT}"
            f" {buffered_geo.area} < {data.iloc[idx].geometry.area}"
        )
        data.loc[idx, "geometry"] = buffered_geo
    del data["bounds_tuples"]
    data.geometry = data.geometry.buffer(0)
    return data


@permacache(
    "historical-congressional-unclipped/create_unclipped_set/unclipped_congress_3"
)
def unclipped_congress(number):
    data = load_shapefile(number)
    data = buffer_all(data, 1 / 120, [])
    return data


def output_unclipped_congresses():
    os.makedirs("unclipped_congresses", exist_ok=True)
    for i in range(1, 1 + 114):
        path = f"unclipped_congresses/{i:03d}.shp.zip"
        if os.path.exists(path):
            continue
        try:
            unclipped_congress(i).to_file(
                filename=path,
                driver="ESRI Shapefile",
            )
        except Exception as e:
            print(f"Failed for {i}")
            traceback.print_exc()
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    output_unclipped_congresses()
