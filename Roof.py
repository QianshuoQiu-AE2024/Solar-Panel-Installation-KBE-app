from parapy.core import Base, Input, Attribute, Part, child
from parapy.geom import Face, Point, LineSegment, Wire
from shapely.geometry import Polygon as ShapelyPolygon
from GableRoof import GableRoof
import warnings


class Roof(Base):
    # ------------------------------------------------------------------
    # Custom validator for the gable-roof index input
    # ------------------------------------------------------------------
    def _validate_gable_indices(self, val):
        """
        Accepts only a list/tuple whose *items* are lists/tuples of **4 ints**,
        e.g. [[4, 3, 7, 5], [1, 8, 2, 6]].
        Raises ValueError (ParaPy shows this in the GUI) *and* gives a pop-up.
        """
        # 1) Must be an outer list/tuple
        if not isinstance(val, (list, tuple)):
            msg = (f"`gable_roof_indices` must be a list/tuple of 4-element "
                   f"lists, got {type(val).__name__}.")
            warnings.warn(msg)
            raise ValueError(msg)

        # 2) Check every sub-item
        for k, item in enumerate(val):
            if not isinstance(item, (list, tuple)):
                msg = (f"Entry #{k} must itself be a list/tuple, "
                       f"got {type(item).__name__}. Recommended to use a 2D array [[1, 2, 3, 4]].")
                warnings.warn(msg)
                raise ValueError(msg)
            if len(item) != 4:
                msg = f"Entry #{k} must have exactly 4 elements, got {len(item)}."
                warnings.warn(msg)
                raise ValueError(msg)
            for j, idx in enumerate(item):
                if not isinstance(idx, int):
                    msg = (f"gable_roof_indices[{k}][{j}] must be an int, "
                           f"got {type(idx).__name__}.")
                    warnings.warn(msg)
                    raise ValueError(msg)
        return True

    gable_roof_indices = Input([], validator=_validate_gable_indices, doc="List of 4-int index lists")
    slope_height = Input(2)
    base_height = Input()
    base_vertexes = Input()
    footprint = Input()


    @Attribute
    def normalized_footprint(self):
        """Return a normalized shapely polygon (shifted so first point is at (0,0))."""
        coords = list(self.footprint.exterior.coords)
        x0, y0 = coords[0]

        def snap(x, res=0.05):
            return round(x / res) * res

        normalized_coords = [(snap(x - x0), snap(y - y0)) for x, y in coords]
        return ShapelyPolygon(normalized_coords)

    @Attribute
    def flat_roof(self):
        flat_roof = self.normalized_footprint
        for gable in self.gable_roof_indices:
            gable_coords = [(self.base_vertexes[i].x, self.base_vertexes[i].y) for i in gable]
            gable_roof_poly = ShapelyPolygon(gable_coords)
            flat_roof = flat_roof.difference(gable_roof_poly)
        return flat_roof

    @Attribute
    def flat_roof_wires(self):
        wires = []

        polygons = [self.flat_roof] if self.flat_roof.geom_type == "Polygon" else list(self.flat_roof.geoms)

        for poly in polygons:
            coords = list(poly.exterior.coords)
            points = [Point(x, y, self.base_height) for x, y in coords]

            segments = [LineSegment(points[i], points[i + 1]) for i in range(len(points) - 1)]
            wire = Wire(segments)
            wires.append(wire)

        return wires

    @Part
    def gable_roofs(self):
        return GableRoof(
            quantify=len(self.gable_roof_indices),
            gable_roof_vertexes=[self.base_vertexes[i] for i in self.gable_roof_indices[child.index]],
            base_height=self.base_height,
            slope_height=self.slope_height)

    @Attribute
    def gable_roof_faces(self):
        return self.gable_roofs.roof_faces

    @Attribute(in_tree=True)
    def roof_wires(self):
        return self.flat_roof_wires + \
            [child.roof_wire_1 for child in self.gable_roofs] + \
            [child.roof_wire_2 for child in self.gable_roofs]

    @Part
    def roof_faces(self):
        return Face(quantify=len(self.roof_wires), island=self.roof_wires[child.index])

if __name__ == '__main__':
    from parapy.gui import display
    obj = Roof(gable_roof_vertexes=[[4, 3, 2, 7], [1, 6, 8, 2]])
    display(obj)