---
description: "Inside Lighting: rain or snow falling around the camera, and how wet and snow-covered surfaces are (parts, models and terrain)."
---

# Weather

```luau
Instance.new("Weather")
```

Inside Lighting: rain or snow falling around the camera, and how wet and snow-covered surfaces are (parts, models and terrain). Wet surfaces are darker and glossier; snow covers the tops of things but not walls. workspace.GlobalWind blows the rain and snow. Every change eases in over TransitionTime. With Precipitation None and no Wetness or SnowCover it costs nothing.

It also has every member of [Instance](Instance.md).

### Properties

#### Enabled

```luau
Weather.Enabled: boolean
```

Turns the weather system on or off (true by default). When false, precipitation stops and surfaces dry and clear over TransitionTime.

#### Precipitation

```luau
Weather.Precipitation: EnumPrecipitation | "None" | "Rain" | "Snow"
```

What falls around the camera (`Enum.Precipitation`): None, Rain (the default) or Snow. Rain wets surfaces as it falls, up to its Intensity; snow covers the ones facing up.

#### Intensity

```luau
Weather.Intensity: number
```

How hard the rain or snow falls, from 0 to 1 (0.5 by default): more drops, and wetter or deeper on the ground.

#### Wetness

```luau
Weather.Wetness: number
```

How wet surfaces are whatever is falling, from 0 (dry, the default) to 1 (soaked): darker and glossier, with puddles on level ground from 0.35. Rain wets them at least as much as its Intensity, and while it falls its drops ring the puddles and splash on solid surfaces.

#### SnowCover

```luau
Weather.SnowCover: number
```

How much snow lies on surfaces facing up whatever is falling, from 0 (none, the default) to 1: light cover lies in patches, more whitens flat tops fully and reaches further down slopes. Walls stay bare; plants are capped with it. Falling snow covers them at least as much as its Intensity.

#### SnowThickness

```luau
Weather.SnowThickness: number
```

How deep the snow lies, in studs, from 0 to 2 (0.35 by default): snow on terrain rises that far (in drifts a little deeper and shallower), burying the foot of whatever stands on the ground, and footprints press that deep into it.

#### Lightning

```luau
Weather.Lightning: number
```

How often lightning flashes, from 0 (never, the default) to 1: the chance of a flash every 2.6 seconds. A flash is two or three strokes within half a second from somewhere in the clouds; it lights what's open to the sky (a tenth as much under a roof or in an interior) and glows inside the cloud round it. It needs no rain, but only shows in the sky where there are Clouds.

#### TransitionTime

```luau
Weather.TransitionTime: number
```

Seconds a change takes to ease in (10 by default): rain starting and stopping, surfaces wetting and drying, snow settling and melting. 0 changes at once.

#### OcclusionEnabled

```luau
Weather.OcclusionEnabled: boolean
```

When true (the default), rain and snow are occluded by solid roofs and geometry, and sheltered interior surfaces stay dry and bare.

#### FootprintsEnabled

```luau
Weather.FootprintsEnabled: boolean
```

When true (the default), moving characters and objects press dynamic footprints and trails into snow-covered ground.

#### FootprintFadeTime

```luau
Weather.FootprintFadeTime: number
```

Seconds a snow footprint or trail takes to fill back in (30 by default).

#### SurfaceMask

```luau
Weather.SurfaceMask: string
```

Manual interior/exterior surface mask cells painted in the editor (format: "x,z:I;x,z:E"). Overrides automatic sky-visibility detection.

