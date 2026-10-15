# Optic Radiation Tracking and Retinotopic Segmentation

A reproducible pipeline for tractography and eccentricity-based segmentation of the human optic radiation using population receptive field (pRF) mapping.

---

## Pipeline

1. **Preprocessing** — resample FreeSurfer volumes and pRF maps to diffusion/T1 space
2. **Fiber tracking** — seed-based (LGN → V1) or whole-brain tractogram (MRtrix3 iFOD2 or DIPY); alternatively accept a pre-computed tractogram
3. **Segmentation** — isolate optic radiation fibers via `tckedit` with ordered LGN ↔ V1 ROI constraints
4. **Classification** — assign fibers to eccentricity bands defined by arbitrary `lo-hi` intervals
5. **Export** — per-tract `.tck` files, classification struct, fiber counts, QC images, `product.json`

The app is designed for **Brainlife.io** and can run inside a **Singularity/Apptainer** container or **locally** via the `main_cli.sh` wrapper script.

---

## Features

- **Three tracking modes**: seed-based from LGN (default), whole-brain ACT, or pre-computed tractogram
- **Auto-generated ROIs**: LGN extracted from FreeSurfer thalamic nuclei segmentation (labels 8109/8209); V1 extracted from `varea == 1` masked by hemisphere ribbon — no explicit ROI files required
- **Auto thalamic nuclei segmentation** via `segmentThalamicNuclei.sh` (FreeSurfer 7.1.0) if absent
- **Auto 5TT** via `5ttgen fsl` (MRtrix3) if absent (tracking mode only)
- Arbitrary eccentricity bands via `ecc_bins` string (e.g. `"0-3,3-7,15-30,30-90"`)
- Hemisphere-specific segmentation (left / right)
- Fully configurable via `config.json` or CLI (`main_cli.sh`)
- Outputs Brainlife-compatible `wmc` datatype + per-tract `tcks/`
- MAD-based iterative fiber cleaning

---

## Author

Gabriele Amorosino — [gabriele.amorosino@utexas.edu](mailto:gabriele.amorosino@utexas.edu)

---

## Citation

If you use this app in your research, please cite:

### Primary work

Amorosino, G., Caron, B., Kwon, J., Carrasco, M., Reid, R. C., Lenglet, C., ... & Pestilli, F. (2026).
*A retinotopic wiring principle of the human brain.*
bioRxiv, 2026-04.

### Software dependencies

**MRtrix3** — Tournier et al. (2019). *MRtrix3: A fast, flexible and open software framework for medical image processing and visualisation.* NeuroImage, 202, 116137.

**DIPY** — Garyfallidis et al. (2014). *Dipy, a library for the analysis of diffusion MRI data.* Frontiers in Neuroinformatics, 8, 8.

**Brainlife.io** — Hayashi et al. (2024). *Brainlife.io: a decentralized platform for reproducible neuroscience.* Nature Methods. [https://doi.org/10.1038/s41592-024-02237-2](https://doi.org/10.1038/s41592-024-02237-2)

---

## Inputs

All parameters are provided via `config.json` (or via CLI flags in `main_cli.sh`).

### Minimum inputs — tractogram mode

| Field         | Description                          |
|---------------|--------------------------------------|
| `tractogram`  | Pre-computed whole-brain `.tck` file |
| `t1`          | T1-weighted anatomical image         |
| `freesurfer`  | FreeSurfer output directory          |
| `eccentricity`| pRF eccentricity map (`.nii.gz`)     |
| `varea`       | pRF visual area map (`.nii.gz`)      |

### Minimum inputs — DWI seed-based tracking mode

| Field         | Description                              |
|---------------|------------------------------------------|
| `dwi`         | DWI image (`.nii.gz`)                    |
| `bvec` / `bval` | Gradient directions and b-values       |
| `t1`          | T1-weighted anatomical image             |
| `freesurfer`  | FreeSurfer output directory              |
| `eccentricity`| pRF eccentricity map (`.nii.gz`)         |
| `varea`       | pRF visual area map (`.nii.gz`)          |

### Optional inputs (auto-computed if absent)

| Field         | Description                                                                 |
|---------------|-----------------------------------------------------------------------------|
| `fivett`      | 5-tissue-type image — computed from T1 via `5ttgen fsl` if absent          |
| `lgn_lh/rh`   | LGN ROIs — extracted from `ThalamicNuclei.v12.T1.FSvoxelSpace.mgz` (labels 8109/8209) |
| `v1_lh/rh`    | V1 ROIs — extracted from `varea == 1` masked by hemisphere ribbon           |
| `lmax2`…`lmax14` | Pre-computed CSD FOD images — skips `dwi2response` + `dwi2fod` if provided |
| `response`    | CSD response function                                                       |

### Tracking & segmentation parameters

| Field             | Type    | Default                    | Description                                      |
|-------------------|---------|----------------------------|--------------------------------------------------|
| `tractogram`      | string  | `null`                     | Pre-computed tractogram; skips tckgen entirely   |
| `algorithm`       | string  | `"iFOD2"`                  | Tracking algorithm — MRtrix3: `iFOD2`, `iFOD1`, `SD_Stream`, `FACT`, `Tensor_Det`, `Tensor_Prob`; DIPY: `dipy_prob`, `dipy_det`, `dipy_eudx`, `dipy_pft` |
| `seed_based`      | boolean | `true`                     | Seed from LGN, include V1 as waypoint            |
| `n_streamlines`        | integer | `50000`                    | Target number of streamlines per hemisphere                     |
| `sift2`           | boolean | `false`                    | Apply SIFT2 streamline weighting (MRtrix3 only)  |
| `pft_back_dist`  | number  | `2`                       | PFT back-tracking distance in mm (`dipy_pft` only) |
| `pft_front_dist` | number  | `1`                       | PFT front-tracking distance in mm (`dipy_pft` only) |
| `pft_particles`  | integer | `15`                      | Particles per streamline (`dipy_pft` only)      |
| `pft_max_cross`  | integer | `1`                       | Max crossings per voxel (`dipy_pft` only)       |
| `step_size`       | number  | `0.5`                      | Tracking step size (mm)                          |
| `max_angle`       | number  | `45`                       | Maximum turning angle (degrees)                  |
| `min_length`      | number  | `10`                       | Minimum streamline length (mm)                   |
| `max_length`      | number  | `250`                      | Maximum streamline length (mm)                   |
| `ecc_bins`        | string  | `"0-3,3-7,7-15,15-30,30-50,50-90"` | Eccentricity intervals as `lo-hi` pairs |
| `ends_only`       | boolean | `true`                     | Match ROIs at streamline endpoints only          |
| `hemispheres`     | array   | `["lh","rh"]`              | Hemispheres to process                           |
| `clean_streamlines`    | boolean | `true`                     | Apply iterative MAD-based fiber cleaning         |
| `clean_max_iter`  | integer | `5`                        | Maximum cleaning iterations                      |
| `clean_min_streamlines`| integer | `10`                       | Minimum fibers before stopping cleaning          |
| `nthreads`        | integer | `1`                        | Number of threads for MRtrix3                    |
| `force`           | boolean | `false`                    | Recompute all intermediate files                 |

---

## Outputs

| Path                          | Description                                            |
|-------------------------------|--------------------------------------------------------|
| `tcks/<name>.tck`             | Per-bundle tractograms                                 |
| `track/track.tck`             | Full tractogram used for segmentation                  |
| `wmc/classification.mat`      | Tract classification struct (Brainlife `wmc` datatype) |
| `wmc/tracts/<name>.tck`       | Per-bundle tractograms (wmc copy)                      |
| `wmc/tracts/<name>.json`      | Per-bundle visualization files                         |
| `5tt/5tt.nii.gz`              | 5-tissue-type image (if auto-computed)                 |
| `output_fibercounts.txt`      | Fiber counts per bundle                                |
| `QC/axial_qc.png`             | Axial QC image of segmented OR                         |
| `QC/coronal_qc.png`           | Coronal QC image of segmented OR                       |
| `QC/sagittal_qc.png`          | Sagittal QC image of segmented OR                      |
| `product.json`                | Brainlife metadata with embedded QC images             |
| `figures/images/`             | QC figures manifest for Brainlife UI                   |

All paths are relative to the current directory (Brainlife root) or to `--output_dir` when running locally.

---

## Local usage

### 1. Clone

```bash
git clone https://github.com/gamorosino/app-optic-radiation-track.git
cd app-optic-radiation-track
```

### 2. Run via CLI

`main_cli.sh` is a convenience wrapper that builds `config.json` from command-line flags and calls `main` directly — no container required for local runs if MRtrix3, FreeSurfer, and the Python dependencies are available on the host.

```bash
bash main_cli.sh \
    --dwi          /path/to/dwi.nii.gz \
    --bvec         /path/to/dwi.bvecs \
    --bval         /path/to/dwi.bvals \
    --t1           /path/to/t1.nii.gz \
    --freesurfer   /path/to/freesurfer/output \
    --eccentricity /path/to/eccentricity.nii.gz \
    --varea        /path/to/varea.nii.gz \
    --ecc_bins     "0-3,3-7,7-15,15-30,30-90" \
    --nthreads     8
```

#### Tractogram mode (skip tracking entirely)

```bash
bash main_cli.sh \
    --tractogram   /path/to/track.tck \
    --t1           /path/to/t1.nii.gz \
    --freesurfer   /path/to/freesurfer/output \
    --eccentricity /path/to/eccentricity.nii.gz \
    --varea        /path/to/varea.nii.gz \
    --ecc_bins     "0-3,3-7,7-15,15-30,30-90"
```

### 3. Requirements

- Singularity / Apptainer
- `jq`
- `FREESURFER_LICENSE` env var (path to FreeSurfer license file) — only needed if thalamic nuclei segmentation must be run

---

## Pipeline diagram

```
T1 + FreeSurfer + pRF (eccentricity, varea)
    │
    ├── [if lgn/v1 absent] Auto-extract ROIs
    │       ├── LGN: ThalamicNuclei.v12 labels 8109/8209
    │       └── V1:  varea==1 × hemisphere ribbon
    │
    ├── [if no tractogram] Fiber tracking
    │       ├── [if no 5TT] 5ttgen fsl (brainlife/mrtrix3)
    │       ├── [if no FOD]  dwi2response dhollander + dwi2fod msmt-CSD
    │       └── tckgen iFOD2  seed=LGN  include=V1
    │
    ├── Segmentation  (tckedit -include_ordered LGN V1, both directions)
    │       ├── OR_lh  →  work/segmentation/OR_lh.tck
    │       └── OR_rh  →  work/segmentation/OR_rh.tck
    │
    ├── Classification  (eccentricity bands from varea+eccentricity)
    │       └── OR_{hemi}_ecc_{lo}_{hi}.tck  per band
    │
    └── Export
            ├── tcks/  +  output/wmc/
            ├── QC images (axial / coronal / sagittal)
            └── product.json  (base64 QC + tract metadata)
```
