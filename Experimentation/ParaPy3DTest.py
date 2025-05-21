from parapy.core import *
from parapy.geom import *
import osmnx as ox
from shapely.geometry import MultiPolygon
from shapely.geometry import Polygon as ShapelyPolygon
import numpy as np
import math


class House(Base):
    address = Input()
    floors = Input()
    slope_height = Input(1.5)  # default slope
    dist = Input(5)
    roof_vertexes = Input()  # indices to form ridge rectangle, selected interactively
    is_correct_house = Input(True)
    selected_building_index = Input(0)

    @Attribute
    def nearby_buildings(self):
        """Get all building footprints around the address."""
        tags = {"building": True}
        gdf = ox.features_from_address(self.address, tags=tags, dist=self.dist)
        shapes = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])].geometry
        return list(shapes)

    @Attribute
    def building_outline_points(self):
        """Normalized building outlines relative to first polygon's origin."""
        results = []
        reference_geom = self.nearby_buildings[0]
        ref_poly = reference_geom if reference_geom.geom_type == "Polygon" else list(reference_geom.geoms)[0]
        ref_proj, _ = ox.projection.project_geometry(ref_poly)
        origin_x, origin_y = ref_proj.exterior.coords[0]

        for geom in self.nearby_buildings:
            geom = geom if geom.geom_type == "Polygon" else list(geom.geoms)[0]
            projected_geom, _ = ox.projection.project_geometry(geom)
            coords = [(x - origin_x, y - origin_y) for x, y in projected_geom.exterior.coords]
            points = [Point(x, y, 0) for x, y in coords]
            results.append(points)
        return results

    @Attribute
    def building_outline_centroids(self):
        return [Polygon(points=pts).cog for pts in self.building_outline_points]

    @Attribute
    def selected_footprint(self):
        """Either the first building or a user-selected alternative."""
        geom = self.nearby_buildings[self.selected_building_index]
        if isinstance(geom, MultiPolygon):
            geom = list(geom.geoms)[0]
        projected_geom, _ = ox.projection.project_geometry(geom)
        return projected_geom

    @Attribute
    def footprint(self):
        """This is the geometry the rest of the house is built on."""
        if self.is_correct_house:
            return self.selected_footprint
        else:
            return ShapelyPolygon()  # avoid crashing

    @Attribute
    def base_height(self):
        return self.floors * 2

    @Attribute(in_tree=True)
    def base_pts(self):
        coords = list(self.footprint.exterior.coords)
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        def snap(x, res=0.05):
            return round(x / res) * res

        return [Point(snap(x - coords[0][0]), snap(y - coords[0][1]), 0) for x, y in coords]

    @Attribute(in_tree=True)
    def extended_intersections(self):
        intersections = []
        base_xy = {(round(p.x, 6), round(p.y, 6)) for p in self.base_pts}

        for i in range(len(self.base_pts) - 1):
            for j in range(i + 1, len(self.base_pts) - 1):
                a1, a2 = self.base_pts[i], self.base_pts[i + 1]
                b1, b2 = self.base_pts[j], self.base_pts[j + 1]
                denom = (a1.x - a2.x) * (b1.y - b2.y) - (a1.y - a2.y) * (b1.x - b2.x)
                if abs(denom) > 1e-6:
                    px = ((a1.x * a2.y - a1.y * a2.x) * (b1.x - b2.x) - (a1.x - a2.x) * (
                                b1.x * b2.y - b1.y * b2.x)) / denom
                    py = ((a1.x * a2.y - a1.y * a2.x) * (b1.y - b2.y) - (a1.y - a2.y) * (
                                b1.x * b2.y - b1.y * b2.x)) / denom

                    def on_segment(p, q1, q2):
                        min_x, max_x = min(q1.x, q2.x), max(q1.x, q2.x)
                        min_y, max_y = min(q1.y, q2.y), max(q1.y, q2.y)
                        return min_x - 1e-6 <= p.x <= max_x + 1e-6 and min_y - 1e-6 <= p.y <= max_y + 1e-6

                    def snap(val, res=0.05):
                        return round(val / res) * res

                    p = Point(snap(px), snap(py), 0)
                    key = (round(p.x, 6), round(p.y, 6))
                    if key not in base_xy and (on_segment(p, a1, a2) or on_segment(p, b1, b2)):
                        intersections.append(p)
        return intersections

    @Attribute(in_tree=True)
    def combined_points(self):
        return self.base_pts + self.extended_intersections

    @Attribute
    def base_wire(self):
        segments = [LineSegment(start=self.base_pts[i], end=self.base_pts[i + 1])
                    for i in range(len(self.base_pts) - 1)]
        return Wire(segments)

    @Part
    def building_outlines(self):
        return Polygon(
            quantify=len(self.building_outline_points),
            points=self.building_outline_points[child.index],
            position=self.building_outline_centroids[child.index],
            color='gray',
            transparency=0.7
        )

    @Part
    def building_labels(self):
        return TextLabel(
            quantify=len(self.building_outline_points),
            text=str(child.index),
            position= self.building_outline_centroids[child.index],
            size=1.0,
            color='black'
        )

    @Part
    def base(self):
        return ExtrudedSolid(island=self.base_wire, distance=self.base_height)

    @Part
    def markers(self):
        return Sphere(
            radius=0.25,
            position=translate(self.combined_points[child.index-1], 'z', self.base_height),
            label=f"{child.index}",
            color='red',
            quantify=len(self.combined_points)
        )

    @Part
    def marker_labels(self):
        return TextLabel(
            quantify=len(self.combined_points),
            text=str(child.index),
            position=translate(self.combined_points[child.index-1], 'z', self.base_height + 0.5),
            size=0.8,
            color='red'
        )

    @Part
    def gable_roofs(self):
            return GableRoof(
                quantify=len(self.roof_vertexes),
                roof_vertexes=[self.combined_points[i] for i in self.roof_vertexes[child.index]],
                base_height=self.base_height,
                slope_height=self.slope_height
            )

class GableRoof(Base):
    roof_vertexes = Input()
    slope_height = Input()
    base_height = Input()

    @Attribute
    def roof_pts(self):
        p0, p1, p2, p3 = self.roof_vertexes
        ridge_start = Point((p0.x + p1.x) / 2, (p0.y + p1.y) / 2, self.base_height + self.slope_height)
        ridge_end = Point((p2.x + p3.x) / 2, (p2.y + p3.y) / 2, self.base_height + self.slope_height)
        return [Point(p0.x, p0.y, self.base_height),
                Point(p1.x, p1.y, self.base_height),
                ridge_start,
                ridge_end,
                Point(p2.x, p2.y, self.base_height),
                Point(p3.x, p3.y, self.base_height)]

    @Attribute(in_tree=True)
    def roof_wire_0(self):
        return Wire([LineSegment(self.roof_pts[0], self.roof_pts[1]),
                     LineSegment(self.roof_pts[1], self.roof_pts[4]),
                     LineSegment(self.roof_pts[4], self.roof_pts[5]),
                     LineSegment(self.roof_pts[5], self.roof_pts[0])])

    @Attribute()
    def roof_plane_1(self):
        pts = [self.roof_pts[1], self.roof_pts[2], self.roof_pts[3], self.roof_pts[4]]
        arr = np.array([[pt.x, pt.y, pt.z] for pt in pts])
        centroid = np.mean(arr, axis=0)
        shifted = arr - centroid
        _, _, vh = np.linalg.svd(shifted)
        normal = vh[-1]
        origin = Point(*centroid)
        return Plane(reference=origin, normal=Vector(*normal))


    @Attribute(in_tree=True)
    def roof_wire_1(self):
        pts = self.roof_pts
        projected_pts = [
            Point(float(p[0]), float(p[1]), float(p[2])) for p in [
                pts[1].project(ref=self.roof_plane_1.location,
                               axis1=self.roof_plane_1.orientation.x,
                               axis2=self.roof_plane_1.orientation.y),
                pts[2].project(ref=self.roof_plane_1.location,
                               axis1=self.roof_plane_1.orientation.x,
                               axis2=self.roof_plane_1.orientation.y),
                pts[3].project(ref=self.roof_plane_1.location,
                               axis1=self.roof_plane_1.orientation.x,
                               axis2=self.roof_plane_1.orientation.y),
                pts[4].project(ref=self.roof_plane_1.location,
                               axis1=self.roof_plane_1.orientation.x,
                               axis2=self.roof_plane_1.orientation.y)
            ]
        ]

        return Wire([LineSegment(projected_pts[0], projected_pts[1]),
                     LineSegment(projected_pts[1], projected_pts[2]),
                     LineSegment(projected_pts[2], projected_pts[3]),
                     LineSegment(projected_pts[3], projected_pts[0])])

    @Attribute()
    def roof_plane_2(self):
        pts = [self.roof_pts[0], self.roof_pts[2], self.roof_pts[3], self.roof_pts[5]]
        arr = np.array([[pt.x, pt.y, pt.z] for pt in pts])
        centroid = np.mean(arr, axis=0)
        shifted = arr - centroid
        _, _, vh = np.linalg.svd(shifted)
        normal = vh[-1]
        origin = Point(*centroid)
        return Plane(reference=origin, normal=Vector(*normal))


    @Attribute(in_tree=True)
    def roof_wire_2(self):
        pts = self.roof_pts
        projected_pts = [
            Point(float(p[0]), float(p[1]), float(p[2])) for p in [
                pts[0].project(ref=self.roof_plane_2.location,
                               axis1=self.roof_plane_2.orientation.x,
                               axis2=self.roof_plane_2.orientation.y),
                pts[2].project(ref=self.roof_plane_2.location,
                               axis1=self.roof_plane_2.orientation.x,
                               axis2=self.roof_plane_2.orientation.y),
                pts[3].project(ref=self.roof_plane_2.location,
                               axis1=self.roof_plane_2.orientation.x,
                               axis2=self.roof_plane_2.orientation.y),
                pts[5].project(ref=self.roof_plane_2.location,
                               axis1=self.roof_plane_2.orientation.x,
                               axis2=self.roof_plane_2.orientation.y)
            ]
        ]

        return Wire([LineSegment(projected_pts[0], projected_pts[1]),
                     LineSegment(projected_pts[1], projected_pts[2]),
                     LineSegment(projected_pts[2], projected_pts[3]),
                     LineSegment(projected_pts[3], projected_pts[0])])

    @Part
    def roof_face_1(self):
        return Face(self.roof_wire_1)

    @Part
    def roof_face_2(self):
        return Face(self.roof_wire_2)

    @Part
    def roof(self):
        return LoftedSolid(profiles=[self.roof_wire_1, self.roof_wire_2])

    @Part
    def solar_panel_on_roof(self):
        return SolarPanel(
            location=self.roof_face_1.cog,
            is_flat_roof=False,
            sync_inclination=True,
            roof_normal=self.roof_face_1.plane_normal,
            inclination=0  # this could be parameterized or vary
        )


class SolarPanel(GeomBase):
    length = Input(1.7)  # meters
    width = Input(1.0)   # meters
    inclination = Input(30)  # degrees from XY-plane
    azimuth = Input(180)  # degrees from North (used only on flat roofs)
    location = Input(ORIGIN)  # position of the panel's center
    is_flat_roof = Input(True)
    sync_inclination = Input(True)
    roof_normal = Input(Vector(0, 0, 1))  # required if not flat

    @Attribute
    def panel_position(self):
        """Compute the position of the solar panel."""
        if self.is_flat_roof:
            # Panel aligned by user-defined azimuth and inclination
            length_vec = Vector(1, 0, 0).rotate('z', math.radians(self.azimuth))
            vz = Vector(0, 0, 1).rotate(length_vec, math.radians(self.inclination))
        else:
            # Align with roof: vz = roof normal, vy = direction along roof
            vz = self.roof_normal.normalized
            # Assume roof slope is in x-direction of panel. Try to find a good vector orthogonal to vz.
            vy = vz.in_plane_orthogonal(Vector(0, 0, 1), normalize=True)
            # Incline by rotating vz around vy if inclination != 0
            incl = self.roof_normal.angle(Vector(0, 0, 1)) if self.sync_inclination else self.inclination
            if abs(incl) > 1e-3:
                vz = vz.rotate(vy, math.radians(incl))
            length_vec = vy

        vx = length_vec.cross(vz).normalized
        vy = length_vec.normalized
        return Position(self.location, orientation=Orientation(x=vx, y=vy))

    @Attribute
    def inclination_relative_to_roof(self):
        """Return angle between panel and roof (0 if flat roof)."""
        if self.is_flat_roof:
            return 0.0
        return math.degrees(self.roof_normal.angle(self.panel_position.Vz))

    @Part
    def panel(self):
        return Box(width=self.length,
                   length=self.width,
                   height=0.04,
                   position=self.panel_position,
                   color="blue",
                   centered=True)


if __name__ == '__main__':
    from parapy.gui import display
    # Populieren - [[22, 13, 15, 16], [22, 12, 11, 21], [21, 10, 9, 8]]
    obj = House(address="Slangenstraat 48", floors=2, roof_vertexes=[[4, 3, 2, 7], [1, 6, 8, 2]])
    display(obj)


