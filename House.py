from parapy.core import Base, Input, Attribute, Part, child
from parapy.geom import Wire, LineSegment, Point, ExtrudedSolid, Vector, Position
from Map import Map
from Marker import Marker
from Roof import Roof
from SolarPanelArray import SolarPanelArray




class House(Base):
    address = Input()
    floors = Input()
    budget = Input(1700)

    @Attribute
    def base_height(self):
        return self.floors * 2.0

    @Attribute
    def base_pts(self):
        coords = list(self.map.footprint.exterior.coords)
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        def snap(x, res=0.05):
            return round(x / res) * res

        return [Point(snap(x - coords[0][0]), snap(y - coords[0][1]), 0) for x, y in coords]

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

    @Attribute
    def base_wire(self):
        segments = [LineSegment(start=self.base_pts[i], end=self.base_pts[i + 1])
                    for i in range(len(self.base_pts) - 1)]
        return Wire(segments)

    @Attribute
    def face_budgets(self):
        budgets = [0] * len(self.roof.roof_faces)
        remaining = self.budget
        i = 0

        for face in self.roof.roof_faces:
            face_area = face.area
            panel_count = int(face_area // (1.35*2.1))
            face_cost = panel_count * 95

            budget_for_face = min(remaining, face_cost)
            budgets[i] = budget_for_face
            remaining -= budget_for_face
            i =+ 1

            if remaining <= 0:
                break

        return budgets

    @Part
    def building(self):
        return ExtrudedSolid(island=self.base_wire, distance=self.base_height)

    @Part
    def map(self):
        return Map(address=self.address)

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


if __name__ == '__main__':
    from parapy.gui import display
    obj = House(address="Slangenstraat 48", floors=2) # roof_vertexes=[[4, 3, 7, 5], [1, 6, 8, 2]] #Bredabaan 614, Brasschaat
    display(obj)