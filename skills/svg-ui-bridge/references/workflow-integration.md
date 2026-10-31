# Fitting svg-ui-bridge into superpowers and pstack

svg-ui-bridge is a **design-phase** skill. It never replaces a superpowers stage; it decides what
the design artifact of a UI task is (an SVG + manifest) and what counts as visual evidence.

This file applies only when superpowers or pstack appear among the available skills. Without them,
follow the steps in SKILL.md; there is nothing to install. In sandbox mode, read "live preview" below
as the static page described in `environments.md`.

## superpowers

superpowers' brainstorming classifies every request as **spike**, **bounded** or **architectural**,
and on the architectural path the only skill it hands off to afterwards is writing-plans. So
svg-ui-bridge must run *inside* brainstorming's design step, not after it.

| superpowers stage | what svg-ui-bridge adds |
|---|---|
| brainstorming — classify | If the task changes anything a user sees, say "UI work → SVG design spec" alongside the path. |
| brainstorming — spike | Optional. A throwaway SVG is fine for "could this layout work?"; label it throwaway, don't put it in `design/`. |
| brainstorming — bounded | The "short design in chat" for a UI change = the edited SVG of just the affected component(s), reviewed in the live preview. Approval of what the user sees there is the gate. |
| brainstorming — architectural, "present design" sections | One section per screen: write `design/<screen>.svg`, lint, and let the user review it in the live preview (`svg_preview.py design --serve`, auto-reloads on every edit); iterate **on the SVG** until approved. This replaces superpowers' browser visual companion for UI questions — decline the companion or keep it for non-UI diagrams; the file in `design/` stays the source of truth. |
| brainstorming — write spec | The spec in `docs/superpowers/specs/…-design.md` gets a **Visual design** section linking each `design/*.svg`, its `*.components.md`, and the acceptance thresholds (default overall ≤ 2 %, every component ≤ 10 %). Run `svg_manifest.py` before writing it. |
| writing-plans | **One task per component**, leaves first, using the manifest's build order. Each task lists: component id, bbox, tokens, states, data-note, the file(s) to create, and its acceptance command (`visual_diff.py … --manifest …`, threshold). A final task per screen assembles it and diffs the whole screen. |
| subagent-driven-development / executing-plans | Each subagent receives only its manifest row + `svg_render.py --component <Id>` PNG (+ the `<g>` subtree if needed), never the whole SVG. |
| test-driven-development | Logic/state (enable/disable rules, data binding, events) is tested with normal tests. Pixel fidelity is not a unit test — it is checked by visual_diff. |
| verification-before-completion | A visual claim ("matches the design") requires fresh output from `visual_diff.py` showing PASS, plus `svg_lint.py` passing. Report the numbers and the diff image path. |
| systematic-debugging | For "looks wrong" bugs, the diff heat-map + per-component % is the first piece of evidence. |

### Visual changes after implementation

Any request like "make the card wider / change the colour" goes to the SVG first:
edit SVG → lint → render → user approves → regenerate manifest → update code → visual_diff.
Only pure behaviour changes skip the SVG.

## pstack

pstack's `create-verification-skill` generates a project-local skill (e.g. `.claude/skills/verify/`
or `verify-<app>/`) that launches the real app, drives it like a user and captures evidence.
That is exactly the screenshot source visual_diff needs.

1. Run `/create-verification-skill` once per project. When it interviews the repo, tell it:
   *"Evidence must include a screenshot of each screen in `design/`, at the viewport given by the
   SVG's data-target, cropped to the canvas, saved to `shots/<screen>.png`, then compared with
   `python <skill>/scripts/visual_diff.py design/<screen>.svg shots/<screen>.png --manifest design/<screen>.components.json`."*
2. From then on, the verification step of every UI task = run the project verify skill.
3. When screens are added or the app's launch flow changes, run `/maintain-verification-skill`
   so the screenshot steps still match the `design/` folder.

## Claude Code hooks (optional, deterministic)

Skills are loaded by judgement; a hook always runs. To lint every SVG the agent writes under
`design/`, add to `.claude/settings.json` (project) or `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      { "matcher": "Write|Edit",
        "hooks": [ { "type": "command",
                     "command": "python \"$CLAUDE_PROJECT_DIR/.claude/skills/svg-ui-bridge/scripts/lint_hook.py\"" } ] }
    ]
  }
}
```

`lint_hook.py` reads the hook JSON from stdin, ignores anything that is not `design/**/*.svg`, and
exits with code 2 plus the lint errors on stderr when the SVG breaks a rule, which Claude Code
feeds back to the agent. The path above assumes the skill is committed into the project. If it is
installed in `~/.claude/skills/` or as a plugin, point the command at that copy's `scripts/lint_hook.py`
(when the skill loads, Claude Code shows its base directory; ask the agent for the absolute path).
The plugin deliberately does not register this hook itself, so nothing runs on your machine unless you add it.
