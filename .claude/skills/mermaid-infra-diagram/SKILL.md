---
name: mermaid-infra-diagram
description: "Generate a control's 'Infrastructure architecture' diagram using Mermaid's architecture-beta syntax with real Microsoft/Azure service icons (Iconify SVGs), then pre-render it to a static image because GitHub does not render Mermaid icon packs live. Use when creating or refreshing a control's Infrastructure architecture section, or when a plain flowchart diagram should show recognizable real-world service icons instead of abstract colored boxes."
license: MIT
user-invocable: true
metadata:
  authors: "Douwe van de Ruit"
  spec_version: "1.0"
---

# Mermaid infrastructure diagram with real icons

## Why this exists, and the one hard constraint to respect

Most controls' "Infrastructure architecture" sections in this repository use
a plain Mermaid `flowchart` with `classDef`-based color coding
(purple/blue/green/orange) instead of real service icons, because that is
what GitHub's built-in Mermaid renderer supports natively in a live code
block. `QLT-001_hallucination_rate_high` is the first control that instead
uses this skill's icon-based pipeline (`docs/architecture.mmd` +
`media/architecture.png`) -- a working reference to copy from.

Mermaid's `architecture-beta` diagram type supports real icons via Iconify
icon packs (`service name(logos:microsoft-azure)[Label]`), but **GitHub does
not call `registerIconPacks()`**, so a live `architecture-beta` block with
icon references renders with missing or broken icons on GitHub (confirmed
2026-09-23). The only way to get real icons into a GitHub-rendered README is
to pre-render the diagram locally to a static SVG/PNG and commit that image
-- the same "capture once, commit the artifact" pattern this repository
already uses for screenshots (`scripts/capture_teams_card.py`).

This means an icon-based architecture diagram is **not** a live-editable
code block like the rest of this repository's diagrams. Every future edit
requires re-running the render step and re-committing the image. Say this
trade-off out loud to the user before switching a control over, and keep the
`.mmd` source file committed alongside the image so it can be re-rendered.

## When to use

- Creating a new control's "Infrastructure architecture" section and real
  Azure/Microsoft/GitHub/Python/OpenAI service icons would make the building
  blocks easier to recognize than colored boxes.
- The user asks to add or refresh real icons on an existing control's
  architecture diagram.
- Do **not** use this for "Logical design" diagrams (decision flow, not
  building blocks) -- keep those as plain `flowchart` code blocks per
  `.github/instructions/governance-controls.instructions.md`.

## One-time setup (author-only, per machine)

```zsh
mkdir -p .tooling/mermaid && cd .tooling/mermaid
npm init -y
npm install @mermaid-js/mermaid-cli @iconify-json/logos
cd -
```

`.tooling/` is gitignored. Never add these packages to a control's
`requirements.txt` or any Python dependency file -- this is authoring
tooling, not a control runtime dependency.

If `npm install` cannot download a headless Chrome for Puppeteer (restricted
network), rendering still works by reusing an already-installed system
browser -- see `--chrome` below.

## Steps

1. **List the real building blocks** for the control: the hosted
   agent/service, the platform capability that provides its signal (for
   example a Foundry evaluation, a policy engine, a queue), the developer
   execution context (`demo.py`/`evaluator.py` or equivalent), and any
   external destination (Teams, GitHub Actions). Group nodes that share an
   environment/boundary (for example "Microsoft Foundry project") using
   `architecture-beta`'s `group` construct, matching this repository's
   existing subgraph-grouping convention.

2. **Pick a real icon for each node**, preferring, in order:
   - A user-supplied official asset in `media/icons/` (repo root), when one
     exists for the exact component being drawn -- see "Official custom
     icons" below. Prefer this over a generic lookalike for anything that is
     specifically a Microsoft Foundry building block (an agent, the Foundry
     product itself, a tool), since a generic or vendor logo can be
     semantically wrong even when it renders cleanly. Confirmed the hard way
     on QLT-001 (2026-09-23): the OpenAI logo (`logos:openai-icon`) was
     initially used for a "Hosted agent" node and the classic Azure "A" logo
     (`logos:microsoft-azure`) for a "Microsoft Foundry project" group --
     both render fine but both are wrong, because a hosted agent is not an
     OpenAI product and a Foundry project is not generically "Azure". Check
     whether `media/icons/` already has the real Foundry ribbon logo or an
     "AI agents" icon before reaching for a model-vendor or generic-cloud
     brand mark as a stand-in.
   - `logos:<name>` for anything with an official brand logo and no better
     asset in `media/icons/`. Confirmed present in the installed
     `@iconify-json/logos` set (2026-09-23): `azure`, `azure-icon`,
     `microsoft`, `microsoft-azure`, `microsoft-teams`, `microsoft-power-bi`,
     `github`, `github-actions`, `github-copilot`, `python`, `micro-python`,
     `openai`, `openai-icon`. Check
     `.tooling/mermaid/node_modules/@iconify-json/logos/icons.json` for the
     full, current list before assuming a name exists -- guessing an icon
     name that is not in the set renders as a broken icon.
   - `azure:<name>` for a specific Azure service that has no brand logo of
     its own (Key Vault, Machine Learning workspace, Storage, and similar).
     This resolves from a community Iconify-format icon set fetched by URL
     (see `--iconPacksNamesAndUrls` in the script), not a local install;
     browse available names at
     https://github.com/NakayamaKento/AzureIcons/blob/main/icons.json
     before picking one.
   - No icon (a plain `service name[Label]` with no parenthesized icon) for
     anything with no good match in any of the above. Do not invent an icon
     name.

### Official custom icons (`media/icons/` + `build_icon_pack.py`)

When the user has dropped official brand SVG/PNG assets into `media/icons/`
(repo root) -- for example a real Microsoft Foundry ribbon logo or an
"AI agents" icon downloaded from a Microsoft brand page -- turn them into a
local Iconify pack once with `scripts/build_icon_pack.py`:

```zsh
python3 scripts/build_icon_pack.py \
    --source-dir media/icons \
    --output media/icons/fwf-icons.json \
    --prefix fwf \
    --icons ai-foundry.png ai-agents.svg
```

Each source file becomes one icon named after its filename stem, slugified
(non-alphanumeric characters become `-`) -- `ai-foundry.png` becomes
`fwf:ai-foundry`, not `fwf:foundry`. Run the script without `--icons` to
package every SVG/PNG directly in the directory, or check the "Wrote ... N
icon(s): ..." output line for the exact keys produced. Reference the result
in the `.mmd` source as `fwf:<icon-name>` (see step 3), and pass it to the
renderer with `--local-icon-pack fwf#media/icons/fwf-icons.json` (see step
4) -- **the plain `--icon-packs`/`--extra-icon-urls` flags will not find a
pack that was never installed via npm or fetched by URL.**

A locally-built pack must be served with a CORS header or Mermaid's
in-browser fetch silently fails (the icon renders as a "?" with no error,
confirmed 2026-09-23) -- `render_architecture_diagram.py`'s
`--local-icon-pack` flag already spins up a throwaway CORS-enabled HTTP
server for the duration of the render, so this only matters if rendering by
some other means.

3. **Write the `.mmd` source** in the control's own directory (for example
   `docs/architecture.mmd`), using `architecture-beta` syntax:

   ```
   architecture-beta
       group foundry(logos:microsoft-azure)[Microsoft Foundry project]

       service agent(logos:microsoft-azure)[Hosted agent] in foundry
       service evaldef(azure:machine-learning-studio-workspaces)[Eval definition] in foundry

       service teams(logos:microsoft-teams)[Teams Workflows]
       service runner(logos:python)[demo.py]

       runner:R --> L:agent
       agent:R --> L:evaldef
       runner:B --> T:teams
   ```

   Edge syntax is `<from-service>:<side> --> <side>:<to-service>` where side
   is one of `T`/`B`/`L`/`R`. Keep the node count small and the labels short
   -- this is still a bite-sized diagram, not a full topology map.

4. **Render it** to the control's `media/` folder:

   ```zsh
   python3 scripts/render_architecture_diagram.py \
       --input controls/<category>/<ID>/docs/architecture.mmd \
       --output controls/<category>/<ID>/media/architecture.png
   ```

   If Puppeteer has no downloaded Chrome available (common on a
   network-restricted machine), point at an already-installed browser
   instead of letting it try to download one:

   ```zsh
   python3 scripts/render_architecture_diagram.py \
       --input controls/<category>/<ID>/docs/architecture.mmd \
       --output controls/<category>/<ID>/media/architecture.png \
       --chrome "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
   ```

   If the diagram references a local official-icon pack built in "Official
   custom icons" above, add `--local-icon-pack`:

   ```zsh
   python3 scripts/render_architecture_diagram.py \
       --input controls/<category>/<ID>/docs/architecture.mmd \
       --output controls/<category>/<ID>/media/architecture.png \
       --local-icon-pack "fwf#media/icons/fwf-icons.json" \
       --chrome "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
   ```

5. **Verify the output visually** before committing: open the rendered
   image and confirm every icon shows a real logo/glyph, not a broken-image
   placeholder or a plain colored box where an icon was expected. A silently
   unresolved icon name is the most likely failure mode -- re-check step 2's
   spelling against the actual installed `icons.json` if anything looks
   wrong, rather than assuming the render succeeded because the command
   exited 0.

6. **Embed the image in the README**, replacing the old `classDef`-colored
   `flowchart` under "Infrastructure architecture", following this
   repository's existing `<img>`-with-caption convention:

   ```html
   <p align="center">
       <img src="media/architecture.png" alt="<describe what the diagram shows>" width="900">
   </p>
   ```

   The declared `width` must equal the actual rendered image's pixel width
   (this repository's own tests enforce that) -- resize the PNG first if the
   raw render is wider than is comfortable to read, and update `width` to
   match the resized file, not the original.

7. **Keep the `.mmd` source committed** next to the image and reference it
   from the README or a `docs/IMPLEMENTATION.md` so a future edit only needs
   to change the source and re-run step 4, not rebuild the whole diagram
   from scratch.

## What this does not replace

- "Logical design" diagrams stay plain `flowchart` code blocks -- decision
  flow, not building blocks, and no rendering pipeline is needed for them.
- A control with no interesting real-world services to show (for example, a
  guided exercise with no deployed components) should keep stating
  "Not applicable" rather than forcing an icon diagram where none is
  warranted.
