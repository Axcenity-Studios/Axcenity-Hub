# PRD — Axcenity Hub

Sources: the project proposal ("Web based application proposal", 11/7/2026),
a design interview (2026-11-23, 17 decisions), the external-services research
note, and the Home prototype outcome. Where this PRD and the proposal
disagree, this PRD wins (it records later, deliberate decisions).

## Problem Statement

Axcenity Engine has no central home. People considering the engine can't
see what it does or how it looks in action; people using it have no single
place for documentation, downloads, resources, project and team
management, bug reports or community discussion. The engine's existing
companion tool (Axcenity Toolbox) lives in a separate repo with nothing
pointing visitors to it. As a student project, the Hub must also show
solid Django practice: authentication, permissions, validated CRUD,
search/filter/pagination, business rules enforced server-side, an API, an
external API integration and automated tests.

## Solution

Axcenity Hub is a Django web app built in vertical slices.

**First slice (this PRD's immediate focus): the public marketing site.** A
cinematic, motion-rich landing page that sells the engine honestly: a
full-bleed animated showcase reel as the hero, a rotating headline, four
feature pillars, the engine's build/script/test/export workflow, open-source
and platform facts, a teaser for the Toolbox, a coming-soon preview of
community features, and clear Download and Docs calls to action. A
standalone Toolbox overview page sits in the main navigation. The site
looks like Axcenity (the editor's own palette, fonts and 1px panel
language) but feels distinct from the Toolbox: cinematic rather than
tool-like, with the editor's selection blue as its single accent.

**Later slices** deliver the proposal's application: an API-backed download
page, accounts, GitHub sign-in and repo linking, projects and teams,
forums, showcases, bug reports and report management, moderation, a REST
API, and eventually porting the Toolbox's apps into the Hub. Each later
slice builds its key business rules test-first.

## User Stories

### Visitors: marketing Home

1. As a visitor, I want the first screen to show the engine in motion, so that I immediately understand it's a real 3D engine with a modern editor.
2. As a visitor, I want a short rotating headline (build worlds, script in Luau, ray trace in real time, ship to every desktop), so that I grasp the engine's range in seconds.
3. As a visitor, I want the headline's rotation to never shift the page layout, so that the page feels polished.
4. As a visitor, I want to see the engine's version and that it's free, open source and in alpha, so that my expectations are honest.
5. As a visitor, I want a prominent Download button, so that I can get the engine right away.
6. As a visitor, I want a Docs button, so that I can learn before installing.
7. As a visitor, I want each key capability (ray-traced renderer, terrain and foliage, visual blocks plus Luau, dockable multi-monitor editor) presented with its own media, so that I can judge each one.
8. As a visitor, I want feature media to swap smoothly as I scroll past each pillar, so that the page feels cinematic.
9. As a visitor, I want feature media to be sharp on high-DPI screens, so that the engine doesn't look low quality.
10. As a visitor, I want illustrative visuals labelled as illustrative, so that I'm never misled about what the engine renders.
11. As a visitor, I want the build → script → test (F5) → export workflow shown at a glance, so that I understand how making a game works.
12. As a visitor, I want the platform and licence facts (Windows, macOS, Linux, Rust, free, alpha), so that I know whether it fits me.
13. As a visitor, I want a teaser for the Axcenity Toolbox, so that I discover the companion asset tool.
14. As a visitor, I want to see that forums, showcases and projects are coming, so that I know the community is planned.
15. As a visitor, I want a closing call to action and a full footer, so that I can act or navigate when I reach the end.
16. As a visitor, I want a slim sticky navigation that turns solid once I scroll, so that I can always move around without it covering the hero.
17. As a visitor, I want to choose light, dark or system theme, so that the site suits my preference.

### Visitors: the showcase reel

18. As a visitor, I want a 15–18 second reel that loops seamlessly with no visible reset, so that it reads as a polished product film.
19. As a visitor, I want the reel to show editor panels (Viewport, Hierarchy/Explorer, Inspector/Properties) snapping into an undocked multi-monitor layout, so that I see the editor's flexibility.
20. As a visitor, I want the reel to show a shader wipe from wireframe/graybox to lit PBR with ray-traced reflections and ambient occlusion, so that I see the renderer's quality.
21. As a visitor, I want the reel to show a terrain grid rising into hills and foliage scattering onto it, so that I see world-building tools.
22. As a visitor, I want the reel to show two logic nodes (OnTriggerEnter → SpawnDecal) wiring up while matching Luau types out beside them, so that I see visual scripting and code working together.
23. As a visitor, I want the reel to end on the Axcenity logo lockup, so that the brand lands.
24. As a visitor, I want the reel to look like the real editor (its palette, panel names and highlighting), so that what I see matches what I'll download.
25. As a visitor, I want play/pause and a scrubber with scene markers, so that I can study a moment.
26. As a keyboard user, I want Space to toggle play and ←/→ to jump between scenes, so that I can control the reel without a mouse.
27. As a screen-reader user, I want a short text description of the reel and properly labelled controls, so that I get the same information.
28. As a visitor who prefers reduced motion, I want the reel not to autoplay and to show its final logo frame with a Play button, so that motion is my choice.
29. As a visitor who prefers reduced motion, I want scroll reveals and the rotating headline to appear in their final state, so that the page is calm.
30. As a phone visitor, I want a compact reel layout with fewer panels and larger text, so that it stays readable on a small screen.
31. As a visitor, I want the reel to pause when it's off screen or the tab is hidden, so that it doesn't waste battery or CPU.
32. As a visitor, I want the reel to stay smooth (target 60 fps) and crisp on Retina displays, so that it feels high quality.

### Visitors: Toolbox page

33. As a visitor, I want a Toolbox page in the main navigation, so that I can learn about the companion tool.
34. As a visitor, I want the Toolbox page to explain finding free assets (ambientCG, Poly Haven, Openverse), saving them to a library and building engine-ready packs, with real screenshots, so that I understand its value.
35. As a developer, I want the Toolbox page to show how to run it locally and link to its repository, so that I can use it today.
36. As a visitor, I want the Toolbox page to share the Toolbox's panel look inside the Hub's marketing shell, so that the two products feel related.

### Visitors: download (later slice)

37. As a visitor, I want a download page that highlights the build for my operating system, so that I pick the right file.
38. As a visitor, I want to see the version, release date, file sizes and checksums, so that I can download confidently.
39. As a visitor, I want the download page to keep working when GitHub is down or rate-limited (cached data or a link to GitHub), so that I'm never stuck.
40. As a visitor, I want prerelease builds clearly marked as alpha, so that I know their stability.

### Accounts and GitHub (later slices)

41. As a new user, I want to register with unique, validated account details, so that I have my own Hub account.
42. As a user, I want to sign in, sign out and recover my password, so that I can access my account securely.
43. As a user, I want to manage my profile, so that others see accurate information.
44. As a developer, I want to connect my GitHub account, so that I can link my engine repositories.
45. As a user, I want signup and password reset protected from bots, so that the community stays clean.

### Projects and teams (later slices)

46. As a developer, I want to create a project and connect a GitHub repository, so that my engine work is organised in the Hub.
47. As a developer, I want to be stopped from owning more than 5 projects, so that limits are fair.
48. As a developer, I want project names to be unique across the Hub (case-insensitive), so that projects are unambiguous.
49. As a project owner, I want to invite members and assign Owner, Maintainer or Viewer roles, so that my team has the right access.
50. As a project owner, I want only owners to manage memberships and permissions, so that control stays with me.
51. As a Viewer, I want read-only access to only what I've been granted, so that private resources stay private.
52. As a developer, I want my GitHub repository permission verified before repo-dependent actions, so that the Hub never grants more than GitHub does.
53. As a developer, I want repository information to stay current through caching and webhooks, so that the Hub reflects my repos.

### Community (later slices)

54. As a registered user, I want to create, edit, delete, comment on and rate forum posts, so that I can share knowledge.
55. As a registered user, I want to be limited to 5 new posts per day and 5 comments per minute, so that the forums stay readable.
56. As a registered user, I want to publish, edit, delete and interact with showcases (at most 1 new one per day), so that I can show my work.
57. As a visitor, I want to find showcases by tag, so that I can browse what interests me.
58. As a visitor, I want to search, sort, filter and paginate projects, forums, showcases and documentation, so that I find things quickly.
59. As a user, I want to modify only my own content, so that others can't change my work.

### Bug reports and moderation (later slices)

60. As a registered user, I want to submit validated, rate-limited bug reports and feedback with supporting information, so that engine issues get fixed.
61. As a project owner or administrator, I want to review, assign, comment on and update reports, so that issues move forward.
62. As a project owner, I want report statuses to follow only permitted transitions, so that the workflow stays consistent.
63. As a user, I want access to reports restricted to the relevant project authorities and administrators, so that sensitive reports stay private.
64. As an administrator, I want to review content, issue warnings and restrict accounts, so that the community stays healthy.
65. As an administrator, I want every moderation action recorded, so that there's an audit trail.
66. As an administrator, I want administrative actions to require authorisation, so that only admins can moderate.

### API and integrations (later slices)

67. As the Axcenity Engine, I want an authenticated REST API for project and asset information, so that the editor can later integrate with the Hub.
68. As a member, I want to use the Toolbox's asset search, library and packs inside the Hub with my Hub account, so that I don't need a second login.

### Maintainers

69. As the maintainer, I want fast tests that never touch the network, so that I can run them on every change.
70. As the maintainer, I want a small set of browser smoke tests for the reel, so that regressions in its JavaScript are caught.
71. As the maintainer, I want Home's copy and links kept as data, so that I can edit content without touching templates and tests can check every link and media file.
72. As the maintainer, I want the reel's scenes structured so they can be ported to Remotion for MP4 export, so that I can produce a video later.
73. As the maintainer, I want feature media slots that swap from stand-ins to real captures without code changes, so that I can drop in new footage.

## Implementation Decisions

### Platform and stack
- Django project in the same layout and conventions as the Toolbox: a config package, one app per area, thin class-based views, logic in models, managers and service modules, every URL named and namespaced, tests only in a top-level tests folder.
- uv is the only dependency tool. No Node, npm or bundler. Tailwind and DaisyUI come through django-tailwind-cli's standalone binary. Any JavaScript library would be a vendored static file; the first slice uses none.
- HTMX for partial updates in later slices. Django REST Framework for the API in a later slice.
- Database: SQLite for development and tests. Production target: PostgreSQL in place of the proposal's MySQL (the MySQL driver needs system C headers under uv, and MySQL's default case-insensitive collation silently changes uniqueness rules). Uniqueness that must be case-insensitive is enforced explicitly whichever database is used. Pending confirmation that MySQL isn't a course requirement.
- Secrets (GitHub, email, Turnstile keys) are read from environment variables, not edited in the admin; the admin may show whether each is configured.

### Theme and visual identity
- Port only the Toolbox's foundation: the single axcenity theme with dark and light sets (System, Light or Dark), the editor colour tokens (app, panel, surface, line, fg tiers, ink/on-ink/shade), Tailwind's and DaisyUI's default palettes switched off, Inter, JetBrains Mono and Plus Jakarta Sans, 1px panels, button and focus styles, the hover-gate, spotlight/lift and blur-up motion primitives, and reduced-motion handling. Port the theme tests that enforce these rules. Toolbox-only styles (asset-type colours, Discover, packs, drawers) are not ported.
- One accent colour: the editor's selection blue (#19A0FF dark; a darker blue on light). Used only for the primary button, the reel's progress and scan line, and the version-badge dot. All other chrome stays monochrome.
- Easing for every UI snap and reveal: cubic-bezier(0.16, 1, 0.3, 1).

### Shells
- Two base templates sharing the tokens: a marketing shell (built now) with a slim sticky top nav (wordmark; Engine, Features, Toolbox, Docs, Community; theme toggle; Sign in; Download) that's transparent over the hero and turns solid on scroll, full-bleed sections and a large footer; and an editor-style app shell (built in the first signed-in slice) for forums, projects and reports.
- Until accounts exist, Sign in is hidden or marked coming soon; it must never be a dead link.

### Marketing app and Home (Cinematic direction, chosen via prototype)
- A marketing app owns the public, signed-out pages: Home and Toolbox.
- Home sections in order: hero (full-bleed reel behind; version badge; headline "Axcenity Engine." plus the rotating line; one-line pitch; Download and Docs CTAs; reel controls bottom right); sticky-scroll feature pillars (text scrolls on the left, one large media stage on the right swaps per pillar; on phones each pillar's media sits inline); workflow strip with oversized outlined numerals; stat band (Free, Rust, 3 OS, Alpha); Toolbox banner; coming-soon community row (Forums, Showcases, Projects); giant final CTA; four-column footer.
- The rotating headline lives in a box sized to its longest phrase at each breakpoint, so changing between one-line and two-line phrases never moves content below.
- All Home copy, links and media references live in a Python content module that the template loops over.
- Download links to the engine repository's Releases list (not "latest": every release is a prerelease, so latest doesn't resolve). Docs links to the engine's documentation.
- Feature media slots are picture/video slots with captions. Editor and Blocks + Luau slots are animated recreations built from the editor's real UI code (palette, panel names and layout, node styling, Luau highlighting), captioned illustrative. The Renderer slot uses the real 2560×1440 ray-traced capture from the purpose-built engine showcase scene (with its same-camera graybox capture as the before frame for the reel's Scene 2 wipe). The Terrain slot shows a crisp drawn stand-in: the existing terrain capture is deliberately excluded because its stylised trees and flat-colour ground don't represent the terrain toolkit, and it's replaced only once a capture shows decent trees and textures. The engine's 480×270 test references are never upscaled into the page.
- Copy is honest: the engine is alpha, scripting is Luau, and drawn visuals are never presented as engine captures.

### Showcase reel
- Vanilla JavaScript: Canvas 2D for the viewport, DOM/SVG for panels, no dependencies.
- Native ES modules under the marketing static area: an entry module (mounting and controls), a timeline module (master clock, scene table, seek), an easing module (expo-out, spring, interpolation), a canvas module (devicePixelRatio scaling capped at 2, resize handling), and one module per scene.
- The scene contract is a pure function of time: each scene exports its start, its duration and render(context, time, size). Play, pause and scrub only set the clock. This is the Remotion porting seam: one scene maps to one sequence, and compact mode becomes a prop.
- Storyboard (~18 s): Scene 1 (0–4 s) boot and multi-monitor workspace, kinetic type and panels snapping into an undocked layout with springs; Scene 2 (4–8 s) wireframe/graybox to lit PBR wipe with ray-traced reflections and AO; Scene 3 (8–12 s) terrain displacement then staggered foliage scale-in; Scene 4 (12–16 s) OnTriggerEnter → SpawnDecal nodes with glowing Bezier wires and Luau typing out; 16–18 s collapse to the logo lockup. The loop's last frame must flow into its first with no visible reset.
- Visual fidelity: palette from the editor theme, Luau colours from the editor's syntax highlighter, node and wire styling from the editor's node graph, real block names from the blocks runtime, and terrain and scatter UI cues from the editor's terrain and scatter panes. The renderer's real features back the Scene 2 claims (hardware ray-traced reflections, AO, GI, shadows; path tracer).
- Compact mode below ~640 px: same timeline and aspect ratio; the viewport plus one docked panel, larger type, fewer Luau lines, shorter labels.
- Playback: autoplay and loop only while at least ~30% is visible; pause when off screen or the tab is hidden. With prefers-reduced-motion it doesn't autoplay and shows the lockup frame with a visible Play button. Controls: play/pause, scrubber with four scene ticks, Space and ←/→. Controls fade in on hover or focus and stay visible on touch. The canvas is aria-hidden with a visually hidden text description; the controls are real labelled buttons and a range input.

### Toolbox page
- A compact product page in the marketing shell: hero line, the three core features, two or three real screenshots captured by running the Toolbox locally, a "run it locally" block with its uv commands, and a GitHub link. It uses the Toolbox's panel styling inside, for visual continuity.
- The Toolbox's code stays in its own repository for now. Porting its catalog, packs and providers apps into the Hub (mounted under the toolbox path, sharing Hub accounts) is a later slice.

### Download page (next slice after the first)
- Server-side fetch of the engine repository's release list through the GitHub REST API (no token needed for public data), choosing the newest non-draft release (prereleases included, clearly marked alpha), with ETag conditional requests and roughly hourly caching. Assets are grouped by OS, the visitor's platform is highlighted, and size, date and the per-asset SHA-256 digest GitHub provides are shown. On failure it falls back to cached data, then to a plain link to GitHub Releases.

### Accounts, GitHub and later slices
- django-allauth for registration, login, logout and password recovery, plus its GitHub provider. Start with an OAuth App and no scopes (public data only); move to a GitHub App if private-repository access is confirmed as needed.
- Email: Django's console backend in development and locmem in tests; a provider (Resend or Postmark through django-anymail) once a domain is owned. SendGrid is dropped because its free plan is retired.
- Spam protection: a honeypot plus server-side limits first; Cloudflare Turnstile on signup, password reset and any anonymous form.
- Posting and creation limits (5 projects per user; 5 posts per day; 5 comments per minute; 1 showcase per day; 5 bug reports per day) are enforced as database count checks in model and service logic, not with a cache-backed rate-limit library.
- Models per the proposal: User/Profile, Project (owner, repository info), ProjectMembership (user–project with role: Owner, Maintainer, Viewer), Showcase, Tag (many-to-many with showcases), ForumPost, Comment, BugReport (status with permitted transitions), Report, ModerationAction (recorded admin actions).
- Access: members-only views require login; anything the caller doesn't own or can't see returns 404, never 403; every write is CSRF protected, including HTMX.
- File uploads go through Django's storage setting so that R2 later is a configuration change only.

### Testing
- pytest and pytest-django. Every test runs offline; an autouse guard blocks network access and external HTTP is mocked with the responses library.
- First slice: tests that pages return 200, every nav and content link resolves, every referenced media file exists, the theme and colour rules hold (ported theme tests), and the reduced-motion and no-JavaScript fallback markup is present.
- About five Playwright smoke tests (pytest-playwright, installed through uv) marked as browser tests: the reel mounts with no console errors; play/pause toggles; ←/→ jump scenes; reduced motion shows the lockup and doesn't autoplay; a phone-width viewport has no horizontal scroll. Day to day the fast suite runs without the browser marker.
- Later slices use TDD for at most three key behaviors per phase, listed in the plan (drawn from limits, ownership, roles, unique names, status transitions, admin permissions, API access and GitHub failure handling). Everything else gets tests written alongside the code.

## Out of Scope

From the proposal: advanced legal dispute management, independent repository hosting, Cloudflare R2 (designed for, not built), monetisation, and asset or marketplace features beyond the Toolbox's existing ones.

For the first slice specifically: accounts, GitHub sign-in, projects, forums, showcases, reports, moderation, the REST API, the API-backed download page and porting the Toolbox are later slices. No real email sending, Turnstile or Cloudflare until a domain is owned. No MP4 export of the reel (only a Remotion-ready structure). No JavaScript unit tests, and no pixel-comparison screenshot tests.

## Further Notes

- Reference repositories are read-only: the engine and the Toolbox. Assets and code patterns are copied into the Hub, never edited at the source. The engine showcase scene lives as its own engine project in the user's engine-projects folder.
- The four engine sites (Unity, Unreal, s&box, Godot) are design inspiration only. No code, assets or branding are copied.
- Prototype fixes to carry into the build: a longer, truly seamless loop; no grainy or upscaled images; an animated, engine-faithful workspace recreation in place of the static docs diagram; a fixed-height rotating headline.
- The canonical engine repository is the Axcenity Studios organisation's; the engine README's Releases link names an older account but redirects there.
- Open questions from the research, to settle before the slices they affect: whether GitHub is a sign-in method or only an account link; whether private repos are needed; whether the download page shows the newest prerelease (assumed yes, with an alpha banner); the production hosting target; when the domain gets bought; whether any write form is truly anonymous; and whether MySQL is a course requirement.
- The proposal's workflow "Browse Documentation Information" (public, no authentication) is covered by the first slice's public pages; documentation itself links to the engine's docs until a docs area is planned.
