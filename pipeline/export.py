"""
Export results:
  - output/wmc/classification.mat   (scipy-compatible struct)
  - output/wmc/tracts/*.json        (Brainlife tract visualization)
  - output_fibercounts.txt
  - product.json
"""

import json
import os
import numpy as np
import scipy.io as sio
from dipy.io.streamline import save_tck
from dipy.io.stateful_tractogram import Space


def export_results(classification, paths, config):
    out        = config.get("output_dir", ".")
    wmc_dir    = paths["out_wmc"]
    tracts_dir = os.path.join(wmc_dir, "tracts")
    tcks_dir   = os.path.join(out, "tcks")
    os.makedirs(tracts_dir, exist_ok=True)
    os.makedirs(tcks_dir, exist_ok=True)

    tract_names = []
    tract_fibers = []  # list of (N, 3) arrays for classification.mat
    fiber_counts = {}
    tract_index = 1

    for hemi, bands in classification.items():
        for band_name, sft in bands.items():
            name = f"OR_{hemi}_{band_name}"
            tract_names.append(name)
            fiber_counts[name] = len(sft.streamlines)

            # Save individual .tck per tract (wmc/tracts and tcks/)
            tck_path = os.path.join(tracts_dir, f"{name}.tck")
            save_tck(sft, tck_path, bbox_valid_check=False)
            save_tck(sft, os.path.join(tcks_dir, f"{name}.tck"),
                     bbox_valid_check=False)

            # Build JSON visualization
            _save_tract_json(sft, name, tract_index,
                             os.path.join(tracts_dir, f"{name}.json"),
                             paths["ref"])

            tract_fibers.append(np.vstack(list(sft.streamlines))
                                if sft.streamlines else np.zeros((0, 3)))
            tract_index += 1

    # tcks.json — index file required by neuro/tcks datatype
    tcks_meta = [
        {"name": n, "filename": f"{n}.tck", "nfibers": fiber_counts[n]}
        for n in tract_names
    ]
    with open(os.path.join(out, "tcks.json"), "w") as f:
        json.dump(tcks_meta, f, indent=2)
    print(f"  tcks.json written to {os.path.join(out, 'tcks.json')}")

    # classification.mat  (mirrors MATLAB wmc structure)
    _save_classification_mat(
        os.path.join(wmc_dir, "classification.mat"),
        tract_names,
        classification,
    )

    # fiber counts
    counts_path = "output_fibercounts.txt"
    with open(counts_path, "w") as f:
        for name, count in fiber_counts.items():
            f.write(f"{name}: {count}\n")
    print(f"  Fiber counts written to {counts_path}")

    # product.json
    product = {
        "tracts": [
            {"name": n, "nfibers": fiber_counts[n]}
            for n in tract_names
        ]
    }
    with open("product.json", "w") as f:
        json.dump(product, f, indent=2)
    print("  product.json written")


def _save_tract_json(sft, name, index, out_path, dwi_ref):
    """Brainlife-compatible tract JSON."""
    coords = []
    for sl in sft.streamlines:
        coords.append(sl.tolist())
    tract_json = {
        "name":  name,
        "index": index,
        "coords": coords,
    }
    with open(out_path, "w") as f:
        json.dump(tract_json, f)


def _save_classification_mat(out_path, tract_names, classification):
    """
    Saves a classification struct compatible with the Brainlife wmc datatype.
    Structure:
      classification.names  — cell array of tract names
      classification.index  — vector assigning each fiber to a tract (1-based)
    """
    names = np.array(tract_names, dtype=object)

    index_list = []
    tract_idx = 1
    for hemi, bands in classification.items():
        for band_name, sft in bands.items():
            n = len(sft.streamlines)
            index_list.extend([tract_idx] * n)
            tract_idx += 1

    index = np.array(index_list, dtype=np.int32)

    mat_struct = {
        "names": names,
        "index": index,
    }
    sio.savemat(out_path, {"classification": mat_struct})
    print(f"  classification.mat written to {out_path}")
