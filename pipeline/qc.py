"""
Generate QC images (axial, coronal, sagittal) of the segmented optic radiation
overlaid on the anatomical reference image.
"""

import os
import numpy as np
import nibabel as nib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dipy.io.streamline import load_tck


_COLORS = {
    "lh": "#FF4444",
    "rh": "#4444FF",
}


def generate_qc_images(classification, paths, config, out_dir="QC"):
    """
    Render axial, coronal, and sagittal QC PNGs of all OR tracts over the T1.
    Returns list of output PNG paths.
    """
    os.makedirs(out_dir, exist_ok=True)

    ref_img = nib.load(paths["t1"])
    ref_data = ref_img.get_fdata()
    affine = ref_img.affine
    shape = ref_data.shape[:3]

    density = _build_density_map(classification, paths, shape, affine)

    # Find bounding box of tract density for smart centering
    nz = np.argwhere(density > 0)
    if len(nz):
        center = nz.mean(axis=0).astype(int)
    else:
        center = np.array(shape) // 2

    views = {
        "axial":    (2, center[2]),
        "coronal":  (1, center[1]),
        "sagittal": (0, center[0]),
    }

    out_paths = []
    for view_name, (axis, idx) in views.items():
        out_path = os.path.join(out_dir, f"{view_name}_qc.png")
        _render_slice(ref_data, density, axis, idx, out_path, view_name)
        out_paths.append(out_path)
        print(f"  QC: {out_path}")

    return out_paths


def _build_density_map(classification, paths, shape, affine):
    """Voxelize all OR streamlines into a density map in T1 space."""
    density = np.zeros(shape, dtype=np.float32)
    inv_affine = np.linalg.inv(affine)

    for hemi, bands in classification.items():
        for band_name, sft in bands.items():
            if len(sft.streamlines) == 0:
                continue
            # Convert to mm (RASMM) then to T1 voxels
            sft.to_rasmm()
            for sl in sft.streamlines:
                ones = np.ones((len(sl), 1))
                sl_h = np.hstack([sl, ones])
                vox = (inv_affine @ sl_h.T).T[:, :3]
                vox_int = np.round(vox).astype(int)
                mask = np.all((vox_int >= 0) & (vox_int < np.array(shape)), axis=1)
                vox_int = vox_int[mask]
                density[vox_int[:, 0], vox_int[:, 1], vox_int[:, 2]] += 1.0

    if density.max() > 0:
        density /= density.max()
    return density


def _render_slice(anat, density, axis, idx, out_path, title):
    """Render one slice of anat + density overlay and save to out_path."""
    def _take(vol, ax, i):
        if ax == 0:
            return np.rot90(vol[i, :, :])
        elif ax == 1:
            return np.rot90(vol[:, i, :])
        else:
            return np.rot90(vol[:, :, i])

    anat_slice = _take(anat, axis, idx)
    dens_slice = _take(density, axis, idx)

    fig, ax = plt.subplots(1, 1, figsize=(5, 5))
    fig.patch.set_facecolor("black")
    ax.set_facecolor("black")

    vmin, vmax = np.percentile(anat_slice[anat_slice > 0], [1, 99]) \
        if anat_slice.max() > 0 else (0, 1)
    ax.imshow(anat_slice, cmap="gray", origin="upper", vmin=vmin, vmax=vmax)

    if dens_slice.max() > 0:
        cmap_overlay = plt.cm.hot
        rgba = cmap_overlay(dens_slice)
        rgba[..., 3] = np.where(dens_slice > 0.01, 0.65, 0.0)
        ax.imshow(rgba, origin="upper")

    ax.set_title(title.capitalize(), color="white", fontsize=10, pad=3)
    ax.axis("off")
    plt.tight_layout(pad=0.2)
    plt.savefig(out_path, dpi=150, bbox_inches="tight",
                facecolor="black", edgecolor="none")
    plt.close(fig)
