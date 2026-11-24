---
description: "A character's look as data: its base model, body and face values, what it wears and its material values."
---

# HumanoidDescription

```luau
Instance.new("HumanoidDescription")
```

A character's look as data: its base model, body and face values, what it wears and its material values. Data is the text of a character file (`*.character.json`, as Character Studio saves it) and Base its base model's ID. Humanoid:ApplyDescription makes a character look like it. The one inside a Humanoid is what that character has applied; it's applied again when the world is loaded or replicated, so every device builds the character's meshes itself.

It also has every member of [Instance](Instance.md).

### Properties

#### Base

```luau
HumanoidDescription.Base: string
```

The ID of its base model in the project's character library, such as `axcenity/stylized`. The methods keep it the same as the `base` in Data; with Data empty, the description is this base model's default character (of `axcenity/stylized` when this is empty too).

#### Data

```luau
HumanoidDescription.Data: string
```

The description: the text of a character file (`*.character.json`), with the base model, parameter values, items worn and material values. Empty is the base model's default character. The methods read and write it, and setting it to a saved character's text loads that character. Changing the Data of the one inside a Humanoid changes that character by the next frame.

### Functions

#### GetParameter

```luau
HumanoidDescription:GetParameter(id: string): number
```

The value of the base model's parameter `id` (`height`, `build`, `nose_width`, ...): the description's, or the parameter's default when it holds none. An error for a parameter the base model hasn't.

#### SetParameter

```luau
HumanoidDescription:SetParameter(id: string, value: number): ()
```

Sets the parameter `id` to `value`, kept within the parameter's range (5 for a parameter from -1 to 1 is 1). An error for a parameter the base model hasn't, or a number that isn't finite.

#### GetItems

```luau
HumanoidDescription:GetItems(): { { Id: string, Slot: string?, Variant: string? } }
```

What it wears, in order: for each item its ID in the character library (`axcenity/tee`), the slot it's worn in (nil for an item the library hasn't) and its variant, if one was chosen.

#### SetItem

```luau
HumanoidDescription:SetItem(slot: string, id: string, variant: string?): ()
```

Puts the library's item `id` in `slot`, as its variant `variant` if given, in place of what the slot holds (a slot that holds several keeps them). An item worn already stays where it is and only its variant changes. An error if the library has no such item, it doesn't fit the base model, `slot` isn't the item's slot, or it has no such variant.

#### RemoveItem

```luau
HumanoidDescription:RemoveItem(slot: string): ()
```

Takes off every item in `slot` (`hair` for a bald head). An error for a slot the base model hasn't.

#### SetMaterialValue

```luau
HumanoidDescription:SetMaterialValue(slot: string, name: string, value: number | Color3): ()
```

Sets the value `name` of the base model's material `slot` (`Skin`, `Iris`, `Brow`, ...): a number such as the skin's `melanin`, or a Color3 such as its `tint`. Values change the material as it was made, they don't replace its maps, and the neutral value changes nothing. An error for a material the base model hasn't, a value its shading model hasn't, the wrong kind of value, or a number outside the value's range.

```lua
local humanoid = workspace.Hero.Humanoid
local description = humanoid:GetAppliedDescription() or Instance.new("HumanoidDescription")
description:SetMaterialValue("Skin", "melanin", 0.4)
description:SetMaterialValue("Iris", "iris_tint", Color3.fromRGB(90, 122, 154))
humanoid:ApplyDescription(description)
```

