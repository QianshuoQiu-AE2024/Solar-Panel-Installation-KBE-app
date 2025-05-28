from parapy.core import Base, Input, Attribute, Part
import requests
from parapy.geom import Rectangle, Face, Point, Vector
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import box
from shapely.affinity import rotate as shapely_rotate
import math


class OptimizedPlacement(Base):
    roof_face = Input()
    coords = Input()

    @Attribute
    def roof_normal(self):
        return self.roof_face.plane_normal.normalized

    @Attribute
    def roof_poly(self):
        # Use outer wire (boundary) of face
        xy = [(v.point.x, v.point.y) for v in self.roof_face.outer_wire.vertices]
        return ShapelyPolygon(xy)

    @Attribute
    def optimal_angles(self):
        # PVGIS request
        peakpower_kwp = 1 # IGNORE, Not important for optimal angles
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
        response = requests.get("https://re.jrc.ec.europa.eu/api/v5_2/PVcalc", params=params)
        data = response.json()
        optimal_tilt = data['inputs']['mounting_system']['fixed']['slope']['value']
        optimal_azimuth = data['inputs']['mounting_system']['fixed']['azimuth']['value']
        return [optimal_azimuth, optimal_tilt]

    @Attribute
    def tilt_angle_deg(self):
        if self.roof_poly:
            tilt = self.optimal_angles[1]
        else:
            tilt = self.roof_poly
        return tilt

    @Attribute
    def optimal_azimuth(self):
        return self.optimal_angles[0]



    # -----------------------------
    # Reusable Functions
    # -----------------------------
    def calculate_solar_radiation(self, tilt, azimuth):
        """
        Calls PVGIS seriescalc API to get average daily solar radiation (kWh/m²/day)
        using the specified tilt and azimuth.
        """
        radiation_url = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"

        params = {
            'lat': self.coords[0],  # Latitude
            'lon': self.coords[1],  # Longitude
            'angle': tilt,  # Panel tilt (slope)
            'aspect': azimuth,  # Panel azimuth
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
                daily_solrad = total_radiation_wh / 1000 / num_days  # kWh/m²/day
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

    # Panel types
    @Attribute
    def panel_specs(self):
        return [
        {'type': 'large', 'length': 0.991, 'width': 1.956},
        {'type': 'medium', 'length': 0.991, 'width': 1.65},
        {'type': 'small', 'length': 0.991, 'width': 0.991},]


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
                'eff_wid': eff_wid
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
                                'color': {'small': 'lightgreen', 'medium': 'orange', 'large': 'lightblue'}[
                                    panel['type']],
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
            section_placements, section_area = optimize_section(section, rotated_poly, self.panels)
            all_placements.extend(section_placements)
            total_area += section_area
        return [all_placements, total_area, best_dir, rotation_angle, 'Wall-Aligned (With Sections)']

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
                                'color': {'small': 'lightgreen', 'medium': 'orange', 'large': 'lightblue'}[
                                    panel['type']],
                            })
                            total_area += panel['proj_len'] * panel['proj_wid']
                            x += panel['eff_len']
                            placed = True
                            break
                    if not placed:
                        x += 0.5
                y += max_eff_wid
            return placements, total_area

        placements, total_area = non_staggered_placement(rotated_poly, self.panels)
        return [placements, total_area, best_dir, rotation_angle, 'Wall-Aligned (No Sections)']

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
                                'color': {'small': 'lightgreen', 'medium': 'orange', 'large': 'lightblue'}[
                                    panel['type']],
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

        placements, total_area = staggered_placement(rotated_poly, self.panels)
        return placements, total_area, self.optimal_azimuth, rotation_angle, 'Optimal Azimuth (No Sections)'

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
                                'color': {'small': 'lightgreen', 'medium': 'orange', 'large': 'lightblue'}[
                                    panel['type']],
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
            section_placements, section_area = optimize_section(section, rotated_poly, self.panels)
            all_placements.extend(section_placements)
            total_area += section_area
        return all_placements, total_area, self.optimal_azimuth, rotation_angle, 'Optimal Azimuth (With Sections)'

    #@Attribute
    #def best_result(self): # NEEDS TO BE CHANGED!!!!!!!!!!!!!
        #print(self.optimize_method_1)
        #return self.optimize_method_1

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
            area = method[1]

            try:
                solar_radiation = self.calculate_solar_radiation(self.tilt_angle_deg, azimuth)
                total_radiation = area * solar_radiation
            except Exception as e:
                print(f"Error calculating radiation for {method[4]}: {e}")
                continue

            results.append({
                'method': method,
                'total_radiation': total_radiation
            })

        best = max(results, key=lambda x: x['total_radiation'])

        print(f"Best Method: {best['method'][4]} | Total Solar Radiation: {best['total_radiation']:.2f} kWh/day")

        # Return the best method result and its total radiation
        return best['method'], best['total_radiation']

    @Attribute
    def solar_panel_placement(self):
        best_placements = self.best_result[0][0]  # Access placements from the best method
        panel_vertices = []
        for idx, placement in enumerate(best_placements):
            left_vertex = ShapelyPoint(placement['x'], placement['y'])
            real_vertex = shapely_rotate(
                left_vertex,
                -self.best_result[0][3],  # Use rotation_angle from best method
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
        return [
            Point(vertex['x_real'], vertex['y_real'], self.roof_face.cog.z)
            for vertex in self.solar_panel_placement]

    @Attribute(in_tree=True)
    def real_points(self):
        z = self.roof_face.plane_normal.normalized

        # Choose a non-parallel reference vector
        reference = Vector(1, 0, 0) if abs(z.dot(Vector(0, 0, 1))) > 0.99 else Vector(0, 0, 1)
        x = z.in_plane_orthogonal(reference, normalize=True)
        y = z.cross(x).normalized
        origin = self.roof_face.cog

        return [
            flat_pt.project(ref=origin, axis1=x, axis2=y)
            for flat_pt in self.flat_points
        ]


if __name__ == '__main__':
    from parapy.gui import display

    obj = OptimizedPlacement(roof_face=Face(Rectangle(width=7, length=4)), coords=[30.370216, 12.895168])
    display(obj)



