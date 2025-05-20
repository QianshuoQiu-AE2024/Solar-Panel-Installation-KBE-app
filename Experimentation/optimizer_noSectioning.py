import requests
import osmnx as ox
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box
from shapely.affinity import rotate
import math

# Address to search
address = "De Run 4604"
tags = {"building": True}

# Get buildings within 50 meters of the address
gdf = ox.features_from_address(address, tags=tags, dist=5)
building_shapes = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]

# Filter for polygons
footprint = building_shapes.geometry.iloc[0]
footprint_proj, crs = ox.projection.project_geometry(footprint)
roof_area = footprint_proj.area
print(f"Roof area: {roof_area:.2f} m²")

# Plot building
fig, ax = plt.subplots(figsize=(8, 8))
building_shapes.plot(ax=ax, color="lightblue", edgecolor="black")
ax.set_title(f"Building Outline for:\n{address}")
ax.set_axis_off()
plt.show()

# Extract center
center = footprint.centroid
lat, lon = center.y, center.x
print(f"Center of roof: lat={lat:.6f}, lon={lon:.6f}")

# Estimate panels
panel_area = 1.7  # m²
num_panels = int(roof_area // panel_area)
peakpower_kwp = num_panels * 0.33
print(f"Estimated number of panels: {num_panels}")

# PVGIS request
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

# -----------------------------
# NEW CODE: Orientation & Panel Packing with Tilt and Gaps
# -----------------------------

def calculate_bearing(p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    angle_rad = math.atan2(dy, dx)
    return math.degrees(angle_rad) % 360

def compute_wall_directions(poly):
    coords = list(poly.exterior.coords)
    wall_directions = []
    for i in range(len(coords) - 1):
        p1, p2 = coords[i], coords[i + 1]
        edge_dir = calculate_bearing(p1, p2)
        wall_directions.append((edge_dir + 90) % 360)
    return wall_directions

def find_closest_direction(wall_directions, target_azimuth):
    min_diff = 360
    best_dir = None
    for wd in wall_directions:
        diff = abs(wd - target_azimuth)
        rev_diff = 360 - diff
        actual_diff = min(diff, rev_diff)
        if actual_diff < min_diff:
            min_diff = actual_diff
            best_dir = wd
    return best_dir

def rotate_polygon_to_azimuth(poly, best_azimuth):
    rotation_angle = -best_azimuth + 90
    return rotate(poly, rotation_angle, origin='centroid', use_radians=False)

# Panel types
panel_specs = [
    {'type': 'large', 'length': 0.991, 'width': 1.956},
    {'type': 'medium', 'length': 0.991, 'width': 1.65},
    {'type': 'small', 'length': 0.991, 'width': 0.991},
]

def compute_panel_dimensions_with_tilt(panel_specs, tilt_angle_deg):
    tilt_rad = math.radians(tilt_angle_deg)
    panels = []
    for spec in panel_specs:
        length = spec['length']
        width = spec['width']
        proj_len = length * math.cos(tilt_rad)
        proj_wid = width
        eff_len = proj_len + 0.05  # side-to-side gap
        eff_wid = proj_wid + 0.15  # front-to-back gap
        panels.append({
            'type': spec['type'],
            'proj_len': proj_len,
            'proj_wid': proj_wid,
            'eff_len': eff_len,
            'eff_wid': eff_wid
        })
    return panels

def non_staggered_placement(roof_poly, panels):
    minx, miny, maxx, maxy = roof_poly.bounds
    placements = []
    total_area = 0
    used_positions = set()
    sorted_panels = sorted(panels, key=lambda p: p['eff_len'] * p['eff_wid'], reverse=True)
    y = miny

    while y < maxy:
        x = minx
        while x < maxx:
            placed = False
            for panel in sorted_panels:
                rect_shape = box(x, y, x + panel['eff_len'], y + panel['eff_wid'])
                if roof_poly.buffer(-0.01, join_style=2).contains(rect_shape):
                    placements.append({
                        'type': panel['type'],
                        'x': x,
                        'y': y,
                        'length': panel['proj_len'],
                        'width': panel['proj_wid'],
                        'color': {'small': 'lightgreen', 'medium': 'orange', 'large': 'lightblue'}[panel['type']]
                    })
                    total_area += panel['proj_len'] * panel['proj_wid']
                    used_positions.add((x, y))
                    x += panel['eff_len']
                    placed = True
                    break
            if not placed:
                x += 0.5
        y += max(p['eff_wid'] for p in panels)

        return placements, total_area

def staggered_placement(roof_poly, panels):
    minx, miny, maxx, maxy = roof_poly.bounds
    placements = []
    total_area = 0
    used_positions = set()
    sorted_panels = sorted(panels, key=lambda p: p['eff_len'] * p['eff_wid'], reverse=True)
    max_eff_len = max(p['eff_len'] for p in panels)
    max_eff_wid = max(p['eff_wid'] for p in panels)

    y = miny
    row_index = 0
    placements_staggered = []

    while y < maxy:
        # Alternate offset
        x_start = minx + ((row_index % 2) * max_eff_len / 2)
        x = x_start
        while x < maxx:
            placed = False
            for panel in sorted_panels:
                rect_shape = box(x, y, x + panel['eff_len'], y + panel['eff_wid'])
                if roof_poly.buffer(-0.01, join_style=2).contains(rect_shape):
                    placements_staggered.append({
                        'type': panel['type'],
                        'x': x,
                        'y': y,
                        'length': panel['proj_len'],
                        'width': panel['proj_wid'],
                        'color': {'small': 'lightgreen', 'medium': 'orange', 'large': 'lightblue'}[panel['type']]
                    })
                    total_area += panel['proj_len'] * panel['proj_wid']
                    x += panel['eff_len']
                    placed = True
                    break
            if not placed:
                x += 0.5
        y += max_eff_wid
        row_index += 1

    return placements_staggered, total_area

def compare_layouts(roof_poly, panels):
    non_staggered_placements, non_staggered_area = non_staggered_placement(roof_poly, panels)
    staggered_placements, staggered_area = staggered_placement(roof_poly, panels)

    if non_staggered_area >= staggered_area:
        return non_staggered_placements, non_staggered_area
    else:
        return staggered_placements, staggered_area

# -----------------------------
# Execute the logic
# -----------------------------
poly = footprint_proj

# Step A: Get wall directions and best orientation
wall_directions = compute_wall_directions(poly)
best_dir = find_closest_direction(wall_directions, optimal_azimuth)

# Step B: Rotate roof to align with optimal orientation
rotated_poly = rotate_polygon_to_azimuth(poly, best_dir)

# Step C: Get bounds of rotated roof
minx, miny, maxx, maxy = rotated_poly.bounds

# Step D: Compute panel dimensions considering tilt and gaps
tilt_angle_deg = optimal_tilt
panels = compute_panel_dimensions_with_tilt(panel_specs, tilt_angle_deg)

# Step E: Try both layouts and choose the best one
placements, total_area = compare_layouts(rotated_poly, panels)

# Step F: Count panel types
panel_counts = {'small': 0, 'medium': 0, 'large': 0}
for placement in placements:
    panel_counts[placement['type']] += 1

print(f"Panel counts: {panel_counts}")
print(f"Total Panel Area: {total_area:.2f} m²")
print(f"Roof Area: {roof_area:.2f} m²")
print(f"Coverage: {total_area / roof_area * 100:.2f}%")

# Step G: Visualize placements with roof outline and tilt direction
fig, ax = plt.subplots(figsize=(12, 12), dpi=300)
x, y = rotated_poly.exterior.xy
ax.plot(x, y, color='blue', linewidth=2, label="Roof Outline")

# Plot panels with different colors
for placement in placements:
    rect_patch = plt.Rectangle(
        (placement['x'], placement['y']),
        placement['length'], placement['width'],
        edgecolor='black',
        facecolor=placement['color'],
        alpha=0.8
    )
    ax.add_patch(rect_patch)

    # Calculate center of panel
    center_x = placement['x'] + placement['length'] / 2
    center_y = placement['y'] + placement['width'] / 2

    # Arrow length in meters (fixed for clarity)
    arrow_length = 0.2  # meters

    # Add arrow pointing along length (x-axis)
    ax.annotate(
        "",
        xy=(center_x + arrow_length, center_y),  # arrow tip
        xytext=(center_x, center_y),             # arrow base
        arrowprops=dict(arrowstyle="->", color="darkgreen", lw=2)
    )

# Set limits based on roof bounds
ax.set_xlim(minx - 0.5, maxx + 0.5)
ax.set_ylim(miny - 0.5, maxy + 0.5)
ax.set_title("Solar Panel Placement with Tilt Arrows")
ax.set_aspect('equal')
ax.legend()
plt.xlabel("Easting (m)")
plt.ylabel("Northing (m)")
plt.tight_layout()
plt.savefig("solar_placement_adaptive.png", dpi=300, bbox_inches='tight')
plt.savefig("solar_placement_adaptive.svg", format='svg', bbox_inches='tight')
plt.show()