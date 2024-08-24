import math
import shapely
import cartopy.geodesic
import cartopy.crs as ccrs
import matplotlib.pyplot as plt

import brahe as bh


def select_color(owner):
    if owner.lower() == 'aws':
        return 'orange'
    elif owner.lower() == 'ksat':
        return 'red'
    elif owner.lower() == 'atlas':
        return 'purple'
    elif owner.lower() == 'viasat':
        return 'yellow'
    elif owner.lower() in ['leaf space', 'leaf']:
        return 'green'
    elif owner.lower() == 'azure':
        return 'blue'
    else:
        return 'grey'

def compute_look_angle_max(ele=0.0, alt=525e3):
    ele = ele * math.pi / 180.0

    rho = math.asin(bh.R_EARTH/(bh.R_EARTH + alt))

    eta = math.asin(math.cos(ele)*math.sin(rho))
    lam = math.pi/2.0 - eta - ele

    return lam

def plot_stations(stations: list[tuple[float, float, str]], elevation_min:float=10, alt:float=500e3, opacity=0.5, ax=None):
    lam = compute_look_angle_max(ele=elevation_min, alt=alt)

    fig = plt.figure(figsize=(10, 5))
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_global()
    ax.stock_img()

    for station in stations:
        lon, lat = station[0], station[1]

        c = select_color(station[2])

        # Plot Groundstation Location
        ax.plot(lon, lat, color=c, marker='o', markersize=3, transform=ccrs.Geodetic())

        circle_points = cartopy.geodesic.Geodesic().circle(lon=lon, lat=lat, radius=lam * bh.R_EARTH, n_samples=100,
                                                           endpoint=False)
        geom = shapely.geometry.Polygon(circle_points)
        ax.add_geometries((geom,), crs=ccrs.Geodetic(), facecolor=c, alpha=opacity, edgecolor='none', linewidth=0)

    return fig, ax