---
description: Sculpt, paint, generate and erode landscapes with the Terrain Studio, and paint grass, plants and trees.
icon: mountains
samples: [part, caves]
---

# Terrain tools

A **Terrain** object is a heightmap landscape: smooth hills and valleys, painted with layers of material and covered with painted foliage. You shape it with brushes in the **Terrain Studio**, and parts and characters walk and roll on it like any other ground.

## Open the Terrain Studio

On the **World** tab, the **Terrain** group opens the Terrain Studio panel; **Brush ▾** picks a tool directly. With a brush up, the left mouse button paints in the Scene, **[** and **]** make the brush smaller and bigger, and **Escape** puts it down. Hover a tool for its name, key and what it does.

The panel has three tabs: **Sculpt** for the brushes that shape the ground, **Materials** for painting, layers, biomes and scatter rules, and **Terrain** for generating and eroding the whole landscape, masks, water, and the terrain's resolution and heightmaps. Picking a tool any way (its key, **Brush ▾** or search) shows its tab, and going back to a tab picks the tool you last used there.

## Tools

| Key | Tool | Does |
|---|---|---|
| **1** | Raise / Lower | Raise ground; hold **Shift** to lower |
| **2** | Smooth | Even out bumps |
| **3** | Flatten | Level to a height |
| **4** | Sculpt | Push and pull freely |
| **5** | Stamp | Press a shape into the ground |
| **6** | Noise | Add natural roughness |
| | Holes | Cut holes for cave mouths and tunnels; hold **Shift** to fill them |
| **7** | Paint | Paint a material layer |
| **8** | Auto Materials | Paint by height and slope rules: grass on flat ground, rock on cliffs |
| **9** | Generate | Make a whole landscape from settings and a seed, or a preset |
| **0** | Erosion | Weather the landscape with water and gravity |
| | Masks | Limit tools by height or slope |

Generate and Erosion run in the background with a progress bar and Cancel. A seed always gives the same landscape.

## Materials

A terrain is painted with **layers** (TerrainLayer objects inside it), each with its own textures and a rule for where it shows. Open a layer in the Terrain Studio and pick **Use texture set** to fill all its maps from a texture in your project, or **From Toolbox…** to download one.

## Foliage

Plants, props and models are painted onto the terrain with the **Scatter** pane: on the ribbon's **Models** group, pick **Scatter**. Turn on **Add from Assets** and click the props or models you want in the Assets panel; each becomes an item in the pane's palette, with its **Weight** (its share of the mix, shown as a percentage), **Size** (smallest and largest scale), **Collide** (solid, so parts rest on it, or only visual), **Rotation** (how far each copy is turned at random), **Align to slope** and **Sink**. Set the brush's **Size**, **Density** (items per 100 square studs) and **Spacing** (the least distance between items, so painting over the same ground fills gaps instead of piling up), press **Paint** and drag on the terrain. Hold **Shift** to erase the palette's items, or tick **Erase everything** to erase any painted foliage. Each stroke is one undo step. Palettes are saved in your project's `presets` folder as `.axscatter` files: make more with **New**, and switch between them with the dropdown. Painted plants sway in the Workspace's **GlobalWind** and are drawn only near the camera (grass to about 120 studs, trees to 800), so a large painted forest stays fast.

### Breaking up an even spread

Painting one mix everywhere looks like wallpaper. Open **Masks** under an item to say where the brush places more or less of it, then sweep a large brush over the whole area and let the masks do the sorting:

- **Noise** gathers the item into patches. Raise it toward 1 to empty the ground between them, set **Scale** to how wide a patch is, **Threshold** to how much ground stays bare, and **Contrast** to how sharp the patches' edges are. **Seed** moves the patches.
- **Slope** keeps it between two steepnesses, such as 0° to 15° for grass and 20° to 90° for rocks.
- **Height** keeps it between two heights. Tick it, then set the lowest and highest ground.
- **Moisture** looks at the shape of the ground: hollows (washes, ditches, the foot of a slope) count as wet, rises (ridges and knolls) as dry. Above 0 the item gathers in the wet, below 0 on the dry. **Reach** is how far round each spot it looks: set it to about half the width of your washes.

For a dry basin, give grass and bushes Moisture 1, so they crowd into the washes, and give dry scrub or rocks Moisture -1 with a little Noise, so they thin out onto the rises. Masks multiply, and an item with none is placed everywhere, as before.

### Ground clutter and stains

Props look pasted on when the ground round them is clean. Two things in the Scatter pane fix that:

- The polygon button beside **New** makes a **Ground Clutter** palette: gravel, pebbles and a few stones that lie to the slope and sink in a little. Paint it round a building's foot, under a vehicle and along a road's edge. For twigs or leaves, add your own models and give them **Align to slope** 1 and a little **Sink**.
- Under **Decals**, turn on **Add pictures from Assets** and click the stain, track or dirt pictures you want (images with a see-through background work best). Set each one's **Size**, **Opacity** and **Rotation** (0 keeps tracks running one way), press **Paint decals** and drag. Each stroke lays projected decals on the ground, in a "Scattered Decals" folder in the Workspace, and is one undo step. **Shift**+drag takes them away. The brush follows the terrain even under a vehicle or a porch; tick **Land on parts** to lay them on top of parts instead.

Projected decals are for dressing a place, not for covering a map: the game draws only the nearest ones (none at Low quality, 128 within 150 studs at Medium), so the brush stops when a place has as many as Medium draws, and says so in Output. For dirt that must show everywhere, paint a terrain layer.

## Scatter rules

Instead of painting by hand, a **scatter rule** (a ScatterRule object inside the terrain) covers the whole terrain for you. On the Terrain Studio's **Materials** tab, open **Scatter Rules** and pick **Add rule**: the **Forest set** adds trees, undergrowth and grass tufts at once, or add one preset. Select a rule to set how far apart things stand, how many, the heights and slopes they grow on, the material layer they need, how much they gather into patches, and how far they keep from what rules above them placed. With a rule selected, click plants, props or models in the Assets panel to add or remove them. The layout follows the ground as you sculpt and paint, and the same seed gives the same layout every time. Rules keep off anchored parts standing on the ground (a house, a fence, a rock you placed) unless you turn **Avoid Parts** off, and **Align To Slope** and **Sink Depth** lean what they place with the hillside and sink it into the ground. It isn't saved: it's made again when the world opens. **Bake** turns what the rules placed into painted foliage, so you can brush and erase it by hand.

## Biomes

A **biome** (a Biome object inside the terrain) is an area such as a forest, a meadow or alpine turf, with its own ground material and its own scatter rules. On the Terrain Studio's **Materials** tab, open **Biomes** and pick **Add biome**: each preset brings its ground layer and its rules. A biome covers ground by itself between its heights, below its steepest slope and between its driest and wettest ground, with soft, ragged edges; where biomes overlap, the lower one in the list wins. Select a biome and click **Paint this biome** to spread it by hand (Shift erases back to the automatic biomes). With a biome selected, **Add rule** adds the rule inside it, so it only places there.

## World presets

A **world preset** sets up a whole landscape at once: its shape, materials, biomes, scatter rules and water. On the **Terrain** tab, pick the **Generate** tool, choose one under **World Presets** (Temperate Forest, Alpine, Desert, Tropical Island, Tundra or Meadow) and click **Generate with it**; **Apply** keeps the result, all as one undo step. **Only its materials and rules** keeps your terrain's shape. To reuse your own setup, type a name and click **Save as preset**: it's saved in the project's `presets` folder and listed with the others.

## Roads and parts into terrain

- A **SplineMesh** lays a road or fence along a spline, and **Flatten Terrain Along** levels the ground under it. See the **roads** sample.
- A **Terrain Path** (Insert ▸ Terrain Path, into the selected spline) makes the spline a road on the terrain. Scatter rules keep off it straight away, wherever you drag its points. In its Properties, set its **Width**, the **Layer** to paint it with and how far it blends in (**Falloff**), then click **Apply to Terrain** to flatten and paint the ground under it. To keep the road from ending in a clean line, type a second layer's name (gravel or dust) into **Shoulder Layer**: Apply paints it from the road's edge out over the Falloff, so make the Falloff 8 studs or more. **Edge Noise** makes that outer edge ragged (0 is even, 1 very ragged) and **Noise Scale** sets how long its bulges are. Apply also takes painted foliage off the road and thins it over **Clear Falloff** beside it, and scatter rules thin out over the same distance. **Route** lays the spline's points over the terrain from its first point to its last without climbing steeper than **Max Grade**, so the road winds round or up a hill. Both are one undo step each.
- **Solid Modeling ▸ To Terrain** turns a selected part into ground: the terrain under it is raised to its top and painted.
- **Solid Modeling ▸ Conform to Terrain** sets the selected parts or models down on the ground (or up out of it), and **Blend into Terrain** levels the ground under them to their bottom and paints it with the Terrain Studio's Paint layer, fading into the slope around. Each is one undo step.

## Caves and cliffs

A terrain is one surface, so it can't bend back over itself. To make a cave, cut a hole in it and build the cave from parts:

- Pick the **Holes** tool and paint over the spot: the ground there disappears, so you see, walk and fall through it. Hold **Shift** to fill it back in.
- Build the cave under the hole from parts: a floor, walls and a ceiling. Rock parts round the opening hide its edges, and scatter rules keep clear of them.
- Under **Scatter Rules**, **Add rule ▸ Cliff Rocks** stands rock faces on every slope steeper than 38 degrees, and **Boulders** scatters rocks over gentler slopes. The **Alpine** world preset includes cliff rocks.

See the **caves** sample: walk into the hill.

## Buildings

- **Insert ▸ Building** puts a building in front of the camera. Its box is its footprint: drag, turn and stretch it with the Move, Rotate and Scale handles, and it's built again as you go. Inserted into a selected spline, the spline's points are its corners instead, for L-shaped or angled buildings.
- In its Properties, set **Floors**, **Floor Height**, the **Roof Style** (Flat or Gable), **Window Chance** and the colors. Change the **Seed** for another arrangement of windows; the same seed always gives the same building. Name your own models in **Wall Model**, **Window Model**, **Door Model** and **Corner Model** to build with them instead of plain parts.
- Its parts aren't saved: they're made again from its settings. Click **Bake** to keep them as an ordinary Model you can edit by hand. Scatter rules keep trees out of it, and **Blend into Terrain** levels the ground under it. See the **buildings** sample.

## How it's saved

A terrain's data is a folder of images and JSON (`heights.png`, paint maps, `foliage.json` and `holes.png`) under `assets/terrain`, named by the Terrain's **DataFolder** property.
