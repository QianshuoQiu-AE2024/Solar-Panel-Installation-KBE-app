from parapy.core import Base, Input, Attribute, Part, child
from parapy.geom import Face, Point, LineSegment, Wire
from shapely.geometry import Polygon as ShapelyPolygon
from GableRoof import GableRoof
from tkinter import Tk, messagebox


class Roof(Base):
    """
    Composite roof consisting of a standard flat surface with
    any number of gable roofs that are carved out of it.

    The gables are defined by **indices** into the list of
    ``base_vertexes`` passed from :class:`House`.

    Validation
    ----------
    * Each entry in :pyattr:`gable_roof_indices` must be a list/tuple of
      **exactly four or zero integers** – corresponding to the rectangular patch
      that forms a single gable roof.
    * Violations raise :class:`ValueError` *and* show a Tk warning pop-up
      so that interactive users see the problem immediately.

    Inputs
    ----------
    gable_roof_indices : list[list[int]]
        2-D array of 4-int index lists; empty 2D list means “no gables”.
    slope_height : float, default 2 m
        Vertical rise of every gable ridge.
    base_height : float
        Z level of the roof’s footprint (usually the top floor slab).
    base_vertexes : Sequence[parapy.geom.Point]
        Planar polygon that delimits the *outer* roof shape.
    footprint : shapely.Polygon
        Same outline, but as Shapely geometry (used for differences etc.).

    Parts
    -----
    gable_roofs : list[:class:`GableRoof`]
    roof_faces  : list[parapy.geom.Face]
        Union of all flat + sloped faces; drives the solar panel array installer.
    """

    # Create a Tk root window to use for pop-up dialogs
    def _popup_error(self, title: str, msg: str):
        dlg = Tk()
        dlg.withdraw()  # hide the root window
        messagebox.showerror(title, msg)  # modal dialog
        dlg.destroy()

    def _validate_gable_indices(self, val):
        # Must be an outer list/tuple
        if not isinstance(val, (list, tuple)):
            msg = (f"`gable_roof_indices` must be a list/tuple of 4-element "
                   f"lists, got {type(val).__name__}.")
            self._popup_error("Invalid gable_roof_indices", msg)
            raise ValueError(msg)

        # Check every sub-item
        for k, item in enumerate(val):
            if not isinstance(item, (list, tuple)):
                msg = (f"Entry #{k} must itself be a list/tuple, "
                       f"got {type(item).__name__}. "
                       f"Recommended to use 2D arrays: [[1, 2, 3, 4]].")
                self._popup_error("Invalid gable_roof_indices", msg)
                raise ValueError(msg)
            if not (len(item) == 4 or len(item) == 0):
                msg = f"Entry #{k} must have exactly 4 elements, got {len(item)}."
                self._popup_error("Invalid gable_roof_indices", msg)
                raise ValueError(msg)
            for j, idx in enumerate(item):
                if not isinstance(idx, int):
                    msg = (f"gable_roof_indices[{k}][{j}] must be an int, "
                           f"got {type(idx).__name__}.")
                    self._popup_error("Invalid gable_roof_indices", msg)
                    raise ValueError(msg)
        return True

    # gable_roof_indices are the indices of the base_vertexes
    # that define the corners of the gable roofs.
    # Each gable roof is defined by a list of 4 indices, e.g.:
    # [[4, 3, 2, 7], [1, 6, 8, 2]] means two gable roofs
    gable_roof_indices = Input([], validator=_validate_gable_indices, doc="List of 4-int index lists")
    slope_height = Input(2)  # Vertical rise of every gable ridge
    base_height = Input()  # Z level of the roof’s footprint (usually the top floor slab)
    base_vertexes = Input()  # Sequence of parapy.geom.Point defining the outer roof shape
    footprint = Input()  # Shapely Polygon defining the outer roof shape

    # Normalized footprint and snap coordinates to a grid
    # If footprint is not normalized, parapy cant handle the large numbers
    @Attribute
    def normalized_footprint(self):
        coords = list(self.footprint.exterior.coords)
        x0, y0 = coords[0]

        # Snap coordinates to a grid with resolution `res`
        def snap(x, res=0.05):
            return round(x / res) * res

        normalized_coords = [(snap(x - x0), snap(y - y0)) for x, y in coords]
        return ShapelyPolygon(normalized_coords)

    # Define the flat roof as polygon without the gable roofs
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
        # if there's no flat area at all, skip it entirely
        if self.flat_roof.is_empty or self.flat_roof.area < 1e-6:
            return []

        wires = []
        polygons = ([self.flat_roof]
                    if self.flat_roof.geom_type == "Polygon"
                    else list(self.flat_roof.geoms))

        for poly in polygons:
            coords = list(poly.exterior.coords)
            # build points + segments only if at least 3 points
            if len(coords) < 3:
                continue
            pts = [Point(x, y, self.base_height) for x, y in coords]
            segments = [LineSegment(pts[i], pts[i + 1])
                        for i in range(len(pts) - 1)]
            wires.append(Wire(segments))

        return wires

    # Make the gable roofs
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

    # Get all roof wires, including flat and gable roofs
    @Attribute(in_tree=True)
    def roof_wires(self):
        return self.flat_roof_wires + \
            [child.roof_wire_1 for child in self.gable_roofs] + \
            [child.roof_wire_2 for child in self.gable_roofs]

    # Create the roof faces from the flat roof and gable roofs
    @Part
    def roof_faces(self):
        return Face(quantify=len(self.roof_wires), island=self.roof_wires[child.index])


if __name__ == '__main__':
    from parapy.gui import display

    obj = Roof(gable_roof_vertexes=[[4, 3, 2, 7], [1, 6, 8, 2]])
    display(obj)