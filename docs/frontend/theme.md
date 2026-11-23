# Theme: colour, light and dark, fonts, branding and motion

All colour lives in `styles/source.css`. `tests/test_theme.py`,
`tests/test_shell.py` and `tests/test_theme_switch.py` enforce every rule
here. Ported from the Axcenity Toolbox's theme foundation; its type
colours and page glows are not part of the Hub.

## The palette

- `@theme static { --color-*: initial; }` drops Tailwind's palette, and the
  DaisyUI plugin's `themes: false` drops DaisyUI's themes. The only theme
  is `axcenity` (`<html data-theme="axcenity">`).
- **Utility colours** (the editor's palette, `crates/editor-kit/src/theme.rs`):
  `app`, `panel`, `surface`, `elevated`, `inset`, `control`,
  `control-hover`, `control-active`, `line`, `line-strong`, `fg`,
  `fg-strong`, `fg-secondary`, `fg-weak`, `fg-muted`. `white` and `black`
  exist but are never used directly.
- **Contrast tokens:** `ink` (white on dark, `#18181B` on light) for hover
  inversion, the focus ring and the current-page underline; `on-ink` for
  what sits on ink; `shade` for shadows and backdrops.
- Every hex value in the file is on an allow-list, and `rgb()`/`hsl()`
  aren't used at all.

## The one accent

The editor's selection blue: `#19A0FF` on dark, `#0B67B8` on light. It is
DaisyUI's `primary` and `accent` role and has exactly these uses:

- the primary button (`btn btn-primary`): Download, Download alpha
- the version badge's dot (`.badge-dot`, the only `var(--color-accent)`)
- the reel's progress fill (`.reel-fill`); Phase 4 adds its scan line,
  drawn on the canvas

Its hex values appear only on the token lines (tested). On dark the
primary button's text is `#171717`: white on `#19A0FF` is 2.8:1 and fails
AA. On light it's white (5.8:1).

## Contrast

`test_theme.py` reads every token's value in both modes from the
stylesheet and checks each real foreground/background pair:

- **Text, 4.5:1:** body and headline text, nav and footer links, pitch
  and badge text, the Soon label, footer headings, primary and quiet
  buttons at rest and hovered or focused, status colours, and the Home's
  media captions, Luau sample and drawn editor.
- **Non-text, 3:1:** the focus ring on app, panel and surface, the badge
  dot, the primary button's edge, the current-page underline, the
  theme and menu icons, the workflow numerals' outline and the drawn
  terrain's lines.

Further tests tie each pair to its CSS rule, and check that a page's text
colour classes are all from the tested set. **Adding a new colour pairing
means adding its row to `TEXT_PAIRS` or `NON_TEXT_PAIRS`.**

## Light and dark

- **The choice:** System, Light or Dark, in the `ax-theme` cookie
  (`config/theme.py`). Only those three exact strings are accepted, on
  every read and write; anything else counts as System and is never
  echoed into the page.
- **The cookie:** `SameSite=Lax`, `path=/`, one year
  (`COOKIE_MAX_AGE`), and `Secure` whenever `THEME_COOKIE_SECURE` is on
  (it follows `not DEBUG`, like the session and CSRF cookies). It isn't
  HttpOnly: it's a harmless display preference the page's own script
  writes.
- **First paint:** the server renders `<html data-scheme-choice="…">` and,
  for Light or Dark, `data-scheme`. For System, an inline `<head>` script
  (before the stylesheet) sets `data-scheme` from
  `matchMedia("(prefers-color-scheme: light)")` and follows it live. The
  script also resets any unknown choice to System. Without JavaScript,
  System is dark.
- **The switch:** the nav's `#theme-toggle` (monitor, sun or moon icon)
  steps System → Light → Dark. `shell.js` switches at once and writes the
  cookie with the same attributes (`Secure` on HTTPS). Without
  JavaScript, the form POSTs `choice` (with CSRF) to `marketing:theme`.
  That view rejects unknown values with a 400 and only follows a
  same-site `next`.
- **Dark** is the default (the `@theme static` values; `static` emits every
  token as a variable, used or not, because the reel's canvas reads them). **Light** is
  `html[data-scheme="light"] { … }`: the Toolbox's storm grey (app
  `#BEC0C2`, panel `#CACCCE`), darker text, lines and status colours, the
  darker accent, and `--logo-filter: invert(1)` for the white wordmark.
  There's no `prefers-color-scheme` media query in the CSS, so Light and
  Dark can override the OS.

## Fonts

Served from `static/fonts/`, never a CDN. Sources, pins and licences:
`static/fonts/SOURCES.md`.

| Use | Family | How |
|---|---|---|
| Body | Inter | Default (`font-sans`) |
| Display headlines | Plus Jakarta Sans 800, `-0.035em` | `.display` |
| Page headlines | Plus Jakarta Sans 700, balanced | `.headline` |
| Micro-labels | JetBrains Mono, uppercase | `.micro` |

`base.html` preloads JetBrains Mono Regular, Inter Regular and SemiBold,
and Plus Jakarta Sans. Mono and display fonts use `font-display: block`
so they never paint in a fallback and then jump; Inter swaps.

## Branding

- `static/brand/` holds `wordmark-white.png`, `mark-white.png` and
  `favicon-32.png`, copied from the engine's `assets/branding/`. The
  identity is black, white and grey only.
- The nav and footer show the wordmark as an `<img class="logo-img">`
  (inverted in light mode). `.mark` and `.word` are CSS-mask versions that
  take `currentColor`, with URLs from `--mark-url` and `--word-url` on
  `<html>`.

## Components

- **Buttons:** DaisyUI `btn`. `btn-primary` is the accent; `btn-quiet` is
  outlined (`line-strong`) with `fg-strong` text. Hover and focus invert
  fully: quiet goes to ink with on-ink text; primary goes to on-ink with
  ink text and an ink edge.
- **Focus:** one ring everywhere: `outline: 2px solid var(--color-ink);
  outline-offset: 2px`. `.btn:focus-visible` restates it over DaisyUI's.
- **1px panels:** `.panel` (panel fill, inset 1px `line`).
  `.grid-bg` is the faint ink dot grid.
- **Badge:** `.badge-pill` with `.badge-dot`. **Soon:** `.soon` with
  `.soon-tag`, both `fg-weak`.

## Motion

- **Easing:** `--ease-expo` (`cubic-bezier(0.16, 1, 0.3, 1)`, the
  `ease-expo` utility) is the only cubic-bezier in the file.
- **Hover gate:** every `:hover` selector starts `html[data-pointer]`.
  `shell.js` sets `data-pointer` only once the pointer has really moved
  (more than 4 px), so nothing flips under a still cursor on page load.
- **Primitives** (ported as reusable classes; Phase 2 uses them):
  - `.spotlight`: a 16 rem pool of ink (9 %, 6 % light) that follows the
    mouse; `shell.js` sets `data-spot`, `--spot-x` and `--spot-y`. Mouse
    only.
  - `.lift`: rises 4 px onto `--lift-shadow` with an ink edge; a 4 px
    `::after` keeps the hover once the element has risen.
  - `.blur-up`: rises out of a 10 px blur, `--stagger` × 40 ms late,
    fill `backwards`.
- **Reduced motion:** a blanket rule turns off every animation, transition
  and smooth scroll. The spotlight is hidden and never lit, and lift
  doesn't move. Every entry animation runs from a `from` state to the
  element's own style, so the content shows at rest. Every `animation:`
  names real keyframes (tested).
