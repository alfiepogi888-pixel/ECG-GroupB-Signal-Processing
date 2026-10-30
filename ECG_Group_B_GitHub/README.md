# ECG Image Preprocessing — Group B

## Purpose

Process approximately **2,100,000 local ECG images** (PNG/JPG/TIFF/BMP/WEBP) in a streaming file-by-file workflow without loading the whole image set into RAM.

> IMPORTANT: This pipeline performs **image preprocessing (median denoising)** only. It does not extract calibrated 12-lead waveforms, classify arrhythmias, produce clinical interpretations, or claim to follow unverified Group B project requirements. The original `Result_scan_ECG (3).ipynb` supports WFDB `.hea/.dat`, not image-only inputs.

## Requirements

- Python 3.10 or newer; available storage for all output images; Windows or Ubuntu
- Do not upload 2.1 million raw medical images or patient data to GitHub.

## Install

```bash
python -m venv .venv
# Ubuntu: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Test with 100 images

Ubuntu:
```bash
python process_images.py --input "$HOME/Documents/ECG" --output "$HOME/Documents/Result scan ECG" --limit 100
```
Windows PowerShell:
```powershell
python process_images.py --input "D:\ECG" --output "E:\Result scan ECG" --limit 100
```

## Run the full dataset

Remove `--limit 100`:
```bash
python process_images.py --input "/path/to/ECG" --output "/other/path/Result scan ECG" --mode color --median 3
```

### Options

- `--mode color`: preserve colors; `--mode grayscale`: convert to grayscale
- `--median 3`: modest image denoising; `--median 1`: do not denoise
- `--limit 100`: dry run on 100 images before full processing
- `--retry-errors`: retry files previously marked failed
- `--log-every 1000`: print progress

## Outputs and resilience

- `Result scan ECG/processed/`: processed images; original relative subfolder structure preserved
- `Result scan ECG/manifest.sqlite3`: resume/checkpoint database
- `Result scan ECG/errors.csv`: failed images, if any
- Re-running the same command skips successful files based on relative path, source file size/mtime, and existing output. Do not change the processing mode or median kernel while reusing the same output directory; use a fresh output directory when changing settings.
- The pipeline processes files sequentially: memory requirements are primarily driven by the largest single image. Performance is limited by image resolution, disk speed, encoding and CPU. Test a representative sample before committing to a full multi-million-image run.
- There is no ZIP of all outputs by default (too much storage and time).
- The pipeline does not compare image content hashes; avoid modifying input mid-run.

## GitHub upload

Create an empty private GitHub repository, then in this folder run:

```bash
git init
git add README.md process_images.py requirements.txt .gitignore
git commit -m "Add Group B local ECG image preprocessing pipeline"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

If your group has an existing repository, clone it and put these **code files only** in the agreed Group B directory, create a branch and submit a pull request. Do not push patient images, results, IDs or credentials.

## Quality limitation

Median filtering may erase fine ECG grid/signal details. Compare before/after visually and validate on labelled examples; if clinical interpretation or waveform digitization is the goal, the pipeline needs a separate, validated extraction stage.
