import csv
import requests
import osmnx as ox
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box, MultiPolygon, Point
from shapely.affinity import rotate as shapely_rotate
import math
import matplotlib.transforms as mtransforms

# Address to search
address = "Plein 2000 5"
# address = "De Run 4604"
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
# Reusable Functions
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

def rotate_polygon_to_azimuth(poly, target_azimuth):
    rotation_angle = -target_azimuth + 90
    return shapely_rotate(poly, rotation_angle, origin='centroid', use_radians=False)

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
        eff_len = proj_len + 0.05
        eff_wid = proj_wid + 0.15
        panels.append({
            'type': spec['type'],
            'proj_len': proj_len,
            'proj_wid': proj_wid,
            'eff_len': eff_len,
            'eff_wid': eff_wid
        })
    return panels

# -----------------------------
# Method 1: Wall-Aligned + Sections
# -----------------------------
def optimize_method_1(roof_poly, panels, optimal_azimuth):
    wall_directions = compute_wall_directions(roof_poly)
    best_dir = find_closest_direction(wall_directions, optimal_azimuth)
    rotated_poly = rotate_polygon_to_azimuth(roof_poly, best_dir)
    rotation_angle = -best_dir + 90

    def partition_roof_shape_based(poly, num_sections=3):
        minx, miny, maxx, maxy = poly.bounds
        section_width = (maxx - minx) / num_sections
        sections = []
        for i in range(num_sections):
            sec_minx = minx + i * section_width
            section = box(sec_minx, miny, sec_minx + section_width, maxy).intersection(poly)
            if not section.is_empty:
                sections.append(section)
        return sections

    def optimize_section(section, roof_poly, panels):
        sec_minx, sec_miny, sec_maxx, sec_maxy = section.bounds
        eff_sec_minx = sec_minx + 0.025
        eff_sec_miny = sec_miny + 0.075
        eff_sec_maxx = sec_maxx - 0.025
        eff_sec_maxy = sec_maxy - 0.075

        if eff_sec_maxx <= eff_sec_minx or eff_sec_maxy <= eff_sec_miny:
            return [], 0

        placements = []
        total_area = 0
        sorted_panels = sorted(panels, key=lambda p: p['eff_len'] * p['eff_wid'], reverse=True)

        y = eff_sec_miny
        while y < eff_sec_maxy:
            x = eff_sec_minx
            while x < eff_sec_maxx:
                placed = False
                for panel in sorted_panels:
                    rect_shape = box(x, y, x + panel['eff_len'], y + panel['eff_wid'])
                    if section.contains(rect_shape) and roof_poly.buffer(-0.01, join_style=2).contains(rect_shape):
                        placements.append({
                            'type': panel['type'],
                            'x': x,
                            'y': y,
                            'length': panel['proj_len'],
                            'width': panel['proj_wid'],
                            'color': {'small': 'lightgreen', 'medium': 'orange', 'large': 'lightblue'}[panel['type']],
                        })
                        total_area += panel['proj_len'] * panel['proj_wid']
                        x += panel['eff_len']
                        placed = True
                        break
                if not placed:
                    x += 0.5
            y += max(p['eff_wid'] for p in panels)
        return placements, total_area

    sections = partition_roof_shape_based(rotated_poly, num_sections=3)
    all_placements = []
    total_area = 0
    for section in sections:
        section_placements, section_area = optimize_section(section, rotated_poly, panels)
        all_placements.extend(section_placements)
        total_area += section_area
    return all_placements, total_area, best_dir, rotation_angle, 'Wall-Aligned (With Sections)'

# -----------------------------
# Method 2: Wall-Aligned (No Sections)
# -----------------------------
def optimize_method_2(roof_poly, panels, optimal_azimuth):
    wall_directions = compute_wall_directions(roof_poly)
    best_dir = find_closest_direction(wall_directions, optimal_azimuth)
    rotation_angle = -best_dir + 90
    rotated_poly = rotate_polygon_to_azimuth(roof_poly, best_dir)

    def non_staggered_placement(roof_poly, panels):
        minx, miny, maxx, maxy = roof_poly.bounds
        placements = []
        total_area = 0
        sorted_panels = sorted(panels, key=lambda p: p['eff_len'] * p['eff_wid'], reverse=True)
        max_eff_wid = max(p['eff_wid'] for p in panels)
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
                            'color': {'small': 'lightgreen', 'medium': 'orange', 'large': 'lightblue'}[panel['type']],
                        })
                        total_area += panel['proj_len'] * panel['proj_wid']
                        x += panel['eff_len']
                        placed = True
                        break
                if not placed:
                    x += 0.5
            y += max_eff_wid
        return placements, total_area

    placements, total_area = non_staggered_placement(rotated_poly, panels)
    return placements, total_area, best_dir, rotation_angle, 'Wall-Aligned (No Sections)'

# -----------------------------
# Method 3: Optimal Azimuth (No Sections)
# -----------------------------
def optimize_method_3(roof_poly, panels, optimal_azimuth):
    rotation_angle = -optimal_azimuth + 90
    rotated_poly = rotate_polygon_to_azimuth(roof_poly, optimal_azimuth)

    def staggered_placement(roof_poly, panels):
        minx, miny, maxx, maxy = roof_poly.bounds
        placements = []
        total_area = 0
        sorted_panels = sorted(panels, key=lambda p: p['eff_len'] * p['eff_wid'], reverse=True)
        max_eff_wid = max(p['eff_wid'] for p in panels)
        row_index = 0
        y = miny
        while y < maxy:
            x = minx + ((row_index % 2) * max_eff_wid / 2)
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
                            'color': {'small': 'lightgreen', 'medium': 'orange', 'large': 'lightblue'}[panel['type']],
                        })
                        total_area += panel['proj_len'] * panel['proj_wid']
                        x += panel['eff_len']
                        placed = True
                        break
                if not placed:
                    x += 0.5
            y += max_eff_wid
            row_index += 1
        return placements, total_area

    placements, total_area = staggered_placement(rotated_poly, panels)
    return placements, total_area, optimal_azimuth, rotation_angle, 'Optimal Azimuth (No Sections)'

# -----------------------------
# Method 4: Optimal Azimuth + Roof Sectioning
# -----------------------------
def optimize_method_4(roof_poly, panels, optimal_azimuth):
    rotation_angle = -optimal_azimuth + 90
    rotated_poly = rotate_polygon_to_azimuth(roof_poly, optimal_azimuth)

    def partition_roof_shape_based(poly, num_sections=3):
        minx, miny, maxx, maxy = poly.bounds
        section_width = (maxx - minx) / num_sections
        sections = []
        for i in range(num_sections):
            sec_minx = minx + i * section_width
            section = box(sec_minx, miny, sec_minx + section_width, maxy).intersection(poly)
            if not section.is_empty:
                sections.append(section)
        return sections

    def optimize_section(section, roof_poly, panels):
        sec_minx, sec_miny, sec_maxx, sec_maxy = section.bounds
        eff_sec_minx = sec_minx + 0.025
        eff_sec_miny = sec_miny + 0.075
        eff_sec_maxx = sec_maxx - 0.025
        eff_sec_maxy = sec_maxy - 0.075
        if eff_sec_maxx <= eff_sec_minx or eff_sec_maxy <= eff_sec_miny:
            return [], 0

        placements = []
        total_area = 0
        sorted_panels = sorted(panels, key=lambda p: p['eff_len'] * p['eff_wid'], reverse=True)
        y = eff_sec_miny
        while y < eff_sec_maxy:
            x = eff_sec_minx
            while x < eff_sec_maxx:
                placed = False
                for panel in sorted_panels:
                    rect_shape = box(x, y, x + panel['eff_len'], y + panel['eff_wid'])
                    if section.contains(rect_shape) and roof_poly.buffer(-0.01, join_style=2).contains(rect_shape):
                        placements.append({
                            'type': panel['type'],
                            'x': x,
                            'y': y,
                            'length': panel['proj_len'],
                            'width': panel['proj_wid'],
                            'color': {'small': 'lightgreen', 'medium': 'orange', 'large': 'lightblue'}[panel['type']],
                        })
                        total_area += panel['proj_len'] * panel['proj_wid']
                        x += panel['eff_len']
                        placed = True
                        break
                if not placed:
                    x += 0.5
            y += max(p['eff_wid'] for p in panels)
        return placements, total_area

    sections = partition_roof_shape_based(rotated_poly, num_sections=3)
    all_placements = []
    total_area = 0
    for section in sections:
        section_placements, section_area = optimize_section(section, rotated_poly, panels)
        all_placements.extend(section_placements)
        total_area += section_area
    return all_placements, total_area, optimal_azimuth, rotation_angle, 'Optimal Azimuth (With Sections)'

# -----------------------------
# Run All Methods and Select Best by Effective Area
# -----------------------------
poly = footprint_proj

# Compute panel dimensions once
tilt_angle_deg = optimal_tilt
panels = compute_panel_dimensions_with_tilt(panel_specs, tilt_angle_deg)

# Run all 4 methods
method_results = []

# Method 1
placements1, area1, azimuth1, rotation_angle1, name1 = optimize_method_1(poly, panels, optimal_azimuth)
method_results.append((placements1, area1, azimuth1, rotation_angle1, name1))

# Method 2
placements2, area2, azimuth2, rotation_angle2, name2 = optimize_method_2(poly, panels, optimal_azimuth)
method_results.append((placements2, area2, azimuth2, rotation_angle2, name2))

# Method 3
placements3, area3, azimuth3, rotation_angle3, name3 = optimize_method_3(poly, panels, optimal_azimuth)
method_results.append((placements3, area3, azimuth3, rotation_angle3, name3))

# Method 4
placements4, area4, azimuth4, rotation_angle4, name4 = optimize_method_4(poly, panels, optimal_azimuth)
method_results.append((placements4, area4, azimuth4, rotation_angle4, name4))

# Calculate effective area for each method
method_results_with_effective = []
for result in method_results:
    placements, total_area, azimuth, rotation_angle, name = result
    angle_diff = abs(azimuth - optimal_azimuth)
    angle_diff = min(angle_diff, 360 - angle_diff)
    if angle_diff > 90:
        effective_area = 0
    else:
        effective_area = total_area * math.cos(math.radians(angle_diff))
    method_results_with_effective.append((effective_area, placements, total_area, azimuth, rotation_angle, name))

# Find best method by effective area
best_result = max(method_results_with_effective, key=lambda x: x[0])
best_effective, best_placements, best_total, best_azimuth, best_rotation_angle, best_name = best_result

# Count panel types
panel_counts = {'small': 0, 'medium': 0, 'large': 0}
for placement in best_placements:
    panel_counts[placement['type']] += 1

# Print best result
print(f"\nBest Method: {best_name}")
print(f"Total Panel Area: {best_total:.2f} m²")
print(f"Effective Panel Area: {best_effective:.2f} m²")
print(f"Roof Area: {roof_area:.2f} m²")
print(f"Coverage: {best_total / roof_area * 100:.2f}%")
print(f"Effective Coverage: {best_effective / roof_area * 100:.2f}%")
print(f"Panel counts: {panel_counts}")
print(f"Panel Azimuth: {best_azimuth:.2f}°")

# -----------------------------
# Final Visualization (Real-Life Orientation)
# -----------------------------
fig, ax = plt.subplots(figsize=(12, 12), dpi=300)

# Plot original roof in projected system
x, y = footprint_proj.exterior.xy
ax.plot(x, y, color='blue', linewidth=2, label="Roof Outline")

# Plot panels
centroid = footprint_proj.centroid
cx, cy = centroid.x, centroid.y

for placement in best_placements:
    rect_patch = plt.Rectangle(
        (placement['x'], placement['y']),
        placement['length'], placement['width'],
        facecolor=placement['color'],
        edgecolor='black',
        alpha=0.8
    )
    trans = mtransforms.Affine2D().rotate_deg_around(cx, cy, -best_rotation_angle) + ax.transData
    ax.add_patch(plt.Rectangle(
        (placement['x'], placement['y']),
        placement['length'], placement['width'],
        facecolor=placement['color'],
        edgecolor='black',
        alpha=0.8,
        transform=trans
    ))

# Set limits based on original projected roof
minx, miny, maxx, maxy = footprint_proj.bounds
ax.set_xlim(minx - 1, maxx + 1)
ax.set_ylim(miny - 1, maxy + 1)

# Final plot settings
ax.set_title(f"Best Layout: {best_name}\nEffective Coverage: {best_effective / roof_area * 100:.2f}%")
ax.set_aspect('equal')
ax.legend()
plt.xlabel("Easting (m)")
plt.ylabel("Northing (m)")
plt.tight_layout()
# plt.savefig(f"best_solar_placement_{best_name.replace(' ', '_')}.png", dpi=300, bbox_inches='tight')
# plt.savefig(f"best_solar_placement_{best_name.replace(' ', '_')}.svg", format='svg', bbox_inches='tight')
plt.show()

# Get roof centroid and rotation info
centroid = footprint_proj.centroid
cx, cy = centroid.x, centroid.y

# Prepare output list
panel_vertices = []

# Process each panel in best_placement
for idx, placement in enumerate(best_placements):
    # Extract panel data
    x = placement['x']
    y = placement['y']
    length = placement['length']
    width = placement['width']
    panel_type = placement['type']

    # Define the "left" vertex in rotated system (bottom-left of the panel)
    left_vertex = Point(x, y)

    # Rotate back to real-life system
    real_vertex = shapely_rotate(left_vertex, -best_rotation_angle, origin=(cx, cy), use_radians=False)

    # Append to output
    panel_vertices.append({
        'id': idx + 1,
        'type': panel_type,
        'x_real': real_vertex.x,
        'y_real': real_vertex.y
    })

# Export to CSV
csv_filename = "panel_left_vertices_real_world.csv"
with open(csv_filename, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["Panel ID", "Type", "Easting (X, meters)", "Northing (Y, meters)"])
    for vertex in panel_vertices:
        writer.writerow([
            vertex['id'],
            vertex['type'],
            f"{vertex['x_real']:.4f}",
            f"{vertex['y_real']:.4f}"
        ])

print(f"Left vertex coordinates saved to {csv_filename}")