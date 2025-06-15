# Solar Panel Installation KBE Application

This application generates a parametric 3D building with solar panel layouts based on user-defined inputs such as address, floors, and budget. Built with ParaPy, it visualizes results and exports data for further use.

## Prerequisites

Make sure the following Python libraries are installed: Parapy, Requests, Shapely, NumPy, OSMnx, math, tkinter

```
pip install parapy requests shapely numpy osmnx math tkinter
```

## How to Use (with PyCharm)

1. Open the provided files in PyCharm.

2. Locate `House.py` and open it.

3. At the bottom of the file, modify the following line according to your preferences:

```
if __name__ == '__main__':
    from parapy.gui import display
    obj = House(address="Slangenstraat 48", floors=2, budget=1000000)
    display(obj)
```

* `address`: Enter your desired address (street name and number) is normally sufficient. If undesired results, please add place name too.
* `floors`: Set the number of floors for your building.
* `budget`: Define your budget limit for solar panel installations (in Euros).

4. Run the script `House.py`.

5. The ParaPy GUI will launch, displaying your building.

6. If the building is INCORRECT. In the ParaPy GUI, click on the `map` part and increase the range to 50. Then double-click on the `map` part to visualize all nearby building footprints. If the displayed building is incorrect, increase the `range` input to view nearby buildings. Look for the correct building. Increase the range even further if necessary.

7. Once the correct building is visible, adjust the `selected_index` to select the correct footprint and generate the correct building in 3D. (you can now hide the map again)

8. (Optional) To set up a gable roof. Visualize roof vertices by double-clicking `markers`.

9. Click on the `roof` part and adjust the `gable_roof_indices` input to select the four vertices of your gable roof. Select them in clockwise order. Ensure it is a list of lists with exactly four integer indices each, representing the corners of the gable roof(s) (e.g., `[[0,1,7,6], [3, 5, 9, 2]]`).

10. Double-click on the `solar_panel_arrays` part to generate the solar panel layouts. Note that this step may take some time due to requests made to PVGIS.

## Output

* **3D STEP file** (`house_with_solar_panels.stp`) stored in the `OUTPUT` folder. You can open this file in CAD software.
* **Results summary** (`Results.txt`) located in the `OUTPUT` folder, providing details on solar panel placements, cost, annual energy production, and potential savings.

## Adjusting Advanced Inputs

Additional inputs available:

* `slope_height`: Adjust the height of gable roofs (default is 2 meters).
* `floor_height`: Adjust the height per floor (default is 2 meters).
* `electrical_efficiency`: Modify the assumed electrical efficiency of your DC/AC converter installation (default is 0.98).
* `loss`: Modify the efficiency of the solar panel array (default is 18% efficient).


## Troubleshooting

* **"No hourly data" error**: PVGIS server may rate-limit your requests. Wait briefly or try again later.
* **Empty roof visualization**: Ensure `gable_roof_indices` is formatted correctly (a list of lists, each containing four integer indices).
* **STEP file not generated**: Check if you have write permissions for the `OUTPUT` folder.


Happy modeling and solar optimizing!
