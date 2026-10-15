#!/bin/bash
# Test run on HCP sample subject
set -e

DATA=/home/gamorosino/data/optic_radiation_HCP
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── reuse intermediates if already computed ──────────────────────────────────

FIVETT_ARG=""
[ -f "${SCRIPT_DIR}/5tt/5tt.nii.gz" ] && \
    FIVETT_ARG="--fivett ${SCRIPT_DIR}/5tt/5tt.nii.gz"

# Pick up any lmax files produced by a previous dwi2fod run
LMAX_ARGS=""
for order in 2 4 6 8 10 12 14; do
    f="${SCRIPT_DIR}/work/mrtrix/wm_fod_lmax${order}.nii.gz"
    [ -f "$f" ] && LMAX_ARGS="${LMAX_ARGS} --lmax${order} ${f}"
done

# ─────────────────────────────────────────────────────────────────────────────

bash "${SCRIPT_DIR}/main_cli.sh" \
    --dwi          "${DATA}/dwi/dwi.nii.gz" \
    --bvec         "${DATA}/dwi/dwi.bvecs" \
    --bval         "${DATA}/dwi/dwi.bvals" \
    --t1           "${DATA}/t1/t1.nii.gz" \
    --freesurfer   "${DATA}/freesurfer/output" \
    --eccentricity "${DATA}/prf/eccentricity.nii.gz" \
    --varea        "${DATA}/prf/varea.nii.gz" \
    --lgn_lh       "${DATA}/rois/ROIlh.lgn.nii.gz" \
    --lgn_rh       "${DATA}/rois/ROIrh.lgn.nii.gz" \
    --v1_lh        "${DATA}/rois/ROIlh.v1.nii.gz" \
    --v1_rh        "${DATA}/rois/ROIrh.v1.nii.gz" \
    --ecc_bins 0-3,3-7,7-15,15-30,30-90 \
    --n_streamlines 50000 \
    --nthreads     12 \
    ${FIVETT_ARG} \
    ${LMAX_ARGS}
