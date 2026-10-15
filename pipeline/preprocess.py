"""
Preprocessing: resample FreeSurfer volumes to diffusion space,
build hemisphere masks, generate tissue masks.
"""

import os
import subprocess
import numpy as np
import nibabel as nib
from nilearn.image import resample_to_img


def preprocess(paths, config):
    """
    Returns a dict of preprocessed volume paths in diffusion space.
    """
    ref = nib.load(paths["ref"])  # reference space (DWI or lmax)
    w   = config.get("work_dir", "work")
    os.makedirs(w, exist_ok=True)

    out = {}

    # Resample ribbon (hemisphere labels) to diffusion space
    ribbon_fs = os.path.join(paths["freesurfer"], "mri", "ribbon.mgz")
    out["ribbon"] = _resample_to_dwi(ribbon_fs, ref, f"{w}/ribbon_dwi.nii.gz",
                                     interpolation="nearest")

    # Resample aparc+aseg (for thalamus / LGN masks if not provided)
    aparc = os.path.join(paths["freesurfer"], "mri", "aparc+aseg.mgz")
    out["aparc"] = _resample_to_dwi(aparc, ref, f"{w}/aparc_dwi.nii.gz",
                                    interpolation="nearest")

    # Resample pRF eccentricity and varea maps to diffusion space
    out["eccentricity"] = _resample_to_dwi(paths["eccentricity"], ref,
                                           f"{w}/eccentricity_dwi.nii.gz",
                                           interpolation="linear")
    out["varea"] = _resample_to_dwi(paths["varea"], ref,
                                    f"{w}/varea_dwi.nii.gz",
                                    interpolation="nearest")

    # LGN ROIs: use provided paths or extract from thalamic nuclei segmentation
    if paths.get("lgn_lh") and paths.get("lgn_rh"):
        for roi in ("lgn_lh", "lgn_rh"):
            out[roi] = _resample_to_dwi(paths[roi], ref,
                                        f"{w}/{roi}_dwi.nii.gz",
                                        interpolation="nearest")
    else:
        print("  LGN ROIs not provided — extracting from ThalamicNuclei segmentation")
        thal_mgz = os.path.join(paths["freesurfer"], "mri",
                                "ThalamicNuclei.v12.T1.FSvoxelSpace.mgz")
        thal_img = nib.load(thal_mgz)
        thal_data = np.round(thal_img.get_fdata()).astype(int)
        for hemi, label in [("lh", 8109), ("rh", 8209)]:
            mask = (thal_data == label).astype(np.uint8)
            mask_img = nib.Nifti1Image(mask, thal_img.affine, thal_img.header)
            raw_path = f"{w}/lgn_{hemi}_thal.nii.gz"
            nib.save(mask_img, raw_path)
            out[f"lgn_{hemi}"] = _resample_to_dwi(raw_path, ref,
                                                   f"{w}/lgn_{hemi}_dwi.nii.gz",
                                                   interpolation="nearest")

    # V1 ROIs: use provided paths or extract from varea == 1, split by hemisphere
    if paths.get("v1_lh") and paths.get("v1_rh"):
        for roi in ("v1_lh", "v1_rh"):
            out[roi] = _resample_to_dwi(paths[roi], ref,
                                        f"{w}/{roi}_dwi.nii.gz",
                                        interpolation="nearest")
    else:
        print("  V1 ROIs not provided — extracting from varea (label 1) per hemisphere")
        varea_img = nib.load(out["varea"])
        varea_data = np.round(np.squeeze(varea_img.get_fdata())).astype(int)
        ribbon_img = nib.load(out["ribbon"])
        ribbon_data = np.squeeze(ribbon_img.get_fdata()).astype(int)
        for hemi, label in [("lh", 3), ("rh", 42)]:
            mask = ((varea_data == 1) & (ribbon_data == label)).astype(np.uint8)
            mask_img = nib.Nifti1Image(mask, varea_img.affine, varea_img.header)
            raw_path = f"{w}/v1_{hemi}_raw.nii.gz"
            nib.save(mask_img, raw_path)
            out[f"v1_{hemi}"] = raw_path  # already in DWI space (varea was resampled)

    # Build hemisphere masks from ribbon (lh=3, rh=42 in FreeSurfer convention)
    ribbon_img = nib.load(out["ribbon"])
    ribbon_data = ribbon_img.get_fdata()
    for hemi, label in [("lh", 3), ("rh", 42)]:
        mask = (ribbon_data == label).astype(np.uint8)
        mask_img = nib.Nifti1Image(mask, ribbon_img.affine, ribbon_img.header)
        p = f"{w}/hemi_mask_{hemi}.nii.gz"
        nib.save(mask_img, p)
        out[f"hemi_mask_{hemi}"] = p

    # CSF mask from 5TT (volume index 3); skipped in tractogram mode
    fivett_nii = paths.get("fivett")
    if fivett_nii:
        fivett_img = nib.load(fivett_nii)
        fivett_data = fivett_img.get_fdata()
        csf_mask = (fivett_data[..., 3] > 0.5).astype(np.uint8)
        csf_img = nib.Nifti1Image(csf_mask, fivett_img.affine, fivett_img.header)
        out["csf_mask"] = f"{w}/csf_mask.nii.gz"
        nib.save(csf_img, out["csf_mask"])
    else:
        out["csf_mask"] = None

    return out


def _run(cmd):
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def _resample_to_dwi(src_path, ref_img, out_path, interpolation="linear"):
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    src_img = nib.load(src_path)
    resampled = resample_to_img(src_img, ref_img, interpolation=interpolation,
                                force_resample=True)
    nib.save(resampled, out_path)
    return out_path
