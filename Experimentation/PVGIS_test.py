import requests
import osmnx as ox
import matplotlib.pyplot as plt

# Address to search
address = "Slangenstraat 48"
tags = {"building": True}

# Get buildings within 50 meters of the address
gdf = ox.features_from_address(address, tags=tags, dist=5)
building_shapes = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
print(building_shapes)


# Filter for polygons
footprint = building_shapes.geometry.iloc[0]
footprint_proj, crs = ox.projection.project_geometry(footprint)
roof_area = footprint_proj.area
print(f"Roof area: {roof_area:.2f} m²")

# Plot
fig, ax = plt.subplots(figsize=(8, 8))
building_shapes.plot(ax=ax, color="lightblue", edgecolor="black")
ax.set_title(f"Building Outline for:\n{address}")
ax.set_axis_off()
plt.show()

footprint = building_shapes.geometry.iloc[0]
center = footprint.centroid
lat, lon = center.y, center.x
print(f"Center of roof: lat={lat:.6f}, lon={lon:.6f}")

panel_area = 1.7  # m²
num_panels = int(roof_area // panel_area)
peakpower_kwp = num_panels * 0.000033  # convert W to kW
print(f"Estimated number of panels: {num_panels}")

params = {
    'lat': lat,
    'lon': lon,
    'outputformat': 'json',
    'mountingplace': 'building',
    'peakpower': peakpower_kwp,
    'loss': 14,
    'optimalangles': 1,
    'usehorizon': 1
}

response = requests.get("https://re.jrc.ec.europa.eu/api/v5_2/PVcalc", params=params)

data = response.json()
optimal_tilt = data['inputs']['mounting_system']['fixed']['slope']['value']
optimal_azimuth = data['inputs']['mounting_system']['fixed']['azimuth']['value']

print("Optimal Tilt:", optimal_tilt)
print("Optimal Azimuth:", optimal_azimuth)

