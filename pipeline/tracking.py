"""
Fiber tracking: MRtrix3 (default) or DIPY.
Both paths produce output/track/track.tck.

Algorithm → backend mapping
  MRtrix3 : iFOD2 (default), iFOD1, SD_Stream, SD_Det  → FOD input
             FACT                                        → peaks input
             Tensor_Det, Tensor_Prob                     → DWI input
  DIPY    : dipy_prob, dipy_det, dipy_eudx, dipy_pft
"""

import os
import subprocess
import numpy as np
import nibabel as nib

# MRtrix3 algorithms grouped by required input type
_MRTRIX_FOD_ALGOS   = {"iFOD1", "iFOD2", "SD_Stream"}
_MRTRIX_PEAKS_ALGOS = {"FACT"}
_MRTRIX_DWI_ALGOS   = {"Tensor_Det", "Tensor_Prob"}
_MRTRIX_ALGOS       = _MRTRIX_FOD_ALGOS | _MRTRIX_PEAKS_ALGOS | _MRTRIX_DWI_ALGOS

# Map display names → tckgen's expected lowercase names
_MRTRIX_NAME_MAP = {
    "iFOD1":      "ifod1",
    "iFOD2":      "ifod2",
    "SD_Stream":  "sd_stream",
    "FACT":       "fact",
    "Tensor_Det": "tensor_det",
    "Tensor_Prob":"tensor_prob",
}

_DIPY_ALGOS = {"dipy_prob", "dipy_det", "dipy_eudx", "dipy_pft"}


def run_tracking(paths, prep, config):
    tractogram = config.get("tractogram")
    if tractogram:
        paths["out_track"] = tractogram
        print(f"  Using provided tractogram: {tractogram}")
        return

    algorithm = config.get("algorithm", "iFOD2")

    if algorithm in _MRTRIX_ALGOS:
        _track_mrtrix(paths, prep, config, algorithm)
    elif algorithm in _DIPY_ALGOS:
        _track_dipy(paths, prep, config, algorithm)
    else:
        raise ValueError(
            f"Unknown algorithm '{algorithm}'. "
            f"MRtrix3: {sorted(_MRTRIX_ALGOS)}. "
            f"DIPY: {sorted(_DIPY_ALGOS)}."
        )


# ---------------------------------------------------------------------------
# MRtrix3 backend
# ---------------------------------------------------------------------------

def _track_mrtrix(paths, prep, config, algorithm):
    work = os.path.join(config.get("work_dir", "work"), "mrtrix")
    os.makedirs(work, exist_ok=True)

    dwi     = paths.get("dwi")
    bvec    = paths.get("bvec")
    bval    = paths.get("bval")
    fivett  = paths["fivett"]
    out_tck = paths["out_track"]

    n_streamlines = config.get("n_streamlines", 50000)
    step_size     = config.get("step_size", 0.2)
    max_angle     = config.get("max_angle", 45)
    min_length    = config.get("min_length", 10)
    max_length    = config.get("max_length", 250)
    seed_based    = config.get("seed_based", True)

    # Determine tckgen input image based on algorithm family
    if algorithm in _MRTRIX_FOD_ALGOS:
        tckgen_input = _get_or_compute_fod(paths, config, work, dwi, bvec, bval)
    elif algorithm in _MRTRIX_PEAKS_ALGOS:
        fod = _get_or_compute_fod(paths, config, work, dwi, bvec, bval)
        tckgen_input = _fod_to_peaks(fod, work, config)
    elif algorithm in _MRTRIX_DWI_ALGOS:
        tckgen_input = _get_dwi_mif(paths, work, dwi, bvec, bval, config)

    tckgen_algorithm = _MRTRIX_NAME_MAP.get(algorithm, algorithm.lower())
    base_cmd = [
        "-algorithm", tckgen_algorithm,
        "-select", str(n_streamlines),
        "-step", str(step_size),
        "-angle", str(max_angle),
        "-minlength", str(min_length),
        "-maxlength", str(max_length),
        "-act", fivett,
        "-crop_at_gmwmi",
        "-force",
    ]
    # -backtrack is only valid for probabilistic iFOD algorithms
    if algorithm in {"iFOD1", "iFOD2"}:
        base_cmd.insert(base_cmd.index("-crop_at_gmwmi"), "-backtrack")

    if seed_based:
        lgn_lh = prep.get("lgn_lh") or paths.get("lgn_lh")
        lgn_rh = prep.get("lgn_rh") or paths.get("lgn_rh")
        v1_lh  = prep.get("v1_lh")  or paths.get("v1_lh")
        v1_rh  = prep.get("v1_rh")  or paths.get("v1_rh")

        hemi_tcks = []
        for hemi, lgn, v1 in [("lh", lgn_lh, v1_lh), ("rh", lgn_rh, v1_rh)]:
            seed_mask = _make_combined_mask(
                [lgn], paths["ref"], f"{work}/lgn_seed_{hemi}.nii.gz"
            )
            v1_mask = _make_combined_mask(
                [v1], paths["ref"], f"{work}/v1_include_{hemi}.nii.gz"
            )
            hemi_tck = f"{work}/track_{hemi}.tck"
            cmd = ["tckgen", tckgen_input, hemi_tck] + base_cmd + [
                "-seed_image", seed_mask,
                "-include", v1_mask,
            ]
            print(f"  [{algorithm}] Seed-based tracking ({hemi}): LGN_{hemi} → V1_{hemi}")
            _run(cmd)
            hemi_tcks.append(hemi_tck)

        os.makedirs(os.path.dirname(out_tck), exist_ok=True)
        _run(["tckedit"] + hemi_tcks + [out_tck, "-force"])
        print(f"  Combined lh+rh tractograms → {out_tck}")
    else:
        cmd = ["tckgen", tckgen_input, out_tck] + base_cmd
        if config.get("seed_dynamic", True) and algorithm in _MRTRIX_FOD_ALGOS:
            cmd += ["-seed_dynamic", tckgen_input]
        else:
            cmd += ["-seed_gmwmi", prep["gmwmi"]]
        print(f"  [{algorithm}] Whole-brain ACT tracking")
        _run(cmd)

    if config.get("sift2", False):
        if algorithm in _MRTRIX_FOD_ALGOS:
            fod_for_sift = tckgen_input
        else:
            # SIFT2 requires a FOD image — compute if not already done
            fod_for_sift = _get_or_compute_fod(paths, config, work, dwi, bvec, bval)
        weights = f"{work}/sift2_weights.txt"
        _run(["tcksift2", out_tck, fod_for_sift, weights, "-force"])
        config["_sift2_weights"] = weights


def _get_dwi_mif(paths, work, dwi, bvec, bval, config):
    """Convert DWI to .mif for Tensor_Det / Tensor_Prob."""
    mif = f"{work}/dwi.mif"
    force = config.get("force", False)
    if force or not os.path.isfile(mif):
        _run(["mrconvert", dwi, mif, "-fslgrad", bvec, bval, "-force"])
    return mif


def _fod_to_peaks(fod_mif, work, config):
    """Extract peaks from a FOD image for FACT tracking."""
    peaks_mif = f"{work}/peaks.mif"
    force = config.get("force", False)
    if force or not os.path.isfile(peaks_mif):
        print("  Extracting FOD peaks for FACT (sh2peaks)")
        _run(["sh2peaks", fod_mif, peaks_mif, "-force"])
    else:
        print(f"  Skipping sh2peaks (exists): {peaks_mif}")
    return peaks_mif


# ---------------------------------------------------------------------------
# DIPY backend — uses DIPY CLI tools (dipy_fit_csd / dipy_track / dipy_track_pft)
# to avoid loading the full DWI array into memory (same approach as dipy_track CLI).
# ---------------------------------------------------------------------------

def _track_dipy(paths, prep, config, algorithm):
    work = os.path.join(config.get("work_dir", "work"), "dipy")
    os.makedirs(work, exist_ok=True)
    out_tck = paths["out_track"]
    os.makedirs(os.path.dirname(out_tck), exist_ok=True)

    # Brain mask from b0 (only one volume loaded — memory-light)
    mask_path = _dipy_b0_mask(paths["dwi"], paths["bval"], work, config)

    # Fit CSD peaks via CLI (writes .pam5 to disk, never holds full DWI in RAM)
    if algorithm == "dipy_eudx":
        peaks_path = _dipy_fit_dti(paths, work, mask_path, config)
    else:
        peaks_path = _dipy_fit_csd(paths, work, mask_path, config)

    # Seed mask: LGN (seed_based) or brain mask (whole-brain)
    seed_based = config.get("seed_based", True)
    if seed_based:
        lgn_lh = prep.get("lgn_lh") or paths.get("lgn_lh")
        lgn_rh = prep.get("lgn_rh") or paths.get("lgn_rh")
        seed_mask = _make_combined_mask(
            [lgn_lh, lgn_rh], paths["ref"], f"{work}/lgn_seed.nii.gz"
        )
    else:
        seed_mask = mask_path

    # Track via CLI → .trk, then convert to .tck
    trk_path = os.path.join(work, "track.trk")
    if algorithm == "dipy_pft":
        fivett_path = paths.get("fivett")
        if not fivett_path:
            raise ValueError("dipy_pft requires a 5TT image (--fivett or auto-computed)")
        _dipy_cli_pft(peaks_path, fivett_path, seed_mask, work, trk_path, config)
    else:
        det = algorithm in ("dipy_det", "dipy_eudx")
        _dipy_cli_track(peaks_path, mask_path, seed_mask, work, trk_path, det, config)

    _trk_to_tck(trk_path, out_tck)


def _dipy_b0_mask(dwi_path, bval_path, work, config):
    """Compute a brain mask from the mean b0 — loads only b=0 volumes."""
    mask_path = f"{work}/brain_mask.nii.gz"
    force = config.get("force", False)
    if not force and os.path.isfile(mask_path):
        return mask_path
    import numpy as np
    import nibabel as nib
    bvals = np.loadtxt(bval_path)
    b0_indices = np.where(bvals < 100)[0]
    dwi_img = nib.load(dwi_path)
    b0_sum = None
    for i in b0_indices:
        vol = np.asarray(dwi_img.dataobj[..., int(i)])
        b0_sum = vol if b0_sum is None else b0_sum + vol
    b0_mean = b0_sum / len(b0_indices)
    threshold = np.percentile(b0_mean[b0_mean > 0], 20)
    mask = (b0_mean > threshold).astype(np.uint8)
    nib.save(nib.Nifti1Image(mask, dwi_img.affine), mask_path)
    print(f"  Brain mask written: {mask_path}")
    return mask_path


def _dipy_fit_csd(paths, work, mask_path, config):
    """Run dipy_fit_csd CLI — processes DWI in chunks, not loaded fully into RAM."""
    peaks_path = os.path.join(work, "peaks.pam5")
    force = config.get("force", False)
    if not force and os.path.isfile(peaks_path):
        print(f"  Skipping dipy_fit_csd (exists): {peaks_path}")
        return peaks_path
    sh_order = config.get("sh_order", 6)
    print(f"  Fitting CSD peaks (sh_order={sh_order}) via dipy_fit_csd")
    _run([
        "dipy_fit_csd",
        paths["dwi"], paths["bval"], paths["bvec"], mask_path,
        "--sh_order", str(sh_order),
        "--out_dir", work,
        "--out_pam", "peaks.pam5",
        "--out_gfa", "gfa.nii.gz",
        "--force",
    ])
    return peaks_path


def _dipy_fit_dti(paths, work, mask_path, config):
    """Run dipy_fit_dti CLI to get DTI-based peaks for EuDX tracking."""
    peaks_path = os.path.join(work, "peaks.pam5")
    force = config.get("force", False)
    if not force and os.path.isfile(peaks_path):
        print(f"  Skipping dipy_fit_dti (exists): {peaks_path}")
        return peaks_path
    print("  Fitting DTI peaks via dipy_fit_dti")
    _run([
        "dipy_fit_dti",
        paths["dwi"], paths["bval"], paths["bvec"], mask_path,
        "--out_dir", work,
        "--out_pam", "peaks.pam5",
        "--force",
    ])
    return peaks_path


def _dipy_cli_track(peaks_path, stop_mask, seed_mask, work, trk_path, deterministic, config):
    """Run dipy_track CLI."""
    method = "det" if deterministic else "prob"
    label = "dipy_det/eudx" if deterministic else "dipy_prob"
    print(f"  [{label}] Running dipy_track (method={method})")
    _run([
        "dipy_track",
        peaks_path, stop_mask, seed_mask,
        "--tracking_method", method,
        "--max_angle",   str(config.get("max_angle",   45)),
        "--step_size",   str(config.get("step_size",  0.5)),
        "--seed_density","1",
        "--out_dir",     work,
        "--out_tractogram", "track.trk",
        "--force",
    ])


def _dipy_cli_pft(peaks_path, fivett_path, seed_mask, work, trk_path, config):
    """
    Run dipy_track_pft CLI.
    Extracts WM/GM/CSF PVE maps from 5TT on-the-fly (only one 3D volume at a time).
    """
    import nibabel as nib
    # Extract PVE maps from 5TT (vol 0+1=GM, vol 2=WM, vol 3=CSF)
    fivett_img  = nib.load(fivett_path)
    fivett_data = fivett_img.dataobj  # use dataobj to avoid loading all at once
    for name, idx in [("pve_wm", 2), ("pve_csf", 3)]:
        vol = np.array(fivett_data[..., idx])
        nib.save(nib.Nifti1Image(vol.astype(np.float32), fivett_img.affine),
                 os.path.join(work, f"{name}.nii.gz"))
    gm = (np.array(fivett_data[..., 0]) + np.array(fivett_data[..., 1])).astype(np.float32)
    nib.save(nib.Nifti1Image(gm, fivett_img.affine), os.path.join(work, "pve_gm.nii.gz"))

    print("  [dipy_pft] Running dipy_track_pft")
    _run([
        "dipy_track_pft",
        peaks_path,
        os.path.join(work, "pve_wm.nii.gz"),
        os.path.join(work, "pve_gm.nii.gz"),
        os.path.join(work, "pve_csf.nii.gz"),
        seed_mask,
        "--max_angle",    str(config.get("max_angle",    45)),
        "--step_size",    str(config.get("step_size",   0.5)),
        "--seed_density", "1",
        "--pft_back_tracking_dist",  str(config.get("pft_back_dist",  2)),
        "--pft_front_tracking_dist", str(config.get("pft_front_dist", 1)),
        "--particle_count",          str(config.get("pft_particles",  15)),
        "--out_dir",      work,
        "--out_tractogram", "track.trk",
        "--force",
    ])


def _trk_to_tck(trk_path, tck_path):
    """Convert TrackVis .trk to MRtrix .tck (nibabel, no full data copy in RAM)."""
    import nibabel as nib
    trk = nib.streamlines.load(trk_path)
    nib.streamlines.save(trk.tractogram, tck_path)
    print(f"  Converted {trk_path} → {tck_path}")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_combined_mask(roi_paths, ref_path, out_path):
    """Union of one or more binary NIfTI ROIs resampled to ref space."""
    from nilearn.image import resample_to_img
    ref_img = nib.load(ref_path)
    combined = None
    for rp in roi_paths:
        img = nib.load(rp)
        resampled = resample_to_img(img, ref_img, interpolation="nearest",
                                    force_resample=True)
        data = (resampled.get_fdata() > 0).astype(np.uint8)
        combined = data if combined is None else np.maximum(combined, data)
    out_img = nib.Nifti1Image(combined, ref_img.affine, ref_img.header)
    nib.save(out_img, out_path)
    return out_path


def _get_or_compute_fod(paths, config, work, dwi, bvec, bval):
    """Return path to WM FOD .mif; uses provided lmax if available."""
    available = {}
    for key, val in config.items():
        if key.startswith("lmax") and key[4:].isdigit() and val:
            available[int(key[4:])] = val

    if available:
        requested = config.get("lmax")
        chosen_order = (int(requested) if requested and int(requested) in available
                        else max(available.keys()))
        chosen_nii = available[chosen_order]
        print(f"  Using provided CSD lmax{chosen_order}: {chosen_nii}")
        wm_fod = f"{work}/wm_fod.mif"
        _run(["mrconvert", chosen_nii, wm_fod, "-force"])
        return wm_fod

    force    = config.get("force", False)
    mif      = f"{work}/dwi.mif"
    wm_resp  = f"{work}/wm.txt"
    gm_resp  = f"{work}/gm.txt"
    csf_resp = f"{work}/csf.txt"
    wm_fod   = f"{work}/wm_fod.mif"
    gm_fod   = f"{work}/gm_fod.mif"
    csf_fod  = f"{work}/csf_fod.mif"

    if force or not os.path.isfile(mif):
        _run(["mrconvert", dwi, mif, "-fslgrad", bvec, bval, "-force"])
    else:
        print(f"  Skipping mrconvert (exists): {mif}")

    if force or not os.path.isfile(wm_resp):
        print("  No CSD provided — estimating response functions (dhollander)")
        _run(["dwi2response", "dhollander", mif,
              wm_resp, gm_resp, csf_resp, "-force"])
    else:
        print(f"  Skipping dwi2response (exists): {wm_resp}")

    if force or not os.path.isfile(wm_fod):
        print("  Estimating FODs (msmt-CSD)")
        _run(["dwi2fod", "msmt_csd", mif,
              wm_resp, wm_fod,
              gm_resp, gm_fod,
              csf_resp, csf_fod,
              "-force"])
    else:
        print(f"  Skipping dwi2fod (exists): {wm_fod}")

    return wm_fod


def _run(cmd):
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)
