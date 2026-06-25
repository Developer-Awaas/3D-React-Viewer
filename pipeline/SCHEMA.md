# Plan schema — the bridge between "reading a plan" and "building 3D"

A plan is JSON. The builder (`builder.py`) turns it into a `.glb`. A trained model
will eventually OUTPUT this same JSON from an image — so this schema is the contract
that connects the two halves of the pipeline.

```jsonc
{
  "units": "metres",
  "ceiling_height": 2.5,
  "rooms": [
    {
      "type": "bedroom",            // bedroom | toilet  (extend with: kitchen, hall, ...)
      "id": "bed1",
      "origin": [x, z],             // room CENTRE in metres
      "size": [width_x, depth_z],
      "walls": {                    // each of back/front/left/right is one of:
        "back":  {"type":"window","center":0,"width":1.2,"sill":0.9,"wh":1.1},
        "left":  {"type":"window", ...},
        "front": {"type":"door","center":1.42,"width":0.95,"state":"closed"},
        "right": "solid"            // "solid" | "shared" (skip, neighbour builds it) | opening object
      },
      "furniture": [               // bedroom: queen_bed, wardrobe
        {"item":"queen_bed","offset":0.15},
        {"item":"wardrobe","size":[1.8,0.5]}
      ],
      "mirror": 1                  // toilet only: +1 or -1 to mirror fixtures
    }
  ]
}
```

Conventions baked into the builder (from DESIGN_RULES.md):
- arc in a plan -> a door; door default state "closed".
- bed = queen (1.53 x 2.03), standard across bedrooms.
- toilet: WC on the outer side, basin toward the shared/centre wall, ONE glass
  partition into the shower, walls aligned with the neighbouring room.

Run: `python builder.py sample_plan.json out.glb`
