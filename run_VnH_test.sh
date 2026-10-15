#!/bin/bash
# Test run on VnH subject using DWI seed-based tracking
set -e

DATA=/home/gamorosino/data/optic_radiation_VnH
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${DATA}/app-optic-radiation-track_outputs"
mkdir -p "${OUT}"

FIVETT_ARG=""
[ -f "${OUT}/5tt/5tt.nii.gz" ] && \
    FIVETT_ARG="--fivett ${OUT}/5tt/5tt.nii.gz"

LMAX_ARGS=""
for order in 2 4 6 8 10 12 14; do
    f="${OUT}/work/mrtrix/wm_fod_lmax${order}.nii.gz"
    [ -f "$f" ] && LMAX_ARGS="${LMAX_ARGS} --lmax${order} ${f}"
done

bash "${SCRIPT_DIR}/main_cli.sh" \
    --dwi          "${DATA}/dwi/dwi.nii.gz" \
    --bvec         "${DATA}/dwi/dwi.bvecs" \
    --bval         "${DATA}/dwi/dwi.bvals" \
    --t1           "${DATA}/t1/t1.nii.gz" \
    --freesurfer   "${DATA}/freesurfer/output" \
    --eccentricity "${DATA}/prf/eccentricity.nii.gz" \
    --varea        "${DATA}/prf/varea.nii.gz" \
    --ecc_bins     "0-3,3-7,7-15,15-30,30-90" \
    --output_dir   "${OUT}" \
    --nthreads     12 \
    --n_streamlines     100000 \
    ${FIVETT_ARG} \
    ${LMAX_ARGS}
