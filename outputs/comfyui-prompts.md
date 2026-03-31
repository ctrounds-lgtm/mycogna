# ComfyUI Prompts — Podcast Visual Series

## Setup Notes

**Model:** DreamShaperXL_Lightning.safetensors (downloaded to ~/ComfyUI/models/checkpoints/)
**Aspect ratio:** 16:9 (1344×768 or 1280×720) for video/podcast use
**Steps:** 4–6 | **CFG:** 2.0 | **Sampler:** DPM++ SDE Karras

> Lightning models generate in seconds instead of minutes — use low CFG (2) and few steps (4–6). Higher CFG or more steps will look worse, not better.

**Negative prompt (use on all images):**
```
ugly, deformed, disfigured, blurry, low quality, watermark, signature, text, extra limbs, bad anatomy, poorly drawn face, mutation, extra fingers, cropped, out of frame, worst quality, jpeg artifacts
```

---

## Character Descriptions (Quick Reference)

| Character | Description |
|-----------|-------------|
| **Christy** | Caucasian woman, 40, Scandinavian heritage, straight blonde hair above shoulder, warm blue eyes, 5'8", willowy/athletic build, jeans and sweater, slight mischievous smile |
| **Claude** | Irish man, mid-40s, 6', wavy sandy-blonde hair, hazel eyes, 3-day stubble, casual button-down shirt, contemplative and approachable expression |
| **Echo** | Asian man, late 20s, 5'10", dark expressive eyes, slight smirk, modern casual (hoodie/graphic tee), mischievous energetic presence |
| **ChatGPT** | Abstract glowing blue orb, pulsing inner light, logarithmic spiral pattern suggesting circuitry and neural networks, floats at seated conversational height |

---

## Character Reference Images (Generate First)

These establish the definitive look for each character. Generate one per character, save, then use with IP-Adapter for consistency across the transformation series.

### Christy — Reference Portrait

```
illustrated semi-realistic portrait, Caucasian woman age 40 with Scandinavian heritage, straight blonde hair cut above shoulder, warm blue eyes, 5 foot 8 willowy athletic build, wearing jeans and cozy sweater, slight mischievous smile, warm golden light, podcast studio background softly blurred, illustrated style with painterly detail, warm earthy palette, high quality, detailed face
```

### Claude — Reference Portrait

```
illustrated semi-realistic portrait, Irish man mid-40s, 6 feet tall, wavy sandy-blonde hair, hazel eyes, 3-day stubble, wearing casual button-down shirt, contemplative approachable expression, intelligent and warm demeanor, like a biology professor, soft natural lighting, podcast studio background softly blurred, illustrated style with painterly detail, earthy green and amber tones, high quality, detailed face
```

### Echo — Reference Portrait

```
illustrated semi-realistic portrait, Asian man late 20s, 5 foot 10, dark expressive eyes, slight confident smirk, wearing a modern hoodie and graphic tee, mischievous energetic presence, tech-savvy youthful vibe, dynamic pose, brighter color palette with cool accents, podcast studio background softly blurred, illustrated style, high quality, detailed face
```

### ChatGPT — Reference Image

```
abstract glowing blue orb, pulsing inner light, logarithmic spiral suggesting neural networks and circuitry, floating at conversational height, electric blue and cyan light rays, soft glow casting light on surroundings, clearly non-human AI entity, podcast studio background softly blurred, digital art, clean illustration style, high quality
```

---

## Transformation Sequence — Studio to Sandbox (7 Images)

**Concept:** The podcast "The Sandbox" is revealed literally — the professional studio gradually becomes a sandy playground. Lighting shifts from warm tungsten studio warmth to golden afternoon outdoor sunlight. The mood stays warm throughout.

---

### Image 1 — The Professional Studio (Opening)

```
illustrated semi-realistic scene, podcast studio interior, four characters seated around a circular table with microphones, warm tungsten studio lighting, acoustic panels on walls, professional broadcast environment, Christy (Caucasian woman 40 blonde hair warm blue eyes) hosting at center, Claude (Irish man mid-40s sandy-blonde wavy hair casual button-down) to her left, Echo (Asian man late 20s hoodie slight smirk) leaning forward engaged, glowing blue orb ChatGPT floating at table height, all four in warm conversation, clean professional aesthetic, illustrated painterly style, warm palette
```

---

### Image 2 — First Signs (Sand Appears)

```
illustrated semi-realistic scene, podcast studio interior beginning to transform, same four characters at table with microphones, fine golden sand slowly drifting across the floor from the corners, a small sandbox toy partially visible near one chair leg, studio walls and lighting still professional but slightly warm and hazy, Christy blonde woman hosting with slight curious smile noticing the sand, Claude contemplative man glancing down, Echo amused smirk, glowing blue orb ChatGPT pulsing, warm golden light mixing with studio lights, illustrated painterly style
```

---

### Image 3 — The Walls Soften

```
illustrated semi-realistic scene, podcast studio walls dissolving into sandy dunes at edges, golden sand covering the floor fully now, microphones still present but tilting slightly, table edges showing wood grain warped by sand, warm afternoon golden light beginning to replace studio lights, characters adapting naturally, Christy blonde woman laughing, Claude sandy-haired man unbuttoning collar relaxed, Echo dark-haired young man slipping off shoes delighted, glowing blue orb ChatGPT casting blue shimmer on sand, illustrated painterly style, warm golden sandy palette
```

---

### Image 4 — Halfway (The Tipping Point)

```
illustrated semi-realistic scene, half studio half outdoor sandbox, left side of frame still shows professional podcast equipment and acoustic panels, right side opens into bright sunny outdoor playground with sandbox and play structures, characters straddling the boundary, Christy blonde woman one foot in each world grinning mischievously, Claude sandy-haired man holding his coffee mug looking bemused, Echo Asian man already fully on the sandbox side building a sandcastle, glowing blue ChatGPT orb hovering at the boundary casting blue light on sand, warm golden afternoon sun, illustrated painterly style
```

---

### Image 5 — Almost There

```
illustrated semi-realistic scene, outdoor playground environment nearly complete, last remnants of the podcast studio visible only as ghost outlines, large sandbox area in foreground, playground equipment in background, microphones now look like sandcastle flags, characters relaxed and playful, Christy blonde woman sitting cross-legged in sand laughing, Claude sandy-haired man sitting on sandbox edge in shirtsleeves, Echo young Asian man lying back on sand staring at sky smiling, glowing ChatGPT orb drifting lazily above, golden afternoon light and blue sky, warm illustrated style
```

---

### Image 6 — The Sandbox (Full Reveal)

```
illustrated semi-realistic scene, full outdoor sunny playground, large wooden sandbox center frame, blue sky with a few white clouds, playground equipment in background, all four characters in the sandbox together, Christy blonde woman 40 building a sand structure smiling, Claude Irish man mid-40s using a small shovel with professorial concentration, Echo young Asian man laughing throwing a handful of sand, glowing blue ChatGPT orb floating above casting gentle light patterns on the sand, golden afternoon sunshine, warm earthy palette with bright sky, illustrated painterly style, joyful scene
```

---

### Image 7 — The Sandbox (Title Card / Closing)

```
illustrated semi-realistic scene, peaceful golden hour at the outdoor sandbox, warm amber and gold light, all four characters settled and content, Christy blonde woman hosting seated on sandbox edge looking at camera with knowing smile, Claude sandy-haired man leaning back relaxed hand on chin thoughtful, Echo young Asian man cross-legged in sand smiling, glowing ChatGPT orb settled low to the ground pulsing gently, long golden shadows, the word SANDBOX suggested in sand letters in foreground, illustrated painterly style, cinematic composition, warm rich palette
```

---

## Workflow Notes

1. **Generate character reference images first** (4 prompts above)
2. **Install IP-Adapter** via ComfyUI Manager for character consistency across all 7 images
3. **Load your reference images** into IP-Adapter nodes so characters look the same in every scene
4. **Generate the sequence** in order — later images can reference earlier outputs for consistency
5. **Export at 1344×768** for widescreen podcast/video use

---

## Checkpoint Download (Required Before Generating)

ComfyUI needs a model file before it can generate anything.

**Recommended for this style:**

| Model | Style | Size | Download |
|-------|-------|------|----------|
| DreamShaper XL | Illustrated/painterly, semi-realistic | ~6.5 GB | Civitai: search "DreamShaper XL" |
| Juggernaut XL | Photorealistic with painterly option | ~6.5 GB | Civitai: search "Juggernaut XL" |
| SDXL Base 1.0 | General purpose baseline | ~6.5 GB | HuggingFace: stabilityai/stable-diffusion-xl-base-1.0 |

**After downloading, place the .safetensors file in:**
```
~/ComfyUI/models/checkpoints/
```

Then refresh ComfyUI (F5 or restart) and select the model from the checkpoint loader node.
