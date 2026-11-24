---
description: Animators, clips and state machines, the Animation tab, keying parts and UI, posing rigs, importing animated models and cutscenes.
icon: person
samples: [animation, character, cutscene]
---

# Animation

Axcenity animates two kinds of things with the same tools: **skinned models** (characters with a skeleton, imported from FBX) and **any object's properties** (a door's Position, a light's Brightness, a button's colour). Both play from **clips**, which are `.anim.json` files under `assets/animations/`.

## The pieces

| Piece | What it is |
|---|---|
| Clip | A file of keyframes over time. A **linked** clip plays a take from an imported model; a **keyed** clip holds keys you set yourself. |
| Animation | An Instance that plays one clip on its parent. Properties: **Clip**, **AutoPlay**, **Enabled**, **Speed**, **Looped**. |
| Animator | An Instance that runs a **state machine** on its parent: which clip plays when, and how they blend. |
| State machine | A `.statemachine.json` file of states (each plays a clip or a blend tree) joined by transitions with conditions. |

## Animate anything in one click

Select a part, model or UI element and press **Animate** (in the Explorer's right-click menu, at the top of Properties, or on the empty Animation tab). In one undo step it adds an Animator, makes a keyed clip named after the object and puts an Animation in it that plays the clip. The **Animation** tab opens on the new clip.

## The Animation tab

The Animation tab (beside the Scene) follows the selection: select something that animates and it shows that object's state machine or clips.

- The **outline** on the left lists the object's Animator, its state machine's states and its Animations. The **breadcrumb** on top says where you are, such as **Hero ▸ State Machine ▸ Walk**.
- The **preview** shows a copy of the object, so changes here don't move the real one until you save. Drag to turn the view and scroll to zoom.
- Above the timeline, the **transport** plays the clip like a media player: go to the start, back a frame, play (pause, then resume), on a frame, go to the end and stop; then where the playhead is, a seek bar to click or drag, the clip's length and the frame number. The rate box (0.25× to 4×) changes only how fast the preview plays, not the clip's own Speed.
- With the mouse over the clip and nothing being typed, **Space** plays or pauses, **Left** and **Right** step a frame (**Shift** for ten), and **Home** and **End** go to the start and end. They're listed in **Settings > Shortcuts** under Animation and Sequencer. The Sequencer tab has the same bar and keys.
- The **timeline** shows the playhead and the clip's length. Under it, the **dope sheet** shows a row per animated property or bone, with a diamond for each key.
- Move, rotate or resize the copy in the preview with the buttons above it. With **Record** on, each change sets keys at the playhead. With Record off, **Key selected** (**K**) keys the object where it is, and **Add track** keys any other property.
- **Dope sheet · Curves** switches to curves: the values over time, X red, Y green and Z blue. Drag points and handles to shape the motion.
- In the dope sheet, drag a box to select keys, drag them to move them, and copy (**Ctrl+C**), cut (**Ctrl+X**) and paste at the playhead (**Ctrl+V**). **Snap** keeps keys on whole frames.

## Posing characters

On a skinned model the preview shows the skeleton's joints. Click a joint (or a bone in the list) and turn it with the gizmo. **Move** drags a joint; for a joint that isn't the root, the bones above it turn so it gets there (inverse kinematics), and **Chain** sets how many bones may bend. Key the pose with Record on.

## State machines

Open the Animator's **State Machine** in the outline to see its graph. Each state plays a clip or a **blend tree** that mixes clips by a number (walk to run by speed, for example). Transitions move between states when their conditions hold. Scripts drive the conditions:

```lua
local animator = workspace.Hero.Animator
animator:SetNumber("Speed", 12)
animator:SetBool("Grounded", true)
animator:SetTrigger("Jump")
```

`Animator.StateChanged` fires when the state changes, and `Animator.AnimationEvent` fires for events placed on a clip's timeline. Layers with weights (`Animator:SetLayerWeight()`) play upper-body clips over the legs.

## Playing clips from scripts

An Animation with **AutoPlay** starts when the game starts. `Animation.Completed` fires when a clip that doesn't loop ends. Scripts play an Animation through its Animator: `Animator:LoadAnimation(animation)` returns an **AnimationTrack** to play, stop, fade and pause (`track:AdjustSpeed(0)`).

## Importing animated models

Import an `.fbx` with a skeleton or takes (**File > Import…**) and the Import dialog shows an **Animation** tab: the bones, each take, and a table of clips to make, with start and end frames and looping. Import writes the clips, a state machine and an Animator in one step. See [Assets: import and manage](assets.md).

## Cutscenes

A **Sequence** Instance plays a cutscene: camera cuts, clips, property tracks and sounds on one timeline, saved as `assets/sequences/<name>.sequence.json`. Edit it in the **Sequencer** tab, which shares the Animation tab's dope sheet and curves. Tick **AutoPlay**, or call `Sequence:Play()` from a script; **Skippable** lets the player skip it and `Sequence.Completed` fires at the end. The **cutscene** sample has one.

### Transitions between shots

Pick a camera cut in the Sequencer and set its **Transition**:

| Transition | What you see |
|---|---|
| **Cut** | The view changes from one frame to the next. |
| **Fade through color** | The screen fades to a color (black, white, any), the view changes behind it, and it clears again. |
| **Dissolve** | The shot before fades into the new one. |

**Lasts** is how long the transition takes. Half of it is before the cut and half after. A fade through a color looks the same in the game, the preview and a movie. A dissolve is drawn in rendered movies; in the game and the preview it plays as a cut.

### Keying the sky, the weather and the lens

A sequence can key more than parts and cameras. Select **Lighting**, something inside it (Clouds, an Atmosphere, a Weather, a DepthOfFieldEffect), a light or the **Workspace** in the Explorer, then press **Add track** and pick a property:

- Lighting's **ClockTime** for a time-lapse from dawn to dusk, and **Exposure**.
- A Weather's **Intensity**, **Wetness** and **SnowCover** for a storm coming in. Set its **TransitionTime** to 0 so the weather follows the keys exactly.
- A DepthOfFieldEffect's **FocusDistance** to pull focus from one thing to another.
- A light's **Brightness** and **Color**, and the Workspace's **GlobalWind**.

Move the playhead, change the property, and press **Key selected** (K) for the next key.

### The Environment track: the weather and the time of day in one key

For a storm rolling in or a day turning to night you don't need a track for each property. An **environment preset** holds the whole look at once (the time of day and exposure, the air's haze, the clouds, what falls and how hard, how wet or snowy the ground is, the wind and the color's saturation), and the **Environment** track blends from one preset to the next.

1. In the Sequencer, move the playhead to where the look should be reached.
2. Press **Add section**, then **Environment key**, and pick a preset: **Clear**, **Evening**, **Overcast**, **Storm**, **SnowDay**, **SnowNight** or one of your own.
3. Move the playhead and add the next key. Between two keys the sky and the weather blend, and scrubbing shows it in the Scene view.
4. Pick a key to set it below the rows: its **Preset**, its **Blend** to the next key (Linear, an Ease, or Hold, then switch) and which way the **Clock** turns.

- **The clock turns the short way.** From 22 to 2 it goes through midnight. From morning (6) to evening (20) the short way is back through midnight too, so pick **Forward (time passes)** on the morning key for a day to pass.
- **Rain never turns straight into snow.** From Storm to SnowDay the rain eases off, stops half way, and the snow eases in.
- **Property tracks win.** If a track keys a property the presets set (Clouds' Cover, say), that property follows its own track and the Environment track sets the rest.
- **Lighting needs the pieces.** A preset's clouds need **Clouds** in Lighting, its rain and snow a **Weather**, and its haze an **Atmosphere** (World tab, Lights & Sky, Sky). Applying a preset from Properties (below) adds Clouds and a Weather for you.
- Set the Weather's **TransitionTime** to 0 for rain and snow to follow the keys exactly, as with property keys.

To make a preset of your own, set the world up the way you want it, select **Lighting** (or nothing), and in the Properties panel's **Environment presets** section type a name and press **Save current as**. It's saved in the project as `assets/environments/<name>.environment.json` and is listed with the built-in ones. The buttons in the same section put the world at a preset straight away, as one undo step. See [Lighting and rendering](lighting-and-rendering.md#environment-presets).

### Rendering a movie

**Render Movie** turns the open sequence into a video file, at any size and at the best graphics your computer can draw. It isn't a screen recording: the editor draws every frame in turn, however long each takes, so the movie plays smoothly even where the game wouldn't.

1. Open the sequence in the **Sequencer** tab. To render only part of it, mark the part with **In** and **Out**.
2. Press **Render Movie** on the row under the play buttons.
3. Choose the **Resolution** (up to 3840 × 2160), the **Shape** (16:9, the cinema's 2.39:1 and others) and the **Frame rate**.
4. Choose the **Format**. **H.264 video (.mp4)** plays everywhere. **PNG image sequence** writes one picture a frame, for a video editor.
5. Press **Render**. A bar shows the frame being drawn, the time left and the last frame. You can keep working meanwhile, or press **Cancel**.

The movie goes in the project's `movies` folder unless you pick another place. **Open folder** shows it when it's done.

> **Videos need ffmpeg.** The editor makes video files with the free program [ffmpeg](https://ffmpeg.org). If it isn't installed, the window says so and only the PNG sequence can be chosen. Install it (`winget install ffmpeg` on Windows, your package manager on Linux), then press **Check again**.

- **Graphics** is the quality the movie is drawn with, whatever the editor's own setting. With **Ray tracing** ticked, shadows, bounced light and reflections are ray traced (your graphics card must support it, and **Settings > Graphics > Hardware ray tracing** must be on).
- **Motion blur** streaks what moves, like a film camera. Leave **Set here** off to use the world's MotionBlurEffect.
- **Warm-up** frames are drawn and thrown away before the first one is kept, so light and textures have settled. Raise it if the first frames flicker.
- The **2.39:1** shape is the letterboxed look as the whole picture. Choosing it turns **Letterbox bars** off, so the picture isn't cut twice.
- Movies have no sound yet: add it in a video editor.

Build scripts can render without the window:

```text
axcenity-editor --render-movie MyGame --sequence Intro --out Intro.mp4 --size 3840x1608 --fps 24
```

> **Known limits.** Animation in glTF files isn't imported yet: use FBX for animated models.
