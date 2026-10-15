#!/usr/bin/env python3
"""
app-optic-radiation-tract
Tractography and eccentricity-based segmentation of the human optic radiation.
"""

import json
import os
from pipeline.preprocess import preprocess
from pipeline.tracking import run_tracking
from pipeline.segmentation import segment_fibers
from pipeline.classification import classify_by_eccentricity
from pipeline.export import export_results
from pipeline.qc import generate_qc_images


def load_config(path="config.json"):
    with open(path) as f:
        return json.load(f)


def main():
    config = load_config()

    # Input paths come from config.json; output paths are fixed locals
    paths = {
        "dwi":          config.get("dwi"),
        "bvec":         config.get("bvec"),
        "bval":         config.get("bval"),
        "t1":           config["t1"],
        "freesurfer":   config["freesurfer"],
        "eccentricity": config["eccentricity"],
        "varea":        config["varea"],
        "lgn_lh":       config["lgn_lh"],
        "lgn_rh":       config["lgn_rh"],
        "v1_lh":        config["v1_lh"],
        "v1_rh":        config["v1_rh"],
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
