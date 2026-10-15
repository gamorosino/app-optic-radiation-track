"""
Segment the optic radiation from the whole-brain tractogram using
tckedit with ordered ROI inclusion (LGN <-> V1, per hemisphere).
"""

import os
import subprocess
import numpy as np
import nibabel as nib
from pathlib import Path
from dipy.io.streamline import load_tck, save_tck
from dipy.io.stateful_tractogram import Space, StatefulTractogram


def segment_fibers(paths, prep, config):
    """
    Returns dict: {"lh": StatefulTractogram, "rh": StatefulTractogram}
    Uses tckedit with -include_ordered in both directions to capture
    fibers connecting LGN and V1 for each hemisphere.
    """
    seg_dir = os.path.join(config.get("work_dir", "work"), "segmentation")
    os.makedirs(seg_dir, exist_ok=True)
    track = Path(paths["out_track"])
    ends_only = config.get("ends_only", True)

    result = {}
    for hemi in config.get("hemispheres", ["lh", "rh"]):
        lgn = prep[f"lgn_{hemi}"]
        v1  = prep[f"v1_{hemi}"]

        out_tck = Path(os.path.join(seg_dir, f"OR_{hemi}.tck"))
        _tckedit_ordered(track, lgn, v1, out_tck, ends_only=ends_only)

        # Load result
        if out_tck.stat().st_size > 0:
            sft = load_tck(str(out_tck), paths["ref"],
                           bbox_valid_check=False, trk_header_check=False)
            sft.to_vox()
            streamlines = list(sft.streamlines)
        else:
            streamlines = []

        if config.get("clean_streamlines", True) and streamlines:
            streamlines = _iterative_clean(streamlines, config)

        sft_hemi = StatefulTractogram(streamlines, paths["ref"], Space.VOX)
        result[hemi] = sft_hemi

        # Overwrite with cleaned version
        save_tck(sft_hemi, str(out_tck), bbox_valid_check=False)
        print(f"  OR {hemi}: {len(streamlines)} fibers -> {out_tck}")

    return result


def _tckedit_ordered(track, roi1, roi2, out_tck, ends_only=True):
    """
    Keep streamlines that connect roi1 and roi2 in either order.
    Runs tckedit twice (12 and 21 direction) then merges.
    """
    tmp12 = out_tck.with_suffix(".tmp12.tck")
    tmp21 = out_tck.with_suffix(".tmp21.tck")

    cmd12 = ["tckedit", str(track), str(tmp12),
             "-include_ordered", str(roi1), "-include_ordered", str(roi2), "-force"]
    cmd21 = ["tckedit", str(track), str(tmp21),
             "-include_ordered", str(roi2), "-include_ordered", str(roi1), "-force"]
    if ends_only:
        cmd12.append("-ends_only")
        cmd21.append("-ends_only")

    print(f"  $ {' '.join(cmd12)}")
    subprocess.run(cmd12, check=True)
    print(f"  $ {' '.join(cmd21)}")
    subprocess.run(cmd21, check=True)

    merge_cmd = ["tckedit", str(tmp12), str(tmp21), str(out_tck), "-force"]
    print(f"  $ {' '.join(merge_cmd)}")
    subprocess.run(merge_cmd, check=True)

    tmp12.unlink(missing_ok=True)
    tmp21.unlink(missing_ok=True)


def _iterative_clean(streamlines, config, mad_threshold=3.0):
    """
    Iteratively remove streamlines whose length deviates more than
    mad_threshold MADs from the median, up to clean_max_iter iterations.
    """
    max_iter   = config.get("clean_max_iter", 5)
    min_fibers = config.get("clean_min_streamlines", 10)

    lengths = np.array([len(s) for s in streamlines], dtype=float)
    for _ in range(max_iter):
        if len(streamlines) <= min_fibers:
            break
        median = np.median(lengths)
        mad = np.median(np.abs(lengths - median))
        if mad == 0:
            break
        keep = np.abs(lengths - median) <= mad_threshold * mad
        streamlines = [s for s, k in zip(streamlines, keep) if k]
        lengths = lengths[keep]

    return streamlines
