---
description: "The parts a MeshPart made by Group as Mesh (Model ▸ Solid Modeling) was made of, kept inside it for Ungroup Mesh."
---

# GroupedParts

```luau
Instance.new("GroupedParts")
```

The parts a MeshPart made by Group as Mesh (Model ▸ Solid Modeling) was made of, kept inside it for Ungroup Mesh. Like a UnionOperation's parts, everything inside it is out of the world: not drawn, colliding or hit by raycasts. The Explorer lists them, dimmed, so they can be looked at.

It also has every member of [Instance](Instance.md).

### Properties

#### Origin

```luau
GroupedParts.Origin: CFrame
```

Where the grouped MeshPart it's in was when Group as Mesh made it. Ungroup Mesh moves and turns the parts by how the MeshPart has moved and turned since.

#### OriginSize

```luau
GroupedParts.OriginSize: Vector3
```

The grouped MeshPart's Size when Group as Mesh made it. Ungroup Mesh stretches the parts by how the MeshPart has been resized since.

