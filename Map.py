from parapy.core import Input, Attribute, Part, child
from parapy.geom import GeomBase, Point, Polygon, TextLabel
import osmnx as ox
from shapely.geometry import MultiPolygon


class Map(GeomBase):
    """
    Downloads and normalises nearby building footprints from **osmnx** API.

    Inputs
    ----------
    address : str
        Search centre – any string acceptable by Nominatim.
    range : float, default 5 m
        Half-length of the square clipping window around *address*
        (metric because we use the projected CRS returned by osmnx).
    selected_building_index : int, default 0
        Index in :pyattr:`nearby_buildings` that will be exposed as the
        *primary* footprint (:pyattr:`footprint`).

    Important attributes
    -------------
    coords : list[float]
        ``[lat, lon]`` pair of the centroid of the primary building
        footprint (used for the PVGIS calls).
    nearby_buildings : list[shapely.Polygon|shapely.MultiPolygon]
        Raw footprints around the address.
    building_outline_points : list[list[parapy.geom.Point]]
        Same geometry, but projected to a *local* XY frame whose origin
        equals the first point of the primary footprint.  Ready to be
        rendered by :class:`parapy.geom.Polygon`.
    footprint : shapely.Polygon
        The *projected* footprint that downstream logic (Roof etc.)
        operates on.

    Parts
    -----
    building_outlines : parapy.geom.Polygon
        Light-grey context blocks.
    building_labels : parapy.geom.TextLabel
        Numeric index labels that help choosing *selected_building_index*.
    """
    address = Input()
    range = Input(5)
    selected_building_index = Input(0)

    @Attribute
    def house(self):
        tags = {"building": True}
        gdf = ox.features_from_address(self.address, tags=tags, dist=self.range)
        return gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]

    @Attribute
    def coords(self):
        center = self.house.geometry.iloc[0].centroid
        return [center.y, center.x]

    @Attribute
    def nearby_buildings(self):
        shapes = self.house.geometry
        return list(shapes)

    @Attribute
    def building_outline_points(self):
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
    def footprint(self):
        geom = self.nearby_buildings[self.selected_building_index]
        if isinstance(geom, MultiPolygon):
            geom = list(geom.geoms)[0]
        projected_geom, _ = ox.projection.project_geometry(geom)
        return projected_geom

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
            position=self.building_outline_centroids[child.index],
            size=1.0,
            color='black'
        )

if __name__ == '__main__':
    from parapy.gui import display
    obj = Map(selected_building_index=1)
    display(obj)