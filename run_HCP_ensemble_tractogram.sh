#!/bin/bash
# Test run using the HCP occipital ensemble template tractogram
set -e

DATA=/home/gamorosino/data/optic_radiation_HCP
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

FIVETT_ARG=""
[ -f "${SCRIPT_DIR}/5tt/5tt.nii.gz" ] && \
    FIVETT_ARG="--fivett ${SCRIPT_DIR}/5tt/5tt.nii.gz"

bash "${SCRIPT_DIR}/main_cli.sh" \
    --tractogram   "/home/gamorosino/data/templates/visual_areas_tractograms/occipital_template_HCP_ensemble.tck" \
    --t1           "${DATA}/t1/t1.nii.gz" \
    --freesurfer   "${DATA}/freesurfer/output" \
    --eccentricity "${DATA}/prf/eccentricity.nii.gz" \
    --varea        "${DATA}/prf/varea.nii.gz" \
    --lgn_lh       "${DATA}/rois/ROIlh.lgn.nii.gz" \
    --lgn_rh       "${DATA}/rois/ROIrh.lgn.nii.gz" \
    --v1_lh        "${DATA}/rois/ROIlh.v1.nii.gz" \
    --v1_rh        "${DATA}/rois/ROIrh.v1.nii.gz" \
    --ecc_bins     "0-3,3-7,7-15,15-30,30-90" \
    --nthreads     12 \
    ${FIVETT_ARG}
