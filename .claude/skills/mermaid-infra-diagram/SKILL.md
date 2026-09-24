---
name: mermaid-infra-diagram
description: "Generate a control's 'Demo infrastructure setup (simplified)' diagram with real Microsoft/Azure service icons instead of abstract colored boxes. Primary path: draw.io XML rendered headlessly via the bundled VS Code draw.io extension, using the official Azure Public Service Icons set indexed at media/icons/Azure_Public_Service_Icons/icon-index.jsonl. Fallback path: Mermaid architecture-beta with Iconify icon packs, pre-rendered because GitHub does not render Mermaid icon packs live. Use when creating or refreshing a control's Demo infrastructure setup (simplified) section, or when a plain flowchart diagram should show recognizable real-world service icons instead of abstract colored boxes."
license: MIT
user-invocable: true
metadata:
  authors: "Douwe van de Ruit"
  spec_version: "2.0"
---

# Demo infrastructure setup (simplified) diagram with real icons

## Why this exists, and the one hard constraint to respect

Most controls' "Demo infrastructure setup (simplified)" sections in this repository use
a plain Mermaid `flowchart` with `classDef`-based color coding
(purple/blue/green/orange) instead of real service icons, because that is
what GitHub's built-in Mermaid renderer supports natively in a live code
block. `QLT-001_hallucination_rate_high` instead uses this skill's icon-based
pipeline (`docs/architecture.drawio` + `media/architecture.png`) -- a working
reference to copy from.

Whichever tool builds the diagram, **GitHub cannot render it live**: it does
not call Mermaid's `registerIconPacks()` for `architecture-beta` icons, and
it has no draw.io renderer at all for `.drawio` XML. Either way the only
option is to pre-render the diagram locally to a static PNG and commit that
image -- the same "capture once, commit the artifact" pattern this
repository already uses for screenshots (`scripts/capture_teams_card.py`).
This means an icon-based architecture diagram is **not** a live-editable
code block like this repository's other diagrams: every future edit
requires re-running the render step and re-committing the image. Say this
trade-off out loud to the user before switching a control over, and keep the
diagram source file (`.drawio` or `.mmd`) committed alongside the image so it
can be re-rendered.

## When to use

- Creating a new control's "Demo infrastructure setup (simplified)" section and real
  Azure/Microsoft/GitHub/Python service icons would make the building blocks
  easier to recognize than colored boxes.
- The user asks to add or refresh real icons on an existing control's
  architecture diagram.
- Do **not** use this for "Logical design" diagrams (decision flow, not
  building blocks) -- keep those as plain `flowchart` code blocks per
  `.github/instructions/governance-controls.instructions.md`.

## Which tool: draw.io (preferred) or Mermaid (fallback)

Use **draw.io** (`scripts/render_drawio_diagram.py`) unless the VS Code
"Draw.io Integration" extension (`hediet.vscode-drawio`) is not installed on
this machine. It is the better fit for this repository specifically because
`media/icons/Azure_Public_Service_Icons/` already holds the official,
Microsoft-published Azure Public Service Icons set (714 SVGs across ~29
categories) with a prebuilt search index -- draw.io just needs a relative
path to one of those files, no icon-pack build step, no CORS server, and
free-form pixel-precise layout instead of Mermaid's `architecture-beta`
auto-layout (which produced label/icon overlap and awkward spacing on
earlier attempts).

Fall back to **Mermaid** (`scripts/render_architecture_diagram.py`, see
"Mermaid fallback" below) only when the draw.io extension genuinely is not
available and installing it is not an option -- it needs its own local
Iconify icon-pack build step and a CORS-enabled local server for any
official custom icon, which is more moving parts for the same result.

## draw.io workflow (preferred)

### One-time setup (author-only, per machine)

Install the "Draw.io Integration" VS Code extension
(`hediet.vscode-drawio`, marketplace id `hediet.vscode-drawio`) if it is not
already present. Nothing else to install: `scripts/render_drawio_diagram.py`
drives the extension's own bundled copy of the diagrams.net web app with
Playwright (already a repository dependency via `capture_teams_card.py`),
serving it over a throwaway local HTTP server (it needs http://, not
file://, for its own internal resource fetches) and reusing the system
Chrome via `--channel chrome` by default.

### Steps

1. **Decide what belongs in the diagram before listing building blocks.**
   Default to showing the *core mechanism* -- what a first-time reader needs
   to understand why this control works -- not every plumbing detail of how
   it happens to be run today. Confirmed the hard way on QLT-001
   (2026-09-24), across several rounds of feedback: an early version made
   authentication (`az`/`azd auth login`) and the execution environment
   ("Local developer workstation (not an Azure resource)") into the most
   visually prominent nodes, each with its own box, badge, and long
   connecting line -- and the reviewer's reaction was that authentication
   "is not really the key thing to show here," and that naming the exact
   current execution environment "feels cumbersome" for a detail that could
   change (it could just as well be an Azure Function tomorrow). The fix
   that stuck: cut auth and the execution environment out of the diagram
   entirely and cover them in one prose sentence *above* the image instead
   (for example "This control's infrastructure is minimal: `demo.py`, run
   locally and authenticated via `az`/`azd auth login`, orchestrates every
   step below against an already-deployed Foundry project") -- then draw
   only the causal chain that explains the control's actual mechanism (a
   hosted agent's output is scored, the score becomes a decision, a
   breaching decision notifies someone). Treat "does every node in this
   diagram help someone understand why this control works, or does it just
   describe today's deployment convenience" as the filter, and default to
   prose for anything that fails it. A hosting detail earns a diagram node
   only when it is itself the notable fact (for example, a control whose
   whole point is a specific network boundary or managed identity).

2. **List the real building blocks** that survive that filter: the hosted
   agent/service, the platform capability that provides its signal, the
   component that turns the signal into a decision, and any external
   destination (Teams, GitHub Actions).

3. **Differentiate from this control's "Logical design" section.** Every
   control README already has a "Logical design" Mermaid flowchart showing
   the decision *branches* (which threshold produces which outcome).
   Demo infrastructure setup (simplified) should not redraw the same branches with
   icons instead of colored boxes -- that is pure duplication with no new
   information. Show the building blocks and the *data flow* between them
   instead (what calls what, what artifact produces what), and say so
   explicitly in the prose above the image so the two sections' distinct
   jobs are legible to the reader, not just to whoever designed them (for
   example: "This is a different view from 'Logical design' above, not a
   repeat of it: Logical design shows the three decision branches; this
   diagram shows the building blocks and data flow that produce the score
   those branches decide on").

4. **Find a real icon for each node** by searching the index instead of
   guessing a filename:

   ```zsh
   grep -i "foundry agent" media/icons/Azure_Public_Service_Icons/icon-index.jsonl
   ```

   Each match is one JSON object with a `path` (relative to
   `media/icons/Azure_Public_Service_Icons/Icons/`), `category`, `name`, and
   `slug`. Prefer the most specific official match over a generic one --
   confirmed the hard way on QLT-001 (2026-09-24): this set has precise
   icons like "Foundry Agent Service" and "Foundry Project", which are a
   real, correct match for a Foundry hosted agent and its containing
   project, not a stand-in. Re-run `scripts/index_azure_icons.py` if the
   icon set folder has been updated and the index looks stale (it is
   deterministic and diffable, so a re-run's diff shows exactly what
   changed). For anything that is not an Azure service at all (a local
   Python script, Microsoft Teams, another non-Azure product), do not force
   an Azure icon onto it. Check `media/icons/` (repo root) for an existing
   real asset first; if none exists but the official brand SVG is already
   cached locally in `.tooling/mermaid/node_modules/@iconify-json/logos/icons.json`
   (installed for the Mermaid fallback below, but its icons are legitimate
   official brand SVGs regardless of which renderer uses them), extract it
   into a standalone file once:

   ```zsh
   python3 -c "
   import json
   with open('.tooling/mermaid/node_modules/@iconify-json/logos/icons.json') as f:
       d = json.load(f)
   icon = d['icons']['python']  # or 'microsoft-teams', etc.
   w, h = icon.get('width', d['width']), icon.get('height', d['height'])
   open('media/icons/python-language.svg', 'w').write(
       f'<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{w}\" height=\"{h}\" viewBox=\"0 0 {w} {h}\">{icon[\"body\"]}</svg>'
   )"
   ```

   (an iconify pack entry is just an inner `<body>` fragment, not a
   standalone file -- it must be wrapped in a real `<svg>` root before
   `icon:` placeholder expansion or `build_icon_pack.py` can use it). Only
   if no real asset exists anywhere should a node fall back to a plain
   labeled box with no icon.

5. **Write the `.drawio` source** (an `<mxfile>` containing one `<diagram>`
   with a plain `<mxGraphModel>`) in the control's own directory, for
   example `docs/architecture.drawio`. Reference each icon with an
   `icon:<relative-path>` placeholder in a `shape=image` style -- the
   render script resolves this to a real embedded image, you never write a
   raw `data:` URI by hand:

   ```xml
   <mxCell id="agent" value="Hosted agent"
           style="shape=image;image=icon:../../../../media/icons/Azure_Public_Service_Icons/Icons/ai + machine learning/038470523-icon-service-Foundry-Agent-Service.svg;verticalLabelPosition=bottom;verticalAlign=top;fontSize=12;labelBackgroundColor=#ffffff;"
           vertex="1" parent="1">
     <mxGeometry x="608" y="110" width="64" height="64" as="geometry" />
   </mxCell>
   ```

   The path is relative to the `.drawio` file's own directory. Use a plain
   rounded rectangle with a real icon (`shape=image` as above) for anything
   with an official match, and only fall back to a plain
   `style="rounded=1;whiteSpace=wrap;html=1;fillColor=#EEF2FF;strokeColor=#6E56CF;fontSize=12;"`
   box when nothing fits -- confirmed on QLT-001 (2026-09-24) that swapping
   plain boxes for real per-node icons (the Microsoft Teams logo for a
   "Teams Workflows" node, the Python logo for each Python script node) made
   the rendered diagram noticeably more compelling than text-only boxes,
   even where no Azure-specific icon exists.

   Draw a dashed rounded rectangle *with a light fill tint*
   (`fillColor=#F5F3FF` for a Foundry/governance boundary,
   `fillColor=#EFF6FF` for a platform boundary, matching each group's
   `strokeColor`) *behind* a group of related nodes (added earlier in the
   XML so it renders behind, not as a true mxGraph parent/child container)
   to visually group them -- a filled tint reads as more finished than a
   transparent outline. Badge the group with a real icon representing what
   the group actually is, as a separate `shape=image` cell layered near the
   group's top-left corner, with the text label (a separate plain
   `style="text;html=1;..."` cell, not the group rectangle's own `value`)
   offset to the right of the badge rather than overlapping it -- confirmed
   on QLT-001 (2026-09-24) that a "Microsoft Foundry project" group with no
   Foundry badge and a "Local developer workstation" group with no device
   badge both read as incomplete once a reviewer compared them to the
   fully-iconed nodes inside. **Give every icon in the diagram the same
   geometry (for example 64x64) -- badges included.** A first pass at this
   used a smaller size (24-28px) for group badges than for the main nodes;
   the user immediately flagged it as inconsistent, and separately, some
   official icons (a thin ribbon mark like "AI Foundry") visually read as
   smaller than a bolder icon (a solid hexagon) even at the *exact same*
   bounding box, because the artwork itself uses less of its own canvas --
   render a same-size comparison strip (see the size-check pattern below)
   before assuming equal geometry means equal visual weight. **Center a
   group's main icon(s) within the group's width, not flush against its
   left edge next to the badge column.** A first pass placed the badge and
   the main icons in the same left-aligned column, leaving a wide unused
   strip down the right side of every group -- confirmed on QLT-001
   (2026-09-24) that this reads as unfinished ("icons hugging the wall
   instead of standing in the room"). Compute `icon_x = group_x + (group_
   width - icon_width) / 2` for the main icons; leave the header badge
   left-aligned next to its label, since a badge-plus-label header is
   conventionally left-aligned like a title bar and centering it would look
   stranger, not better. Use a small, fixed corner radius on group
   rectangles instead of `rounded=1`'s default (which reads as an oversized
   pill on a large box): `rounded=1;arcSize=5;absoluteArcSize=1;` fixes the
   radius at 5px regardless of the rectangle's size, rather than scaling
   the radius as a percentage of the shorter side. Connect nodes
   with edges styled per relationship type, not one identical arrow for
   everything -- see "Differentiate edges by meaning" below. Keep node count
   small and labels short -- this is still a bite-sized diagram, not a full
   topology map.

### Differentiate edges by meaning

A diagram where every edge is an identical black arrow forces the reader to
infer what kind of relationship each one is. Give each distinct kind of
relationship its own color, dash pattern, and short label, reusing this
repository's palette so the meaning stays consistent across controls:

- Solid black or gray, no label or a short factual label -- plain
  sequential/data flow (one node's output directly becomes the next node's
  input).
- Teal (`strokeColor=#00A3BF`) labeled "notifies" -- a message sent to a
  human or a notification channel.
- Purple (`strokeColor=#A855F7` or `#7E22CE`) labeled "invokes" -- a call
  into a governed/hosted component.

Note: an earlier version of this guidance recommended a dashed amber edge
labeled "authenticates via" for auth/identity steps. Per "Decide what
belongs in the diagram" above, authentication is now a prose note above the
image, not a node or edge -- if a control's diagram still has an
"authenticates via" edge, that is a sign it should be simplified, not a
pattern to copy into a new diagram.

**Prefer solid over dashed once dashed no longer carries real meaning.**
Dashed strokes are useful for a genuine distinction (for example "Foundry's
own internal mechanism" vs. "this control's own code calling out"), but two
real problems show up otherwise: (1) a small, confirmed rendering artifact
where a dash's phase lands exactly at a label's background-rectangle edge
and peeks a couple of pixels beyond it, visible even with
`labelBackgroundColor=#ffffff` set and not fixed by padding the label text
-- switching the edge to solid removes the artifact entirely rather than
fighting it; (2) once a diagram is simplified down to a single causal chain
(see above), every edge in it is the same kind of "this produces that"
relationship, so a dashed/solid split stops encoding any real distinction
and is just inconsistent for its own sake -- confirmed on QLT-001
(2026-09-24), where dashed styling left over from a more complex, multi-
actor version of the diagram no longer matched anything once the diagram
was cut down to four nodes.

**Don't duplicate a fact the prose above the diagram already states.**
If a detail is already established in the sentence introducing the image
(for example "scored by a *batch* evaluation run"), don't also cram it into
an edge label -- confirmed on QLT-001 (2026-09-24): adding "(batch eval
run)" to an edge label that already had a full-sentence-worth of text made
the label wide enough to visually collide with the arrowhead at the far end
of its own routing segment. Add the qualifier to the prose (or shorten the
segment/widen the gap) rather than to an already-long label.

```xml
<mxCell id="e1" value="notifies"
        style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;strokeWidth=2;strokeColor=#00A3BF;fontColor=#00A3BF;fontSize=11;labelBackgroundColor=#ffffff;exitX=0;exitY=0.5;entryX=0;entryY=0.5;"
        edge="1" parent="1" source="runner" target="teams">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

### Route edges deliberately -- floating connections cross and collide

mxGraph's default "floating" connection (no `exitX`/`exitY`/`entryX`/`entryY`,
no waypoints) picks whatever point on each shape's perimeter is closest to
the other shape's center. This looks fine for one isolated edge and produces
two real, confirmed failure modes once a diagram has several:

1. **Edges cross each other** when two edges leave the same source toward
   targets on opposite sides, because each one's floating exit point can end
   up more central than expected. Fix: pin `exitX`/`exitY` and
   `entryX`/`entryY` explicitly (fractions 0-1 of the shape's own bounding
   box) on every edge, and add `edgeStyle=orthogonalEdgeStyle;rounded=0;` so
   the line bends at right angles instead of drawing a diagonal.
2. **An edge cuts straight through an unrelated icon or label** when its
   shortest path happens to pass through a group's badge/label header on the
   way from an interior node to a target outside the group. Fix: give the
   edge explicit waypoints (`<Array as="points"><mxPoint x=".." y=".."/>...</Array>`
   inside the edge's `<mxGeometry>`) that route it outside the group's
   bounding box first, then up or across to the target, instead of straight
   through the group's interior. Confirmed on QLT-001 (2026-09-24): two
   edges from a node inside a group to two nodes above the group both
   originally cut straight through that group's badge icon; adding one
   waypoint just outside each side of the group's bounding box before
   turning toward the target fixed it.

Separately, **an edge's own auto-placed label can land exactly on top of a
nearby node's label** if the edge's midpoint happens to coincide with where
that node's label sits below it -- confirmed on QLT-001 (2026-09-24), where
a vertical edge's default centered label overlapped the source node's own
label directly above it, rendering as garbled overlapping text. Fix: give
the edge no `value` and add a separate manually positioned `style="text;..."`
cell for its label instead, positioned in whatever free space actually
exists (increase the gap between the two connected nodes first if none
does), rather than trusting the edge's automatic midpoint placement.

**A chain of nodes at the same height needs its connecting edges routed
above or below the icon row, never through the icons' own vertical
center.** `entryY=0.5`/`exitY=0.5` connects at each icon's vertical
midpoint, which is *inside* the icon artwork when both nodes sit at the
same height -- confirmed on QLT-001 (2026-09-24): a simplified left-to-right
chain of four same-height icons rendered its connecting lines and labels
directly behind the icon glyphs, invisible against the artwork. Fix: route
every edge in the chain along a shared horizontal "spine" a fixed distance
above the icon row instead -- `exitX=0.5;exitY=0` (icon's top-center) with a
waypoint at the same `x` a fixed offset above the icons (for example 20px),
across to the target's `x` at that same spine height, then down into
`entryX=0.5;entryY=0` (target's top-center). Because the segments between
different node pairs in a simple left-to-right chain don't share an `x`
range, every edge can use the *same* spine height without colliding with
its neighbors -- there's no need to stagger heights unless two edges
actually cross the same `x` range.

### Verify icon sizing and edge layout before calling it done

Two verification passes catch what "does it render at all" does not:

1. **Size comparison.** Render every candidate icon at the same fixed
   geometry (for example a row of `shape=image` cells all sized 64x64) in a
   disposable test diagram before wiring them into the real one, and look
   at whether they read as visually equal -- not just whether the bounding
   box matches. A thin ribbon-style logo can look smaller than a solid
   geometric icon at an identical box size.
2. **Full-diagram visual review**, specifically checking for: any label
   touching or overlapping the icon above it, any two edges crossing each
   other, any edge passing through an icon or a label instead of empty
   space, and how much unused white space the group boxes contain relative
   to their actual content (a box sized for content that got trimmed later
   reads as an unfinished layout). Treat "the command exited 0 and produced
   a PNG" as necessary, not sufficient.
3. **Scope review**: does any node exist only to describe today's
   deployment/execution convenience rather than to explain why the control
   works (see "Decide what belongs in the diagram" above)? Does the diagram
   redraw the same decision branches "Logical design" already shows instead
   of showing building blocks and data flow? Both were real, repeated
   findings on QLT-001, not hypothetical risks -- check for them explicitly
   rather than assuming a diagram that renders cleanly is also well-scoped.

6. **Render it**:

   ```zsh
   .venv/bin/python scripts/render_drawio_diagram.py \
       --input controls/<category>/<ID>/docs/architecture.drawio \
       --output controls/<category>/<ID>/media/architecture.png
   ```

   The export format embeds the source XML in the PNG's own metadata
   (`xmlpng`), so the committed image is also directly re-openable and
   re-editable in the VS Code draw.io extension, not just a dead-end
   raster -- a nice side benefit over the Mermaid pipeline's plain PNG.

7. **Verify the output visually** before committing: open the rendered
   image and confirm every icon shows a real logo/glyph, not a broken-image
   placeholder. A broken image most often means either the `icon:` path is
   wrong relative to the `.drawio` file's directory, or (if hand-editing
   the style outside this script's placeholder mechanism) a raw `;` snuck
   into an embedded `data:` URI -- mxGraph's style parser does a naive
   `style.split(';')` (confirmed 2026-09-24 by reading
   `mxgraph/src/view/mxStylesheet.js` in the bundled extension), so any
   literal semicolon inside a value silently truncates it. This is exactly
   why the render script's `icon:` placeholder expands to a **non-base64**,
   fully percent-encoded `data:image/svg+xml,...` URI instead of the more
   common `data:image/svg+xml;base64,...` form: the base64 form's own
   `;base64,` segment contains the one semicolon that breaks it.

8. **Embed the image in the README**, following this repository's existing
   `<img>`-with-caption convention:

   ```html
   <p align="center">
       <img src="media/architecture.png" alt="<describe what the diagram shows>" width="900">
   </p>
   ```

   Do **not** add a "Source: docs/architecture.drawio ... re-render it with
   `scripts/render_drawio_diagram.py`" caption sentence after the image --
   confirmed on VAL-001 and QLT-001 (2026-09-25) that this is authoring
   information (how a maintainer regenerates the picture), not something
   the reader of the control needs, and it was removed from both. The
   `.drawio` source being committed next to the image (see the next step)
   is enough for a future editor to find it; a diffable git history and the
   file's own presence in `docs/` already answer "where does this come
   from" without spending a reader-facing sentence on it.

   The declared `width` must equal the actual rendered image's pixel width
   (this repository's own tests enforce that) -- resize the PNG first if
   the raw render is wider than is comfortable to read, and update `width`
   to match the resized file, not the original.

9. **Keep the `.drawio` source committed** next to the image so a future
   edit only needs to change the source and re-run step 4.

## Mermaid fallback (when the draw.io extension is unavailable)

The same pipeline this skill previously used exclusively still works and is
still the right choice for a machine without the draw.io extension
installed:

1. One-time setup: `mkdir -p .tooling/mermaid && cd .tooling/mermaid && npm init -y && npm install @mermaid-js/mermaid-cli @iconify-json/logos && cd -`
   (`.tooling/` is gitignored; never add these packages to a control's own
   dependency files).
2. Write `docs/architecture.mmd` using `architecture-beta` syntax
   (`service name(logos:microsoft-teams)[Teams Workflows]`, `group id(icon)[Label]`,
   edges as `from:SIDE --> SIDE:to`).
3. Pick icons from, in order: a user-supplied official asset in
   `media/icons/` turned into a local pack with `scripts/build_icon_pack.py`
   (referenced as `--local-icon-pack fwf#media/icons/fwf-icons.json`, served
   with a CORS header the script already adds -- a locally-built pack
   fetched without one silently fails and renders a "?"); `logos:<name>`
   from the installed `@iconify-json/logos` set; `azure:<name>` from the
   community pack fetched by URL via `--iconPacksNamesAndUrls`; no icon at
   all if nothing fits.
4. Render: `python3 scripts/render_architecture_diagram.py --input docs/architecture.mmd --output media/architecture.png [--local-icon-pack ... ] [--chrome "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]`.
5. Verify visually, embed in the README, and keep the `.mmd` committed --
   same as steps 5-7 of the draw.io workflow above.

### Verify relationships against the actual code, not memory or a prior summary

Before drawing an edge between two building blocks, confirm what actually
calls what by reading the control's own entry point (`demo.py` or
equivalent), not by reasoning from an earlier design description or a
mental model carried over from a previous session. Confirmed the hard way
on QLT-001 (2026-09-24): an earlier pass drew `az / azd auth login` as the
node that invokes the hosted agent, and drew the agent's output as flowing
into a passive downstream "Eval definition" scorer. Reading `demo.py`
directly showed both were wrong -- authentication is a one-time prerequisite
with no outgoing calls of its own, and `demo.py` itself is the caller that
directly invokes the agent (`azd ai agent invoke`) *and* directly triggers
and reads the eval run (`azd ai agent eval run`, then
`openai_client.evals.runs.output_items.list`); the agent's involvement in
scoring happens through Foundry's own eval-run mechanism, not through a
call chain `demo.py` orchestrates end to end. A visually polished diagram
that draws the wrong caller is worse than an ugly one that draws the right
one -- treat "does this match what the code actually does" as a required
check, equal in weight to the visual checks in the previous section.

### Do not add step numbers, even if asked for "reading order"

The Demo infrastructure setup (simplified) diagram is a component overview, not an
execution trace -- `docs/control-readme-template.md` says so explicitly
("This is a component overview, not a numbered execution trace"). If a
reviewer asks for a way to tell reading order from the image, resist adding
①②③-style sequence numbers to nodes or edges; that reintroduces the exact
call-order framing the template rules out, and this control's own several
CLI subcommands (`run`, `evaluate`, `notify`) are invoked as separate,
independently-runnable steps by an operator, not one atomic top-to-bottom
sequence a numbered diagram would honestly represent. Address the concern
with descriptive edge labels (what relationship this is) instead of
sequence numbers (when it happens).

## What this does not replace

- "Logical design" diagrams stay plain `flowchart` code blocks -- decision
  flow, not building blocks, and no rendering pipeline is needed for them.
- A control with no interesting real-world services to show (for example, a
  guided exercise with no deployed components) should keep stating
  "Not applicable" rather than forcing an icon diagram where none is
  warranted.
