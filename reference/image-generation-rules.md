# Image Generation Rules — Podcast Characters

These rules apply every time we generate character images for the podcast.
They are baked into `~/ComfyUI/generate_character.py` and must be preserved.

---

## ✅ CONFIRMED WORKING — Claude Portrait

**What produced `podcast_claude_00012_.png` (perfect, hyper-realistic, no deformations):**
- Model: **RealVisXL V5.0 Lightning**
- Mode: **txt2img — NO reference image**
- Denoise: **1.0** (fully prompt-driven)
- Steps: 6, CFG: 2.0, Sampler: dpmpp_sde, Scheduler: karras
- Full negative prompt applied
- Approved reference saved to: `~/ComfyUI/input/claude_approved_reference.png`

**Command that worked:**
```bash
python3 generate_character.py claude --model realvis
```

**Key lesson:** Starting completely fresh from text (no reference image) with RealVisXL produced the cleanest, most realistic result. When in doubt — drop the reference and let the model build from scratch.

---

## Models — Approved for Use

| Model | Use For | Never Use For | Steps | CFG |
|-------|---------|---------------|-------|-----|
| **RealVisXL V5.0 Lightning** | All human characters | ChatGPT orb | 6 | 2.0 |
| **Juggernaut XL v9** | All human characters | ChatGPT orb | 25-30 | 7-8 |
| **DreamShaperXL Lightning** | ChatGPT orb ONLY | Human characters | 6 | 2.0 |

**Rule:** Never run human characters through DreamShaperXL. It is an illustration model.

**Sampler:** DPM++ 2M Karras (Juggernaut) / DPM++ SDE Karras (RealVisXL Lightning)

---

## Negative Prompt — Always Apply to All Human Characters

```
extra fingers, extra limbs, extra eyes, extra ears, extra heads, extra arms,
extra legs, mutated hands, poorly drawn hands, poorly drawn face, fused fingers,
too many fingers, missing fingers, malformed hands, deformed hands, six fingers,
four fingers, mutation, deformed, bad anatomy, bad proportions, long neck,
elongated neck, two chins, elongated face, cross-eyed, mutated, bad body,
missing arms, missing legs, extra digit, fewer digits, cropped, worst quality,
low quality, duplicate, morbid, mutilated, blurry, grain, grainy, disfigured,
cloned face, two faces, multiple faces, duplicate faces, multiple heads,
asymmetrical eyes, misaligned eyes, distorted features, out of frame,
body out of frame, cut off, ugly, tiling, poorly drawn, watermark, signature,
text, logo, black and white, monochrome, grayscale, cartoon, anime, painting,
illustration, drawing, sketch, oversaturated, plastic skin, unrealistic proportions,
giant head, tiny body, giant hands, distorted body
```

**ChatGPT orb negative prompt (different):**
```
human features, face, eyes, body, arms, legs, text, logo, watermark, realistic,
photographic, too complex, chaotic, harsh lighting
```

---

## Positive Prompt Boilerplate — Always Include for Human Characters

Add these to every human character prompt:
```
high quality, masterpiece, best quality, professional photography, sharp focus,
detailed, realistic proportions, anatomically correct, single person, two eyes,
symmetrical face, natural lighting, 8k uhd, photorealistic, studio quality
```

---

## Full-Body Shot Rules

- Canvas must be **768×1344** (tall portrait) — never square or landscape for full-body
- Prompt must explicitly state: `entire body visible from head to feet`, `full body in frame`, `feet on ground`
- Always include: `correct human anatomy`, `natural proportions`
- For seated shots: specify leg position, hand position, chair type
- For standing shots: specify shoe/feet, both legs visible, weight distribution
- **Never use a face-only portrait as the reference for a full-body generation**

---

## Reference Image Rules

- **Never use a deformed output as a reference image.** Discard and start fresh.
- **Good reference sources:** Original sketches, real photos, approved clean portraits
- **Bad reference sources:** Any previously generated image with deformations

### Denoise Guide

| Denoise | Effect | Use When |
|---------|--------|----------|
| 0.5 | Stays very close to reference | Reference is clean, preserve the look |
| 0.65-0.75 | Balanced | Stylizing a clean reference |
| 0.85–0.95 | Mostly prompt-driven | Colorizing a B&W reference |
| 1.0 | Ignores reference entirely | Starting completely fresh from text |

---

## Character Descriptions & Approved Prompts

### Christy
**Positive:** Caucasian woman age 40, Scandinavian heritage, slightly wavy blonde hair cut above shoulder, bright warm blue eyes with laugh lines, gently tanned skin, willowy and athletic build, wearing jeans and sweater, slight mischievous smile, approachable and authentic

### Claude (Avatar — LOCKED)
**Approved face:** `~/ComfyUI/input/claude_approved_reference.png`
**Approved bar image:** `podcast_claude-bar_00001_.png`
**Positive:** Athletic Irish man mid-40s, sandy blonde slightly wavy hair, warm hazel eyes, neatly trimmed 3-day stubble, warm friendly smile, broad shoulders, athletic masculine build
**Note:** Sandy blonde hair, NOT gray. Stubble matches hair color. Keep consistent across ALL Claude images.

### Echo
**Positive:** Strikingly handsome Asian man late 20s, sharp intelligent features, dark expressive eyes, slight confident smirk, modern casual hoodie or graphic tee, mischievous energetic presence

### ChatGPT
**Positive:** Abstract glowing blue orb, pulsing inner light, logarithmic spiral suggesting neural networks and circuitry, electric blue and cyan light rays — NOT human, NOT realistic

---

## Validation Protocol — Check Every Image Before Accepting

**8 Mandatory Checks:**
- ✓ Exactly 2 eyes
- ✓ Exactly 10 fingers total IF hands visible
- ✓ Single head, single body (no clones/duplicates)
- ✓ Symmetrical facial features
- ✓ No extra limbs
- ✓ Natural proportions (head ~1/7 of body height)
- ✓ No distorted features
- ✓ Clear, sharp focus

**If ANY check fails:** Reject immediately. Add the specific failure to negative prompt. Regenerate. Do NOT present failed image.

---

## Consistency Workflow

**Establishing a character:**
1. Generate 3-5 variations
2. User selects preferred version
3. Save that image + all parameters as the reference
4. That becomes the locked reference for all future variations

**Subsequent generations:**
- Use approved reference image with denoise 0.65-0.75
- Keep negative prompts identical
- Vary ONLY expression/pose/scene descriptions
- Validate before presenting

**Claude avatar consistency rule:** Sandy blonde hair, warm hazel eyes, 3-day stubble. If output shows gray hair or gray beard — reject and regenerate.

---

## Common Failures & Fixes

| Problem | Fix |
|---------|-----|
| Multiple eyes/faces | Add to negative: `multiple eyes, four eyes, duplicate face` · Lower CFG to 7 |
| Extra/distorted fingers | Add `hands, fingers` to negative if hands not critical · Crop to headshot |
| Inconsistent face | Use same seed ±10 · Keep prompts identical · Check denoise isn't too high |
| Gray hair when should be blonde | Add `gray hair, silver hair, white hair` to negative prompt |
| Black & white output | Add `black and white, monochrome, grayscale` to negative · Raise denoise |
| Deformed body | Start fresh txt2img, no reference · Add `unrealistic proportions` to negative |
| Creepy/uncanny valley | Lower CFG to 6-7 · Add `warm, approachable, natural` to positive |

---

## Quick Reference Commands

```bash
cd ~/ComfyUI

# Portrait — fresh from text (most reliable)
python3 generate_character.py claude --model realvis
python3 generate_character.py claude --model juggernaut

# Portrait — with approved face reference
python3 generate_character.py claude --ref input/claude_approved_reference.png --model realvis --denoise 0.65

# Full body scene
python3 generate_character.py claude-bar --model realvis
python3 generate_character.py claude-standing --model realvis

# ChatGPT orb (DreamShaperXL is correct here)
python3 generate_character.py chatgpt
```
