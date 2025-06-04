from parapy.core import Base, Input, Attribute, Part
import requests
from parapy.geom import Rectangle, Face, Point, Vector, Position
from parapy.core.widgets import TextField
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import box
from shapely.affinity import rotate as shapely_rotate
import math

from Experimentation.optimizer_withSectioning import tilt_angle_deg


class SolarRadiationDisplay(Base):
    annual_radiation = Input(
        0.0,
        label="Annual Solar Radiation (kWh/year)",
        widget=TextField()
    )


class OptimizedPlacement(Base):
    roof_face = Input()
    coords = Input()
    budget = Input(10000000000)  # Default budget

    @Attribute
    def roof_normal(self):
        return self.roof_face.plane_normal.normalized

    @Attribute
    def roof_poly(self):
        xy = [(v.point.x, v.point.y) for v in self.roof_face.outer_wire.vertices]
        return ShapelyPolygon(xy)

    @Attribute
    def optimal_angles(self):
        peakpower_kwp = 1
        params = {
            'lat': self.coords[0],
            'lon': self.coords[1],
            'outputformat': 'json',
            'mountingplace': 'building',
            'peakpower': peakpower_kwp,
            'loss': 14,
            'optimalangles': 1,
            'usehorizon': 1
        }
        response = requests.get("https://re.jrc.ec.europa.eu/api/v5_2/PVcalc",  params=params)
        data = response.json()
        optimal_tilt = data['inputs']['mounting_system']['fixed']['slope']['value']
        optimal_azimuth = data['inputs']['mounting_system']['fixed']['azimuth']['value']
        return [optimal_azimuth, optimal_tilt]

    from parapy.geom import Position, Vector

    @Attribute
    def tilt_xy(self):
        if self.roof_face.plane_normal.is_parallel(Vector(0, 0, 1), tol=1e-2):
            # FLAT ROOF: tilt south by optimal tilt angle
            tilt_rad = math.radians(self.optimal_angles[1])
            normal = Vector(0, -math.sin(tilt_rad), math.cos(tilt_rad)).normalized
        else:
            # SLOPED ROOF: use actual normal
            normal = self.roof_normal

        # Pitch: rotation about X (tilt in Y direction)
        pitch_rad = math.atan2(-normal.y, normal.z)
        pitch_deg = math.degrees(pitch_rad)

        # Roll: rotation about Y (tilt in X direction)
        roll_rad = math.atan2(normal.x, normal.z)
        roll_deg = math.degrees(roll_rad)
        return [pitch_deg, roll_deg]

    @Attribute
    def tilt_angle_deg(self):
        if self.roof_face.plane_normal.is_parallel(Vector(0, 0, 1), tol=1e-2):
            tilt = self.optimal_angles[1]
        else:
            tilt = math.degrees(self.roof_normal.angle(Vector(0, 0, 1)))
        return tilt

    @Attribute
    def optimal_azimuth(self):
        return self.optimal_angles[0]

    def calculate_solar_radiation(self, tilt, azimuth):
        radiation_url = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"
        params = {
            'lat': self.coords[0],
            'lon': self.coords[1],
            'angle': tilt,
            'aspect': azimuth,
            'outputformat': 'json',
            'pvcalculation': 1,
            'peakpower': 1,
            'loss': 14,
            'usehorizon': 1
        }
        try:
            response = requests.get(radiation_url, params=params)
            if response.status_code == 200:
                data = response.json()
                hourly_data = data.get('outputs', {}).get('hourly', [])
                if not hourly_data:
                    print("No hourly data in radiation response")
                    return 0
                total_radiation_wh = sum(hour.get('G(i)', 0) for hour in hourly_data)
                num_days = len(hourly_data) / 24
                daily_solrad = total_radiation_wh / 1000 / num_days
                print('Azimuth:', azimuth)
                print("Average daily radiation:", daily_solrad)
                return daily_solrad
            else:
                print(f"Radiation API returned status {response.status_code}")
                print(f"Response text: {response.text[:500]}...")
                return 0
        except Exception as e:
            print(f"Radiation API call failed: {e}")
            return 0

    def calculate_bearing(self, p1, p2):
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        angle_rad = math.atan2(dy, dx)
        return math.degrees(angle_rad) % 360

    def compute_wall_directions(self, poly):
        coords = list(poly.exterior.coords)
        wall_directions = []
        for i in range(len(coords) - 1):
            p1, p2 = coords[i], coords[i + 1]
            edge_dir = self.calculate_bearing(p1, p2)
            wall_directions.append((edge_dir + 90) % 360)
        return wall_directions

    def find_closest_direction(self, wall_directions, target_azimuth):
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

    def rotate_polygon_to_azimuth(self, poly, target_azimuth):
        rotation_angle = -target_azimuth + 90
        return shapely_rotate(poly, rotation_angle, origin='centroid', use_radians=False)

    @Attribute
    def panel_specs(self):
        return [
            {'type': 'large', 'length': 0.991, 'width': 1.956, 'cost': 95},
            {'type': 'medium', 'length': 0.991, 'width': 1.65, 'cost': 75},
            {'type': 'small', 'length': 0.991, 'width': 0.991, 'cost': 50},
        ]

    @Attribute
    def panels(self):
        tilt_rad = math.radians(self.tilt_angle_deg)
        panels = []
        for spec in self.panel_specs:
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
                'eff_wid': eff_wid,
                'cost': spec['cost']
            })
        return panels

    # -----------------------------
    # Method 1: Wall-Aligned + Sections
    # -----------------------------
    @Attribute
    def optimize_method_1(self):
        wall_directions = self.compute_wall_directions(self.roof_poly)
        best_dir = self.find_closest_direction(wall_directions, self.optimal_azimuth)
        rotated_poly = self.rotate_polygon_to_azimuth(self.roof_poly, best_dir)
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

        def optimize_section(section, roof_poly, panels, remaining_budget):
            sec_minx, sec_miny, sec_maxx, sec_maxy = section.bounds
            eff_sec_minx = sec_minx + 0.025
            eff_sec_miny = sec_miny + 0.075
            eff_sec_maxx = sec_maxx - 0.025
            eff_sec_maxy = sec_maxy - 0.075
            if eff_sec_maxx <= eff_sec_minx or eff_sec_maxy <= eff_sec_miny:
                return [], 0, 0, {'small': 0, 'medium': 0, 'large': 0}

            placements = []
            total_area = 0
            total_cost = 0
            panel_counts = {'small': 0, 'medium': 0, 'large': 0}
            sorted_panels = sorted(panels, key=lambda p: p['eff_len'] * p['eff_wid'], reverse=True)
            y = eff_sec_miny

            while y < eff_sec_maxy:
                x = eff_sec_minx
                while x < eff_sec_maxx:
                    placed = False
                    for panel in sorted_panels:
                        panel_cost = panel['cost']
                        if total_cost + panel_cost > remaining_budget:
                            continue
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
                            total_cost += panel_cost
                            panel_counts[panel['type']] += 1
                            x += panel['eff_len']
                            placed = True
                            break
                    if not placed:
                        x += 0.5
                    y += max(p['eff_wid'] for p in panels)

            print(f"Method 1 - Wall-Aligned (With Sections):")
            print(f"Total Cost: {total_cost}")
            print(f"Panel Counts: Small={panel_counts['small']}, Medium={panel_counts['medium']}, Large={panel_counts['large']}")
            return placements, total_area, total_cost, panel_counts

        sections = partition_roof_shape_based(rotated_poly, num_sections=3)
        all_placements = []
        total_area = 0
        total_cost = 0
        panel_counts = {'small': 0, 'medium': 0, 'large': 0}

        for section in sections:
            remaining_budget = self.budget - total_cost
            section_placements, section_area, section_cost, section_counts = optimize_section(section, rotated_poly, self.panels, remaining_budget)
            all_placements.extend(section_placements)
            total_area += section_area
            total_cost += section_cost
            for k in panel_counts:
                panel_counts[k] += section_counts[k]
            if total_cost >= self.budget:
                break

        return [all_placements, total_area, best_dir, rotation_angle, 'Wall-Aligned (With Sections)', total_cost, panel_counts]

    # -----------------------------
    # Method 2: Wall-Aligned (No Sections)
    # -----------------------------
    @Attribute
    def optimize_method_2(self):
        wall_directions = self.compute_wall_directions(self.roof_poly)
        best_dir = self.find_closest_direction(wall_directions, self.optimal_azimuth)
        rotation_angle = -best_dir + 90
        rotated_poly = self.rotate_polygon_to_azimuth(self.roof_poly, best_dir)

        def non_staggered_placement(roof_poly, panels):
            minx, miny, maxx, maxy = roof_poly.bounds
            placements = []
            total_area = 0
            total_cost = 0
            panel_counts = {'small': 0, 'medium': 0, 'large': 0}
            sorted_panels = sorted(panels, key=lambda p: p['eff_len'] * p['eff_wid'], reverse=True)
            max_eff_wid = max(p['eff_wid'] for p in panels)
            y = miny

            while y < maxy:
                x = minx
                while x < maxx:
                    placed = False
                    for panel in sorted_panels:
                        panel_cost = panel['cost']
                        if total_cost + panel_cost > self.budget:
                            continue
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
                            total_cost += panel_cost
                            panel_counts[panel['type']] += 1
                            x += panel['eff_len']
                            placed = True
                            break
                    if not placed:
                        x += 0.5
                    y += max_eff_wid

            print(f"Method 2 - Wall-Aligned (No Sections):")
            print(f"Total Cost: {total_cost}")
            print(f"Panel Counts: Small={panel_counts['small']}, Medium={panel_counts['medium']}, Large={panel_counts['large']}")
            return placements, total_area, total_cost, panel_counts

        placements, total_area, total_cost, panel_counts = non_staggered_placement(rotated_poly, self.panels)
        return [placements, total_area, best_dir, rotation_angle, 'Wall-Aligned (No Sections)', total_cost, panel_counts]

    # -----------------------------
    # Method 3: Optimal Azimuth (No Sections)
    # -----------------------------
    @Attribute
    def optimize_method_3(self):
        rotation_angle = -self.optimal_azimuth + 90
        rotated_poly = self.rotate_polygon_to_azimuth(self.roof_poly, self.optimal_azimuth)

        def staggered_placement(roof_poly, panels):
            minx, miny, maxx, maxy = roof_poly.bounds
            placements = []
            total_area = 0
            total_cost = 0
            panel_counts = {'small': 0, 'medium': 0, 'large': 0}
            sorted_panels = sorted(panels, key=lambda p: p['eff_len'] * p['eff_wid'], reverse=True)
            max_eff_wid = max(p['eff_wid'] for p in panels)
            row_index = 0
            y = miny

            while y < maxy:
                x = minx + ((row_index % 2) * max_eff_wid / 2)
                while x < maxx:
                    placed = False
                    for panel in sorted_panels:
                        panel_cost = panel['cost']
                        if total_cost + panel_cost > self.budget:
                            continue
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
                            total_cost += panel_cost
                            panel_counts[panel['type']] += 1
                            x += panel['eff_len']
                            placed = True
                            break
                    if not placed:
                        x += 0.5
                    y += max_eff_wid
                    row_index += 1

            print(f"Method 3 - Optimal Azimuth (No Sections):")
            print(f"Total Cost: {total_cost}")
            print(f"Panel Counts: Small={panel_counts['small']}, Medium={panel_counts['medium']}, Large={panel_counts['large']}")
            return placements, total_area, total_cost, panel_counts

        placements, total_area, total_cost, panel_counts = staggered_placement(rotated_poly, self.panels)
        return [placements, total_area, self.optimal_azimuth, rotation_angle, 'Optimal Azimuth (No Sections)', total_cost, panel_counts]

    # -----------------------------
    # Method 4: Optimal Azimuth + Roof Sectioning
    # -----------------------------
    @Attribute
    def optimize_method_4(self):
        rotation_angle = -self.optimal_azimuth + 90
        rotated_poly = self.rotate_polygon_to_azimuth(self.roof_poly, self.optimal_azimuth)

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

        def optimize_section(section, roof_poly, panels, remaining_budget):
            sec_minx, sec_miny, sec_maxx, sec_maxy = section.bounds
            eff_sec_minx = sec_minx + 0.025
            eff_sec_miny = sec_miny + 0.075
            eff_sec_maxx = sec_maxx - 0.025
            eff_sec_maxy = sec_maxy - 0.075
            if eff_sec_maxx <= eff_sec_minx or eff_sec_maxy <= eff_sec_miny:
                return [], 0, 0, {'small': 0, 'medium': 0, 'large': 0}

            placements = []
            total_area = 0
            total_cost = 0
            panel_counts = {'small': 0, 'medium': 0, 'large': 0}
            sorted_panels = sorted(panels, key=lambda p: p['eff_len'] * p['eff_wid'], reverse=True)
            y = eff_sec_miny

            while y < eff_sec_maxy:
                x = eff_sec_minx
                while x < eff_sec_maxx:
                    placed = False
                    for panel in sorted_panels:
                        panel_cost = panel['cost']
                        if total_cost + panel_cost > remaining_budget:
                            continue
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
                            total_cost += panel_cost
                            panel_counts[panel['type']] += 1
                            x += panel['eff_len']
                            placed = True
                            break
                    if not placed:
                        x += 0.5
                    y += max(p['eff_wid'] for p in panels)

            print(f"Method 4 - Optimal Azimuth (With Sections):")
            print(f"Total Cost: {total_cost}")
            print(f"Panel Counts: Small={panel_counts['small']}, Medium={panel_counts['medium']}, Large={panel_counts['large']}")
            return placements, total_area, total_cost, panel_counts

        sections = partition_roof_shape_based(rotated_poly, num_sections=3)
        all_placements = []
        total_area = 0
        total_cost = 0
        panel_counts = {'small': 0, 'medium': 0, 'large': 0}

        for section in sections:
            remaining_budget = self.budget - total_cost
            section_placements, section_area, section_cost, section_counts = optimize_section(section, rotated_poly, self.panels, remaining_budget)
            all_placements.extend(section_placements)
            total_area += section_area
            total_cost += section_cost
            for k in panel_counts:
                panel_counts[k] += section_counts[k]
            if total_cost >= self.budget:
                break

        return [all_placements, total_area, self.optimal_azimuth, rotation_angle, 'Optimal Azimuth (With Sections)', total_cost, panel_counts]

    # -----------------------------
    # Best Result with Budget and Solar Radiation
    # -----------------------------
    @Attribute
    def best_result(self):
        methods = [
            self.optimize_method_1,
            self.optimize_method_2,
            self.optimize_method_3,
            self.optimize_method_4,
        ]
        results = []

        for method in methods:
            azimuth = method[2]
            tilt_angle = self.tilt_angle_deg
            if self.tilt_angle_deg < 0:
                tilt_angle = -self.tilt_angle_deg
                azimuth += 180
            while azimuth > 180:
                azimuth -= 360
            while azimuth < -180:
                azimuth += 360
            area = method[1]
            try:
                solar_radiation = self.calculate_solar_radiation(tilt_angle, azimuth)
                total_radiation = area * solar_radiation
            except Exception as e:
                print(f"Error calculating radiation for {method[4]}: {e}")
                continue
            results.append({
                'method': method,
                'total_radiation': total_radiation
            })

        best = max(results, key=lambda x: x['total_radiation'])
        best_method = best['method']

        placements = best_method[0]
        total_panel_area = best_method[1]
        roof_area = self.roof_poly.area
        panel_counts = best_method[6]
        total_cost = best_method[5]

        print(f"Best Method: {best_method[4]}")
        # print(f"  Total Solar Radiation: {best['total_radiation']:.2f} kWh/day")
        # print(f"  Roof Area: {roof_area:.2f} m²")
        # print(f"  Total Solar Panel Area: {total_panel_area:.2f} m²")
        print(f"  Panel Counts: Small={panel_counts['small']}, Medium={panel_counts['medium']}, Large={panel_counts['large']}")
        print(f"  Total Cost: {total_cost:.2f} EUR")

        return best_method, best['total_radiation']

    # -----------------------------
    # Placement Data
    # -----------------------------
    @Attribute
    def solar_panel_placement(self):
        best_placements = self.best_result[0][0]
        panel_vertices = []
        for idx, placement in enumerate(best_placements):
            left_vertex = ShapelyPoint(placement['x'], placement['y'])
            real_vertex = shapely_rotate(
                left_vertex,
                -self.best_result[0][3],
                origin=(self.roof_poly.centroid.x, self.roof_poly.centroid.y),
                use_radians=False
            )
            panel_vertices.append({
                'id': idx + 1,
                'type': placement['type'],
                'x_real': real_vertex.x,
                'y_real': real_vertex.y
            })
        return panel_vertices

    @Attribute
    def flat_points(self):
        return [Point(p['x_real'], p['y_real'], 0) for p in self.solar_panel_placement]

    @Attribute(in_tree=True)
    def real_points(self):
        z = self.roof_face.plane_normal.normalized
        reference = Vector(1, 0, 0) if abs(z.dot(Vector(0, 0, 1))) > 0.99 else Vector(0, 0, 1)
        x = z.in_plane_orthogonal(reference, normalize=True)
        y = z.cross(x).normalized
        origin = self.roof_face.cog
        return [flat_pt.project(ref=origin, axis1=x, axis2=y) for flat_pt in self.flat_points]

    @Attribute
    def annual_solar_radiation(self):
        best_method_data = self.best_result[0]
        panel_counts = best_method_data[6]
        azimuth = best_method_data[2]

        total_actual_area = 0
        for panel_type in ['small', 'medium', 'large']:
            count = panel_counts.get(panel_type, 0)
            spec = next((spec for spec in self.panel_specs if spec['type'] == panel_type), None)
            if spec:
                total_actual_area += count * spec['length'] * spec['width']
        tilt_angle = self.tilt_angle_deg
        if self.tilt_angle_deg < 0:
            tilt_angle = -self.tilt_angle_deg
            azimuth += 180
        while azimuth > 180:
            azimuth -= 360
        while azimuth < -180:
            azimuth += 360
        daily_solrad = self.calculate_solar_radiation(tilt_angle, azimuth)
        annual_radiation = total_actual_area * daily_solrad * 365

        return annual_radiation

    @Part
    def solar_radiation_widget(self):
        return SolarRadiationDisplay(
            annual_radiation=str(self.annual_solar_radiation),
            label="Annual Solar Radiation"
        )
    # @Attribute(in_tree=True)
    # def test_face(self):
    #     return self.roof_face






if __name__ == '__main__':
    from parapy.gui import display
    obj = OptimizedPlacement(roof_face=Face(Rectangle(width=7, length=4)), coords=[30.370216, 12.895168])
    display(obj)