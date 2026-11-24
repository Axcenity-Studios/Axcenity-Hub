---
description: "Inside a Spline: a road or path on the terrain (procedural worlds PW4), Width studs across along the Spline's curve."
---

# TerrainPath

```luau
Instance.new("TerrainPath")
```

Inside a Spline: a road or path on the terrain (procedural worlds PW4), Width studs across along the Spline's curve. ScatterRules keep off it (ClearScatter) wherever it goes, on every device, without changing the terrain. In the editor, Apply to Terrain flattens the ground under it to the curve, paints its Layer and its ShoulderLayer out over Falloff with an edge EdgeNoise breaks up, and takes painted foliage off it, thinning it over ClearFalloff (one undo step), and Route lays the Spline's points over the terrain from its first point to its last, no stretch climbing more than MaxGrade degrees, so a road winds round or up a hill (one undo step). Put a SplineMesh in the same Spline for the road's surface.

It also has every member of [Instance](Instance.md).

### Properties

#### Enabled

```luau
TerrainPath.Enabled: boolean
```

If false, scatter rules don't keep off it and the editor's Apply and Route do nothing. True by default.

#### Width

```luau
TerrainPath.Width: number
```

Studs across the road or path. Apply flattens and paints this strip fully. 8 by default.

#### Falloff

```luau
TerrainPath.Falloff: number
```

Studs past each edge over which Apply's flattening and paint blend into the ground around. With a ShoulderLayer, the shoulder is this wide. 4 by default.

#### Flatten

```luau
TerrainPath.Flatten: boolean
```

If true (the default), Apply levels the strip to the height of its Spline's curve.

#### Layer

```luau
TerrainPath.Layer: string
```

The name of the TerrainLayer Apply paints the strip with. Empty (the default) paints nothing.

#### ShoulderLayer

```luau
TerrainPath.ShoulderLayer: string
```

The name of the TerrainLayer Apply paints the road's shoulders with (gravel or dust, say): full at each edge and fading into the ground over Falloff, while the road's own Layer blends into it over the first quarter of that. Empty (the default) paints no shoulder, and Layer itself fades over Falloff.

#### EdgeNoise

```luau
TerrainPath.EdgeNoise: number
```

0 to 1: how much noise breaks up the outer edge of what Apply paints, so the road doesn't end in a clean line. The paint reaches Falloff times 1 - EdgeNoise to 1 + EdgeNoise studs past the road's edge, from place to place. The flattening is never ragged. 0.5 by default; 0 is an even edge.

#### NoiseScale

```luau
TerrainPath.NoiseScale: number
```

Studs across the edge noise's patches: how long each bulge and bite of the ragged edge is. 10 by default.

#### ClearScatter

```luau
TerrainPath.ClearScatter: boolean
```

If true (the default), the terrain's ScatterRules place nothing within Width / 2 + ClearMargin studs of the curve, seen from above, and fewer over ClearFalloff past that. They keep off it as soon as it's there and wherever its points move, on every device. The editor's Apply also takes the painted foliage (the Scatter pane's) off the same strip.

#### ClearMargin

```luau
TerrainPath.ClearMargin: number
```

Studs past each edge that scatter rules keep clear, so trees don't stand on the verge. 1 by default.

#### ClearFalloff

```luau
TerrainPath.ClearFalloff: number
```

Studs past the cleared strip over which scatter thins out: nearly none beside the strip, all of it this far away, so plants close in on the road gradually. 4 by default; 0 is a clean edge.

#### MaxGrade

```luau
TerrainPath.MaxGrade: number
```

The steepest the editor's Route lets the road climb, in degrees. 8 by default.

