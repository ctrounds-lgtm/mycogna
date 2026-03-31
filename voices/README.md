# Voice Conversion — Setup & Patch Notes

This folder contains reference audio clips used by `scripts/convert_voice.py`
for local voice conversion via Seed-VC.

---

## Reference Clips

| File | Character | Notes |
|------|-----------|-------|
| `christy.wav` | Christy | Neutral reference text |
| `chatgpt.wav` | ChatGPT | Neutral reference text |
| `claude.wav` | Claude | Accent-rich text (Australian vowels) |
| `echo.wav` | Echo | Neutral reference text |

**Format:** 16-bit PCM WAV, 22050 Hz mono — matches Seed-VC's native rate exactly.

To regenerate: `python3 scripts/generate_reference_voices.py`
(Existing files are skipped unless deleted first.)

---

## Seed-VC Patches

Seed-VC is cloned into `vendor/seed-vc/` on first run. If you ever delete that
folder and re-clone, two files need to be patched before conversions will work.

### Patch 1 — Fix `huggingface_hub` compatibility
**File:** `vendor/seed-vc/modules/bigvgan/bigvgan.py`

The `_from_pretrained` method signature uses required keyword arguments that
newer versions of `huggingface_hub` no longer pass. Make them optional:

**Find:**
```python
proxies: Optional[Dict],
resume_download: bool,
```

**Replace with:**
```python
proxies: Optional[Dict] = None,
resume_download: bool = False,
```

---

### Patch 2 — Fix `torchaudio.save` (requires missing `torchcodec`)
**File:** `vendor/seed-vc/inference.py`

New versions of `torchaudio` removed their built-in save backend and require
`torchcodec`, which has no Mac ARM wheel. We replace the save call with
`soundfile`, which is already installed.

**Add to imports** (after `import numpy as np`):
```python
import soundfile as sf
```

**Find** (near the bottom of the `main` function):
```python
torchaudio.save(os.path.join(args.output, f"vc_{source_name}_{target_name}_{length_adjust}_{diffusion_steps}_{inference_cfg_rate}.wav"), vc_wave.cpu(), sr)
```

**Replace with:**
```python
out_path = os.path.join(args.output, f"vc_{source_name}_{target_name}_{length_adjust}_{diffusion_steps}_{inference_cfg_rate}.wav")
audio_out = vc_wave.cpu().squeeze().numpy()
peak = np.abs(audio_out).max()
if peak > 0:
    audio_out = audio_out / peak * 0.7079  # normalize to -3dB headroom
sf.write(out_path, audio_out, sr, subtype='PCM_16')
```

**Why:** Seed-VC's vocoder output can exceed ±1.0 (we observed ±1.2), causing
hard digital clipping and a metallic buzz. Normalizing to −3dB eliminates this.
Using `soundfile` with `subtype='PCM_16'` also ensures consistent 16-bit depth
matching the reference clips and mic recordings throughout the pipeline.

---

## Why These Audio Settings Matter

The metallic buzz in early conversions had three causes, all now fixed:

| Problem | Cause | Fix |
|---------|-------|-----|
| Resampling artifacts | Reference clips were 44100 Hz MP3; Seed-VC runs at 22050 Hz | Generate references as WAV at 22050 Hz (`pcm_22050`) |
| MP3 compression artifacts | Lossy reference clips fed into the model | Use lossless PCM WAV for all reference clips |
| Digital clipping / buzz | Model output exceeded ±1.0 before saving | Normalize output to −3dB (0.7079 linear) before writing |

---

## Quick Reinstall Checklist

If `vendor/seed-vc/` is deleted and recreated:

1. `python3 scripts/convert_voice.py` — triggers auto-download of Seed-VC
2. Apply **Patch 1** to `modules/bigvgan/bigvgan.py`
3. Apply **Patch 2** to `inference.py`
4. Run a test conversion to confirm it works

Reference clips in `voices/` do **not** need to be regenerated — they're
independent of the Seed-VC installation.
