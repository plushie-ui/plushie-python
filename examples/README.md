# Plushie Examples

Example apps demonstrating Plushie's features from minimal to complex.
Run any example with:

```sh
python -m plushie run examples.<module>:<Class>
```

## Examples

### Counter

**File:** `counter.py`

Minimal Elm-architecture example. Two buttons increment and decrement a count.
Start here to understand `init`, `update`, and `view`.

```sh
python -m plushie run examples.counter:Counter
```

### Todo

**File:** `todo.py`

Todo list with text input, checkboxes, filtering (all/active/done), and
delete. Demonstrates `text_input` with `on_submit`, `checkbox` with dynamic
IDs, `scrollable` layout, and pattern matching on scoped event IDs.

```sh
python -m plushie run examples.todo:TodoApp
```

### Notes

**File:** `notes.py`

Notes app combining all five state helpers: `State` (change tracking),
`UndoStack` (undo/redo for title and body editing), `Selection`
(multi-select in list view), `Route` (stack-based `/list` and `/edit`
navigation), and `query()` (search across note fields). Shows how
to compose multiple state helpers in a single model.

```sh
python -m plushie run examples.notes:Notes
```

### Clock

**File:** `clock.py`

Displays the current local time, updated every second. Demonstrates
`Subscription.every(1000, "tick")` for timer-based subscriptions.

```sh
python -m plushie run examples.clock:Clock
```

### Shortcuts

**File:** `shortcuts.py`

Logs keyboard events to a scrollable list. Demonstrates
`Subscription.on_key_press("keys")` for global keyboard handling. Shows
modifier key detection (Ctrl, Alt, Shift, Super) and the `KeyPress` event.

```sh
python -m plushie run examples.shortcuts:Shortcuts
```

### AsyncFetch

**File:** `async_fetch.py`

Button that triggers simulated background work. Demonstrates
`Command.task` for running expensive operations off the main update
loop. Shows the `(model, command)` return form from `update` and how
`AsyncResult` events deliver the result.

```sh
python -m plushie run examples.async_fetch:FetchApp
```

### ColorPicker

**Files:** `color_picker.py`, `widgets/color_picker_widget.py`

HSV color picker using a custom canvas widget. A hue ring surrounds a
saturation/value square with drag interaction. The canvas drawing is
extracted into a reusable widget module (`widgets/color_picker_widget.py`),
showing the widget composition pattern. Demonstrates canvas layers,
path commands, linear gradients with alpha, and coordinate-based canvas
events (press/move/release for continuous drag).

```sh
python -m plushie run examples.color_picker:ColorPicker
```

### Catalog

**File:** `catalog.py`

Comprehensive widget catalog exercising every widget type across four
tabbed sections:

- **Layout:** column, row, container, scrollable, stack, grid, pin, float,
  responsive, keyed_column, themer, space
- **Input:** button, text_input, checkbox, toggler, radio, slider,
  vertical_slider, pick_list, combo_box, text_editor
- **Display:** text, rule, progress_bar, tooltip, image, svg, markdown,
  rich_text, canvas
- **Composite:** mouse_area, sensor, pane_grid, table, simulated tabs,
  modal, collapsible panel

Use this as a reference for widget props and event patterns.

```sh
python -m plushie run examples.catalog:Catalog
```

### RatePlushie

**Files:** `rate_plushie.py`, `widgets/star_rating.py`, `widgets/theme_toggle.py`

App rating page with custom canvas-drawn widgets composed into a styled UI.
Features a 5-star rating built from path-drawn star geometry and an animated
theme toggle (a smiley face that rotates upside down when "Dark humor"
is enabled). The entire page theme flips at the animation midpoint.

Demonstrates: custom canvas widgets as reusable modules, the interactive
shape wrapper, canvas transforms for rotation, timer-based animation via
subscriptions, container styling with border and padding, theme-aware
rendering, keyboard interaction (arrow keys adjust rating).

```sh
python -m plushie run examples.rate_plushie:RatePlushie
```
