#!/usr/bin/env python3
"""
app-optic-radiation-tract
Tractography and eccentricity-based segmentation of the human optic radiation.
"""

import json
import os
from pathlib import Path
from pipeline.preprocess import preprocess
from pipeline.tracking import run_tracking
from pipeline.segmentation import segment_fibers
from pipeline.classification import classify_by_eccentricity
from pipeline.export import export_results
from pipeline.qc import generate_qc_images


def load_config(path="config.json"):
    with open(path) as f:
        return json.load(f)


def _resolve_rois_from_dir(rois_dir):
    """Resolve lgn_lh/rh and v1_lh/rh paths from a neuro/rois directory.

    Reads label.json (list of {name, filename} or {name: filename} dict)
    when present; falls back to <roi_name>.nii.gz filename convention.
    Returns a dict with whichever of the four keys were found.
    """
    rois_path = Path(rois_dir)
    if not rois_path.is_dir():
        return {}

    name_to_file = {}
    label_json = rois_path.parent / "label.json"
    if label_json.exists():
        labels = json.loads(label_json.read_text())
        if isinstance(labels, list):
            for entry in labels:
                name_to_file[entry["name"]] = rois_path / entry["filename"]
        elif isinstance(labels, dict):
            for name, filename in labels.items():
                name_to_file[name] = rois_path / filename

    resolved = {}
    for roi in ("lgn_lh", "lgn_rh", "v1_lh", "v1_rh"):
        if roi in name_to_file and name_to_file[roi].exists():
            resolved[roi] = str(name_to_file[roi])
        else:
            for candidate in (f"{roi}.nii.gz", f"{roi}.nii"):
                p = rois_path / candidate
                if p.exists():
                    resolved[roi] = str(p)
                    break
    return resolved


def main():
    config = load_config()

    # Resolve individual ROI paths: brainlife passes a rois/ directory;
    # CLI passes lgn_lh/rh and v1_lh/rh directly in config.
    rois_from_dir = _resolve_rois_from_dir(config["rois"]) if config.get("rois") else {}

    # Input paths come from config.json; output paths are fixed locals
    paths = {
        "dwi":          config.get("dwi"),
        "bvec":         config.get("bvec"),
        "bval":         config.get("bval"),
        "t1":           config["t1"],
        "freesurfer":   config["freesurfer"],
        "eccentricity": config["eccentricity"],
        "varea":        config["varea"],
        "lgn_lh":       config.get("lgn_lh") or rois_from_dir.get("lgn_lh"),
        "lgn_rh":       config.get("lgn_rh") or rois_from_dir.get("lgn_rh"),
        "v1_lh":        config.get("v1_lh")  or rois_from_dir.get("v1_lh"),
        "v1_rh":        config.get("v1_rh")  or rois_from_dir.get("v1_rh"),
        "fivett":       config.get("fivett"),
    }

    out      = config.get("output_dir", ".")
    work_dir = config.get("work_dir", "work")
    paths["out_track"] = os.path.join(out, "track", "track.tck")
    paths["out_wmc"]   = os.path.join(out, "wmc")

    os.makedirs(work_dir, exist_ok=True)

    # Reference image for voxel space: DWI if available, else highest lmax
    lmax_files = {int(k[4:]): v for k, v in config.items()
                  if k.startswith("lmax") and k[4:].isdigit() and v}
    if paths["dwi"]:
        paths["ref"] = paths["dwi"]
    elif lmax_files:
        paths["ref"] = lmax_files[max(lmax_files)]
    elif config.get("tractogram"):
        paths["ref"] = paths["t1"]
    else:
        raise ValueError("Provide --dwi, at least one --lmax<N>, or --tractogram.")

    os.makedirs(os.path.dirname(paths["out_track"]), exist_ok=True)
    os.makedirs(os.path.join(paths["out_wmc"], "tracts"), exist_ok=True)
    os.makedirs(os.path.join(out, "tcks"), exist_ok=True)

    print("[1/5] Preprocessing: resampling FreeSurfer volumes to diffusion space")
    prep = preprocess(paths, config)

    print("[2/5] Fiber tracking:", config.get("algorithm", "iFOD2"))
    run_tracking(paths, prep, config)

    print("[3/5] Fiber segmentation (optic radiation isolation)")
    fibers_per_hemi = segment_fibers(paths, prep, config)

    print("[4/5] Eccentricity-based classification")
    classification = classify_by_eccentricity(fibers_per_hemi, paths, prep, config)

    print("[5/5] Exporting results")
    export_results(classification, paths, config)

    print("[6/6] Generating QC images")
    generate_qc_images(classification, paths, config, out_dir="QC")

    print("Done.")


if __name__ == "__main__":
    main()
