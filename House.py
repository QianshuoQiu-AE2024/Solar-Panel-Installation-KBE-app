from parapy.core import Base, Input, Attribute, Part, child
from parapy.geom import Wire, LineSegment, Point, ExtrudedSolid, Vector
from Map import Map
from Marker import Marker
from Roof import Roof
from SolarPanelArray import SolarPanelArray
from parapy.exchange.step import STEPWriter
from Summary import Summary
from TextWriter import TextWriter




class House(Base):
    """
    High-level class that ties the whole program together.

    A :class:`House` object:

    * retrieves an OSM building footprint (:class:`Map`)
    * allows for cycling through different buildings around one address
    * constructs base floors, a roof (flat + optional gable roofs)
    * places set of optimal solar panel arrays on the roof
    * keeps track of the project budget and electricity savings
    * can export everything to STEP file
    * maks a summary with the financial result

    Inputs
    ----------
    address : str
        Free-format address understood by **osmnx**.
        Used to retrieve the main building footprint.
    floors : int
        Number of storeys.  Multiplies with ``floor_height`` to get the
        extrusion height.
    budget : float
        Maximum amount (EUR) available for PV installation. This si a first estimate, will
        deviate from the final cost.
    electrical_efficiency : float
        Static, user-tunable DC/AC efficiency factor (η\_AC).
    base_height : float
        Total extrusion height (= ``floors * floor_height``).

    Important attributes
    --------------------
    base_pts : list[parapy.geom.Point]
        Footprint vertices expressed in a local XY frame (z = 0).
    extended_pts : list[parapy.geom.Point]
        Extra point used to construct gable roof.
    summary_info : list[int, float, int]
        List of the total solar panel cost, usable power generated and yearly money saved.
    Parts
    -----
    building : :class:`parapy.geom.ExtrudedSolid`
        Solid representation of the extruded floor plan geometry.
    roof : :class:`Roof`
        Composite roof (flat + any gables).
    solar_panel_arrays : list[:class:`SolarPanelArray`]
        One array per roof face that receives a non-zero budget.
    writer : :class:`parapy.exchange.STEPWriter`
        Optional STEP export (*.stp) of the three solids above.
    summary : :class:`Summary`
        Pops up the cost / energy yield / savings calculation.

    Notes
    -----
    * All geometries are modelled in a *local* Cartesian frame whose origin
      coincides with the first footprint vertex.
    * Budget is distributed *greedily* per face: when it runs out the
      remaining faces simply receive ``0 €``. This prioritises flat roofs to
      be filled with solar panels first as they are more efficient, due to their
      free choice of tilt angle.
    """

    address = Input()
    floors = Input() # nr of storeys, not including the roof
    budget = Input() # EUR, budget for solar panel installation
    electrical_efficiency = Input(0.98)
    floor_height = Input(2.0)

    @Attribute
    def base_height(self):
        return self.floors * self.floor_height


    @Attribute
    def base_pts(self):
        # list of tuples (x, y) defining the footprint of house polygon
        coords = list(self.map.footprint.exterior.coords)
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        def snap(x, res=0.05):
            return round(x / res) * res

        return [Point(snap(x - coords[0][0]), snap(y - coords[0][1]), 0) for x, y in coords]


    # Extended points are used to construct gable roofs
    # These points are teh intersections of the base polygon edges
    @Attribute
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

    @Attribute
    def combined_points(self):
        return self.base_pts[:-1] + self.extended_intersections

    # The base wire is the wire that defines the base of the house
    # It is used to extrude the base solid
    # And consists of line segments connecting the base points
    @Attribute
    def base_wire(self):
        segments = [LineSegment(start=self.base_pts[i], end=self.base_pts[i + 1])
                    for i in range(len(self.base_pts) - 1)]
        return Wire(segments)


    # The face budgets are estimations based on the roof faces
    # and the budget available for solar panel installation.
    @Attribute
    def face_budgets(self):
        budgets = []
        remaining = self.budget

        for face in self.roof.roof_faces:
            n = face.plane_normal.normalized
            if n.is_parallel(Vector(0, 0, 1), tol=1e-2):
                cost = 900 * 0.9
            else:
                cost = 0.82 * 900 * 0.9 # non-flat roofs fit less panels, manual adjustment

            face_area = face.area
            panel_count = int(face_area // (1.4 * 2.1))
            face_cost = panel_count * cost

            budget_for_face = min(remaining, face_cost)
            budgets.append(budget_for_face)
            remaining -= budget_for_face

            if remaining <= 0:
                break

            # pad with zeros if you broke early
        while len(budgets) < len(self.roof.roof_faces):
            budgets.append(0)
        return budgets

    @Attribute
    def summary_info(self):
        # Total cost of all solar panel arrays
        total_cost = 0
        total_radiation = 0
        for array in self.solar_panel_arrays:
            total_cost += array.solution.best_result[0][5]
            # Total annual solar radiation
            total_radiation += array.solution.annual_solar_radiation
        usable_energy = self.solar_panel_arrays[0].loss/100 * self.electrical_efficiency * total_radiation
        # Money saved per year from solar panels assuming cost of kwh is 0.3 EUR
        money_saved = usable_energy * 0.3

        return total_cost, usable_energy, money_saved


    @Attribute
    def solar_panel_details(self):
        details = []
        for array in self.solar_panel_arrays:
            detail = {
                'roof_area': array.solution.roof_area,
                'panel_total_area': array.solution.panel_total_area,
                'panel_counts': array.solution.panel_counts,
                'best_tilt': array.solution.best_tilt,
                'best_azimuth': array.solution.best_azimuth,
                'actual_azimuth': array.solution.actual_azimuth,
                'avg_daily_radiation': array.solution.avg_solar_radiation
            }
            details.append(detail)
        return details



    @Part
    def building(self):
        return ExtrudedSolid(island=self.base_wire, distance=self.base_height)

    @Part
    def map(self):
        return Map(address=self.address)

    # Mark the roof vertexes in the GUI, user can use these for refrence
    # When generating a gable roof
    @Part
    def roof_vertexes(self):
        return Marker(points=self.combined_points, color='red', offset=Vector(0, 0, self.base_height))

    @Part
    def roof(self):
        return Roof(footprint=self.map.footprint,
                    base_vertexes=self.combined_points,
                    base_height=self.base_height)

    @Part
    def solar_panel_arrays(self):
        return SolarPanelArray(
            quantify=len(self.roof.roof_faces),
            roof_face=self.roof.roof_faces[child.index],
            coords=self.map.coords,
            budget=self.face_budgets[child.index])

    # The STEPWriter exports to a STEP file
    @Part
    def write_step(self):
        return STEPWriter(
            trees=[self],
            filename="OUTPUT\\house_with_solar_panels.stp"
        )

    @Part
    def summary(self):
        return Summary(info=self.summary_info)

    @Part
    def write_output(self):
        return TextWriter(
            solar_panel_details=self.solar_panel_details,
            summary_info=self.summary_info
        )


if __name__ == '__main__':
    from parapy.gui import display
    obj = House(address="Slangenstraat 48", floors=2, budget=1000000)
    display(obj)
    obj.writer.write_step()


