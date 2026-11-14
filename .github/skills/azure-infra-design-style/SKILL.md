---
name: azure-infra-design-style
description: "House visual style for every Forged with Foundry infrastructure diagram (a control's 'Demo infrastructure setup (simplified)' image, shared infra diagrams, slides): a white canvas, a dashed rounded Azure boundary titled with the Azure logo and a caption set into the border, a nested dashed Microsoft Foundry boundary under a blue-outlined hero header, light-gray rounded cards with a centered official icon, bold title and short description, thin gray caller-to-callee arrows, and people or external tools as gray pills outside the boundary. Use whenever you create or refresh an infrastructure or architecture diagram; render it with the draw.io pipeline from mermaid-infra-diagram."
license: MIT
user-invocable: true
metadata:
  authors: "Douwe van de Ruit"
  spec_version: "1.0"
---

# Azure infrastructure design style

## Overview

Every infrastructure diagram in this repository uses one visual style,
modeled on Microsoft's solution-accelerator architecture diagrams (adopted
2026-11-14). It shows Azure as a dashed boundary, Microsoft Foundry as a
nested boundary with a highlighted header, and each resource as a calm gray
card with its official icon. The result reads like Microsoft's own material
and lets a reader match each card to what they will find in Azure Portal.

This skill owns **how a diagram looks**. The
[`mermaid-infra-diagram`](../../../.claude/skills/mermaid-infra-diagram/SKILL.md)
skill still owns **how it is built and rendered**: finding icons in
`media/icons/Azure_Public_Service_Icons/icon-index.jsonl`, writing the
`.drawio` source with `icon:` placeholders, rendering with
`scripts/render_drawio_diagram.py`, routing edges, and verifying the
result. Where the two disagree on appearance (colors, boundary fills, legend,
edge colors, icon tiers), this skill wins.

Reference implementation, AUT-004 drawn in this style:

- [reference.png](reference.png): the rendered result;
- [reference.drawio](reference.drawio): the source;
- [reference_diagram.py](reference_diagram.py): the generator, with
  reusable helpers for every element below.

## When to use

- Creating or refreshing a control's **Demo infrastructure setup
  (simplified)** image.
- Any other architecture picture for this repository: the shared `infra/`
  README, a slide, a LinkedIn cover.
- Not for **Logical design** diagrams. Those stay Mermaid flowcharts with
  the brand `classDef` palette, because they show decision branches, not
  resources.

## The style, element by element

| Element | Appearance | draw.io style (key values) |
|---|---|---|
| Canvas | White, no grid, no page border | `background="#FFFFFF"` |
| Font | Segoe UI, falling back to a neutral sans-serif; text `#242424` | `fontFamily=Segoe UI,Helvetica Neue,Helvetica,Arial,sans-serif;fontColor=#242424` |
| Azure title | Azure logo (30px) + bold **Azure** (18px), sitting above the outer boundary, left of center | `other/10018-icon-service-Azure-A.svg` |
| Outer boundary | Dashed, rounded, unfilled, dark gray | `rounded=1;absoluteArcSize=1;arcSize=18;dashed=1;dashPattern=5 4;fillColor=none;strokeColor=#3B3B3B;strokeWidth=1.5` |
| Boundary caption | One plain sentence centered on the top border, on a white text box that interrupts the dashed line | `text;fillColor=#FFFFFF;strokeColor=none;fontSize=13` |
| Foundry boundary | Same dashed style, nested inside the outer boundary | as outer boundary |
| Foundry hero header | White box straddling the Foundry boundary's top edge, solid blue outline, Foundry logo (34px) left, bold **Microsoft Foundry** | `fillColor=#FFFFFF;strokeColor=#0F6CBD;strokeWidth=2;arcSize=4` (absolute); icon `ai + machine learning/035746832-icon-service-AI-Foundry.svg` |
| Resource card | Light gray rounded card, official icon (40px) centered at the top, bold title (14px), one or two description lines (11px) | `rounded=1;absoluteArcSize=1;arcSize=12;fillColor=#F3F2F1;strokeColor=#D6D6D6;strokeWidth=1.5;verticalAlign=top;spacingTop=60;fontSize=14` |
| Person or external tool | Gray pill outside every boundary, icon (30px) left, bold label | `rounded=1;arcSize=50;fillColor=#F3F2F1;strokeColor=none;align=left;spacingLeft=52;fontSize=13` |
| Bottom caption | One italic sentence under the pills, `#424242`, 12px | `text;fillColor=none;align=left` |
| Arrow | Thin gray, orthogonal, small filled head, pointing from caller to callee | `edgeStyle=orthogonalEdgeStyle;rounded=0;strokeColor=#616161;strokeWidth=1.25;endArrow=block;endFill=1;endSize=5` |

### Card content

- **Title:** what the resource *is for* in this control ("Stop switch",
  "Audit log", "Support chat + ACS"), not only its product name.
- **Description:** the Azure product and SKU on line one ("App
  Configuration · Free"), the role in the control on line two ("one
  feature flag per action"). At most two short lines; if it needs more, it
  belongs in the README prose.
- **Icon:** the most specific official icon from the index. Never use a
  generic shape when an official icon exists.
- Cards in one column or row share the same size. Use 210-220 x 130-140px
  and 30px gutters.

### Boundaries tell scope

- **Outer boundary = Azure.** Its caption states the scope in one sentence,
  for example "Resource group (shared) · AUT-004 resources are tagged
  control-id=AUT-004 and removed by cleanup". This replaces a legend.
- **Nested Foundry boundary** groups everything that lives in the Foundry
  account: agents, models, Foundry IQ, projects.
- Add another nested dashed boundary only for a real scope a reader will
  meet in Azure Portal (for example a Container Apps environment). Never
  nest more than two levels.
- Things the control uses but does not own (a shared model deployment, for
  example) stay inside the boundary where they live, and their card says
  "shared · not removed by cleanup".
- People, Entra ID sign-in, GitHub, Docker, Teams and other external tools
  go **below** the outer boundary as pills, with one italic caption line
  explaining their role.

### Arrows

- Every arrow means the same thing: the caller calls the service the arrow
  points to. Use a double head only for a genuinely two-way exchange.
- No labels by default; the card descriptions carry the meaning. If an arrow
  needs a label, use a short verb phrase and the two-cell label pattern
  from `mermaid-infra-diagram`, with the backdrop matching the white
  canvas.
- Route with pinned `exitX/exitY/entryX/entryY` so arrows never cross cards.
- Passive resources (a managed identity, a registry) may have no arrows.

### What to leave out

- No legend, color coding, tinted boundary fills or colored arrows; scope
  is told by boundaries and captions.
- No planned or not-deployed components, deployment tooling (`az`, `azd`)
  or the author's workstation.
- No step numbers on arrows.
- No subscription IDs, tenant names or real people; use role names.

## Workflow

1. Decide the building blocks with steps 1-4 of the draw.io workflow in
   `mermaid-infra-diagram`: show the control's mechanism and what it
   deploys, nothing else.
2. Copy [reference_diagram.py](reference_diagram.py) into the control's
   `docs/` folder as the generator, or edit
   [reference.drawio](reference.drawio) directly. Adjust the `I` icon path
   prefix to be relative to the new `.drawio` file.
3. Lay out: Azure title, outer boundary with caption, resource cards on a
   grid, the Foundry boundary with its hero header on the right, pills and
   caption below.
4. Render:

   ```bash
   .venv/bin/python scripts/render_drawio_diagram.py --input <control>/docs/architecture.drawio --output <control>/media/architecture.png
   sips -Z 1400 <control>/media/architecture.png
   ```

5. Verify by viewing the image:
   - text is sans-serif;
   - every caption sits on its border;
   - the hero header straddles the Foundry boundary;
   - no arrow crosses a card;
   - all icons in the same role are the same size.
6. Embed in the README's **Demo infrastructure setup (simplified)** section
   with an `<img src="media/architecture.png" ... width="<real width>">`
   tag. The README structure test checks that the declared width matches the
   PNG. The alt text lists boundaries and cards in reading order. Commit the
   `.drawio` source next to the image.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Text renders in a serif font | The headless browser has no Segoe UI; keep the full fallback stack in `fontFamily`. |
| Caption does not interrupt the dashed line | Its text cell needs `fillColor=#FFFFFF` and must be vertically centered on the border's `y`. |
| Hero header hidden behind the boundary | Add the hero cells after the boundary cell in the XML; later cells render on top. |
| Icon shows as a broken image | The `icon:` path must be relative to the `.drawio` file; the renderer embeds SVG only. |
