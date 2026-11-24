# The Toolbox page (`/toolbox/`)

`marketing:toolbox` (`ToolboxView`) is the overview of the Axcenity
Toolbox, the companion asset tool. The Toolbox itself still lives in
its own repository (`content.TOOLBOX_REPO_URL`) and runs on the
visitor's machine; Phase 17 brings it into the Hub. `tests/test_toolbox.py`
enforces everything here.

## Files

| Path | Holds |
|---|---|
| `marketing/content.py` | `TOOLBOX_PAGE` (all copy, the features, providers and commands), `TOOLBOX_REPO_URL`, `TOOLBOX_COMMIT`, `TOOLBOX_CAPTURE_RECORD`, and the three screenshots in `MEDIA` |
| `templates/marketing/toolbox.html` | The page, in the marketing shell |
| `styles/source.css` | The `.tb-*` classes (below) |
| `marketing/media_sources/toolbox-*-2560x1600.png` | The screenshots as captured, dark and `-light` |
| `marketing/media_sources/toolbox-capture.json` | How they were captured and what each showed |

## Sections, in order

`#overview`, `#discover`, `#library`, `#packs`, `#run`.

- **Overview:** the eyebrow, "Axcenity Toolbox" (the page's only `<h1>`),
  the lede, a note that it runs on your own machine with no API keys,
  then View on GitHub (the page's one primary button) and Run it locally
  (`#run`).
- **Discover, Library, Packs** (`ToolboxFeature`): each is a split panel
  (Home's `.panel.split`): a shelf head (number, label, a rule), the
  title, the body and three points, beside its screenshot. The
  screenshot alternates sides: right, left, right. Under Discover,
  `providers` lists ambientCG, Poly Haven and Openverse Audio with
  what they offer and their licence.
- **Run:** a terminal panel with the README's commands (`Command`: the
  line and an optional `# note`), then where to open it, what works
  offline, the demo credentials and Read the README.

Copy is data, as on Home: the visible text in `<main>` must all come from
`TOOLBOX_PAGE`, and the `<pre>` must render the commands exactly.

## The Toolbox's look, inside the shell

The `.tb-*` classes port a few of the Toolbox's own pieces, in the
monochrome tokens only:

- `.tb-shelf-head` / `.tb-shelf-rule`: its Discover shelf heads (`01
  AMBIENTCG ───`).
- `.tb-bar` / `.tb-chip` / `.tb-chip-current`: its title-bar crumbs; the
  `/` between chips is drawn by CSS, so it's never copy or read out.
- `.tb-terminal`: the commands, scrolling sideways inside their own box
  (`tabindex="0"`, so the keyboard can scroll it), never the page.
- `.tb-code` for inline code, `.tb-demo` for the credentials box,
  `.tb-points` for the feature points.

## Commands and demo credentials

`TOOLBOX_PAGE["run"]["commands"]` are the README's Setup and Running
blocks at `TOOLBOX_COMMIT`, with the clone placeholder replaced by the
real URL. `test_the_commands_match_the_toolbox_readme` compares them with
the README of the Toolbox's checkout when it exists on this machine
(`~/Documents/VSCode Projects/project-two-building-with-apis`, read only),
and skips elsewhere. Update both together if the README changes.

The page shows only the README's published demo password
(`toolbox-demo`) for `seed_demo`'s three demo members, and labels it:

- **demo credentials, for your local copy only**;
- the accounts are regular members with **no staff or admin rights**;
- **never run `seed_demo` on a server other people can reach**, and
  never give a demo account more.

The capture record confirms the demo members had no staff, superuser,
group or permission when the screenshots were taken (tested). The
README's personal test account never appears.

## The screenshots

Three `Media` captures with `subject="toolbox"`, so their captions start
"Toolbox screenshot" (never "Engine capture"): `toolbox-discover`,
`toolbox-library`, `toolbox-packs`, built by `_toolbox_screenshot()`
into `TOOLBOX_SCREENS`. Each is the Toolbox's dark theme with a `light`
twin (`toolbox-*-light`): the same screen and content in its light
theme, so the page stays cohesive in either scheme.

- **Twins:** `Media.light` must be a capture of the same subject, size,
  caption and display (`is_light_twin_of`), with no twin of its own.
  Both are in `MEDIA`, so `make_media` and the manifest tests treat them
  like any capture.
- **Switching:** `frame.html` renders one `<picture>` per scheme
  (`class="when-dark"`, `"when-light"`) under one caption; the stylesheet
  shows the one matching `html[data-scheme]`, so it follows the theme
  switch live and, without JavaScript, the server-rendered choice. The
  hidden picture is `display: none` and lazy, so it's never fetched until
  the scheme switches (tested). Each is 2560×1600 (1280×800 at 2×),
the frames' own 16:10, so it's drawn whole, never cropped, and with
`SECTION_DISPLAY` it's never upscaled. They go through the media
pipeline like any capture ([media.md](media.md)).

**They're committed static sources.** Nothing in the test suite or the
build regenerates them; the tests only read them, and each file's
SHA-256 must match `toolbox-capture.json`. Provider results and
thumbnails were live at capture time, so they'll drift at the providers,
but the committed PNGs and their derivatives never change with them. The
record keeps what each one showed.

### `toolbox-capture.json`

- `source`: the repository, commit and commit date; how it was copied
  (`git archive HEAD` into a throwaway directory, so the Toolbox repo was
  never touched); the commands run; what `seed_demo` created; the demo
  accounts' privileges; a note on the live content.
- `capture`: the browser, viewport, pixel ratio, reduced motion and the
  demo member signed in.
- `screens`: per screen (`discover`, …, `discover-light`, …), its
  scheme, file and SHA-256, URL, how far the Toolbox's
  work area (`main#content`) was scrolled, when it was captured, the
  provider shelves showing, and every image on screen with its card's
  title and its live thumbnail URL.

### Capturing them again

Only when the Toolbox changes enough to need it, by hand:

1. `git archive <commit> | tar -x -C <empty dir>` from the Toolbox repo,
   then in that copy `uv sync`, `migrate`, `seed_demo`, `tailwind build`
   and `runserver 127.0.0.1:8765`.
2. In headless Chromium (Playwright from this project's environment),
   once per scheme: cookie `ax-theme=<scheme>`, `color_scheme=<scheme>`,
   `reduced_motion="reduce"`, 1280×800 at `device_scale_factor=2`. Sign
   in as `demo_mira` through `.auth-form` (the title bar's theme switch
   is a form too).
3. Open each screen's URL, scroll `main#content` by its recorded offset,
   wait for every visible thumbnail to decode, move the pointer off the
   content and take a viewport screenshot.
4. Check both runs showed the same results and thumbnails (the record's
   `shown` lists must match; the tests check it), or capture both again.
   Copy the PNGs into `marketing/media_sources/`, rewrite the record
   (with the new SHA-256s, the commit and what each screen showed), update
   `TOOLBOX_COMMIT`, the alt text and provenance, run `make_media --force`
   and commit the derivatives with them.

## Browser test

`test_media_browser.py::test_toolbox_screenshots_are_sharp_and_framed_at_every_width`
opens `/toolbox/` at 360, 768, 1280, 1440 and 2560 px, dark and light, 1×
and 2×: each frame shows its scheme's screenshot, 16:10 and drawn whole
from a file at least as wide as it's drawn in device pixels; the other
scheme's files are never fetched; nothing scrolls sideways; and each
frame is saved to `screenshots/media/` for review by eye.
`test_toolbox_screenshots_follow_a_live_switch_to_light` switches the
scheme on an open page and sees the light twin load.
