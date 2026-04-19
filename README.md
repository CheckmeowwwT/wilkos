# Wilkos Map Editor

Wilkos Map Editor is a desktop tool for building 2D scenes, drawing pixel art, and putting together short animations in one place.

It is built around two connected workflows. Scene mode is for laying out assets, maps, and compositions. Canvas mode is for direct drawing, layered artwork, frame animation, and export. The point is speed, you can drop art in, edit it, animate it, and ship the result without bouncing between three different programs.

## Why Use It

Wilkos is built for people who want a focused art and layout tool that feels immediate.

- build scenes from imported assets
- draw directly on a layered pixel canvas
- animate frame by frame with live preview
- move between multiple canvas tabs in the same session
- export finished work as PNG, GIF, or spritesheet
- keep assets, scenes, and canvas work inside the same editor

## What Is In The Editor

### Scene Workspace

Scene mode is for composition, placement, and map building.

- drag and drop asset placement
- move, scale, rotate, duplicate, merge, and delete placed assets
- import and delete assets directly from the editor
- scene save data stored as JSON

### Canvas Workspace

Canvas mode is for drawing the actual assets.

- custom canvas sizes with up 2000 percent zoom at 1920x1080
- Variety of useful shortcuts and tools
- freeform lasso select for exact selection
- light tool to quickly place 2D lights and speed up workflow
- export dropdown for PNG, GIF, and spritesheet output

### Drawing Tools

- pencil
- brush
- spray
- bucket
- eraser
- fill
- line
- gizmo rotate
- square and circle tools
- lasso select
- square select
- move and resize
- mirror and flip 
- transparency-aware drawing

### Animation And Export

Canvas mode is built to handle sprite and loop workflows cleanly.

- preview animation while you work
- control frame order and playback speed
- export a single frame as PNG
- export a full animation as GIF
- export frames as a spritesheet

Exports are written to:

```text
assets/exported canvasses/
```

Scene data is stored in:

```text
assets/maps/scenes/
assets/maps/scenes_project.json
```

## Installation

Python 3.11 or newer is recommended.

Install dependencies:

```bash
pip install -e .
```

## Run

From inside the `wilkos` folder:

```bash
python3 wilkos.py
```

Or, after installing:

```bash
wilkos
```

## Status

Ongoing development. Next to add a 3D mode and more game engine specific tools.
