"""
Classify optic radiation fibers by pRF eccentricity band.
Each streamline endpoint is mapped to the eccentricity map;
the streamline is assigned to the band matching its V1 endpoint.
"""

import numpy as np
import nibabel as nib
from dipy.io.stateful_tractogram import Space, StatefulTractogram


def _parse_ecc_bins(ecc_bins):
    """
    Parse eccentricity bin string into a list of band dicts.
    Accepts:  "0-3,3-7,15-30,30-90"  or a list of such strings.
    Returns:  [{"name": "ecc_0_3", "min": 0, "max": 3}, ...]
    """
    if isinstance(ecc_bins, list):
        intervals = ecc_bins
    else:
        intervals = [s.strip() for s in str(ecc_bins).split(",")]
    bands = []
    for interval in intervals:
        lo, hi = interval.split("-")
        lo, hi = float(lo), float(hi)
        name = f"ecc_{lo:g}_{hi:g}"
        bands.append({"name": name, "min": lo, "max": hi})
    return bands


def classify_by_eccentricity(fibers_per_hemi, paths, prep, config):
    """
    Returns a nested dict:
      { hemi: { band_name: StatefulTractogram } }
    """
    ecc_img   = nib.load(prep["eccentricity"])
    varea_img = nib.load(prep["varea"])
    ecc_data   = np.squeeze(ecc_img.get_fdata())
    varea_data = np.squeeze(varea_img.get_fdata())

    bands = _parse_ecc_bins(config.get("ecc_bins", "0-3,3-7,7-15,15-30,30-50,50-90"))

    result = {}
    for hemi, sft in fibers_per_hemi.items():
        sft.to_vox()
        streamlines = list(sft.streamlines)
        result[hemi] = {}

        band_streams = {b["name"]: [] for b in bands}

        for sl in streamlines:
            # Sample eccentricity at both endpoints; use the V1 (cortical) end
            ecc_vals = []
            for endpoint in [sl[0], sl[-1]]:
                vox = np.round(endpoint).astype(int)
                vox = np.clip(vox, 0, np.array(ecc_data.shape[:3]) - 1)
                # Only use endpoint if it falls in a visual area (varea > 0)
                if varea_data[vox[0], vox[1], vox[2]] > 0:
                    ecc_vals.append(ecc_data[vox[0], vox[1], vox[2]])

            if not ecc_vals:
                continue
            ecc = np.mean(ecc_vals)

            for band in bands:
                if band["min"] <= ecc < band["max"]:
                    band_streams[band["name"]].append(sl)
                    break

        for band_name, streams in band_streams.items():
            result[hemi][band_name] = StatefulTractogram(
                streams, paths["ref"], Space.VOX
            )

    return result
