from parapy.core import *
from parapy.geom import *
import osmnx as ox
from shapely.geometry import MultiPolygon
import numpy as np

class TopologyElements(Base):
    address = Input()
    floors = Input()
    slope_height = Input(1.5)  # default slope
    dist = Input(5)
    selected_indices = Input([4, 3, 2, 7])  # indices to form ridge rectangle, selected interactively

    @Attribute
    def footprint(self):
        tags = {"building": True}
        gdf = ox.features_from_address(self.address, tags=tags, dist=self.dist)
        shapes = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
        geom = shapes.geometry.iloc[0]
        if isinstance(geom, MultiPolygon):
            geom = list(geom.geoms)[0]
        projected_geom, _ = ox.projection.project_geometry(geom)
        return projected_geom

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

    @Attribute(in_tree=True)
    def roof_pts(self):
        idx = self.selected_indices
        pts = self.combined_points
        if len(idx) < 4:
            return []

        p0, p1, p2, p3 = pts[idx[0]], pts[idx[1]], pts[idx[2]], pts[idx[3]]

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
        pts = self.roof_pts
        if not pts: return None
        return Wire([LineSegment(pts[0], pts[1]),
                     LineSegment(pts[1], pts[4]),
                     LineSegment(pts[4], pts[5]),
                     LineSegment(pts[5], pts[0])])

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
    def base(self):
        return ExtrudedSolid(island=self.base_wire, distance=self.base_height)

    @Part
    def roof_face_1(self):
        return Face(self.roof_wire_1)

    @Part
    def roof_face_2(self):
        return Face(self.roof_wire_2)

    @Part
    def roof(self):
        return LoftedSolid([self.roof_wire_1, self.roof_wire_2])

    @Part
    def markers(self):
        return Sphere(
            radius=0.25,
            position=translate(self.combined_points[child.index], 'z', self.base_height),
            label=f"{child.index}",
            color='red',
            quantify=len(self.combined_points)
        )


if __name__ == '__main__':
    from parapy.gui import display
    obj = TopologyElements(address="Slangenstraat 48", floors=2)
    display(obj)

