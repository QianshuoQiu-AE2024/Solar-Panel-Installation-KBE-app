from parapy.core import Attribute, Part, Input
from parapy.geom import GeomBase, Point, LineSegment, Wire, Plane, Face, LoftedSolid, Vector
import numpy as np


class GableRoof(GeomBase):
    """
    Builds a single symmetric gable roof from four base vertices.

    The constructor derives two *sloped* quadrilateral faces and a
    lofted solid:

    0,1 –> ridge –> 4,5
          ^            ^
          |            |
          p0,p1      p2,p3  (indices refer to *roof_pts*)

    Inputs
    ----------
    base_height : float
        Z-level of the flat roof (bottom of the sloped planes).
    gable_roof_vertexes : Sequence[parapy.geom.Point]
        Exactly **four** corner points in clockwise order.
    slope_height : float
        Vertical rise between the flat roof and the ridge line.

    Important Attributes
    ----------
    roof_pts : list[parapy.geom.Point]
        Convenience list containing the 6 key vertices used downstream.
    roof_wire_1 / roof_wire_2 : parapy.geom.Wire
        Line segment construction of each sloped face – used both for creating
        the roof faces.
    roof_plane_1 / roof_plane_2 : parapy.geom.Plane
        Planes on which the roof wires are projected to obtain a planar sloped
        roof face.
    roof_faces : list[parapy.geom.Face]
        The actual sloped faces (two per roof pitch).

    Parts
    -----
    gable_roof_solid : parapy.geom.LoftedSolid
        Toy representation of the gable mass-model (optional).
    """

    base_height = Input()
    gable_roof_vertexes = Input()
    slope_height = Input()

    # Calculate ridge end and start points based on the four input vertexes.
    @Attribute
    def roof_pts(self):
        p0, p1, p2, p3 = self.gable_roof_vertexes
        ridge_start = Point((p0.x + p1.x) / 2, (p0.y + p1.y) / 2, self.base_height + self.slope_height)
        ridge_end = Point((p2.x + p3.x) / 2, (p2.y + p3.y) / 2, self.base_height + self.slope_height)
        return [Point(p0.x, p0.y, self.base_height),
                Point(p1.x, p1.y, self.base_height),
                ridge_start,
                ridge_end,
                Point(p2.x, p2.y, self.base_height),
                Point(p3.x, p3.y, self.base_height)]

    # Wire of the flat part of the roof
    # Only used for the solid representation
    @Attribute(in_tree=True)
    def roof_wire_0(self):
        return Wire([LineSegment(self.roof_pts[0], self.roof_pts[1]),
                     LineSegment(self.roof_pts[1], self.roof_pts[4]),
                     LineSegment(self.roof_pts[4], self.roof_pts[5]),
                     LineSegment(self.roof_pts[5], self.roof_pts[0])])

    # Plane of first sloped roof face
    # Used to project wire onto
    @Attribute()
    def roof_plane_1(self):
        pts = [self.roof_pts[1], self.roof_pts[2], self.roof_pts[3], self.roof_pts[4]]
        arr = np.array([[pt.x, pt.y, pt.z] for pt in pts])
        centroid = np.mean(arr, axis=0)
        shifted = arr - centroid
        _, _, vh = np.linalg.svd(shifted)
        normal = vh[-1]
        normal = Vector(*normal)
        # This makes sure the nromal points upwards
        if normal.z < 0:
            normal = Vector(-normal.x, -normal.y, -normal.z)
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
        normal = Vector(*normal)
        # This makes sure the nromal points upwards
        if normal.z < 0:
            normal = Vector(-normal.x, -normal.y, -normal.z)
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
        # Order of points is reversed in order ot make normal of face point upwards
        return Wire([LineSegment(projected_pts[0], projected_pts[3]),
                     LineSegment(projected_pts[3], projected_pts[2]),
                     LineSegment(projected_pts[2], projected_pts[1]),
                     LineSegment(projected_pts[1], projected_pts[0])])

    @Attribute(in_tree=True)
    def roof_wire_2_solid(self):
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

    @Attribute
    def roof_faces(self):
        return [Face(self.roof_wire_1), Face(self.roof_wire_2)]

    @Part
    def gable_roof_solid(self):
        return LoftedSolid(profiles=[self.roof_wire_1, self.roof_wire_2_solid])

