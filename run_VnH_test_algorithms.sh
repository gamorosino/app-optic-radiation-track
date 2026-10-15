#!/bin/bash
# Run all tracking algorithms on the VnH subject with n_streamlines=5K.
# Each algorithm writes to its own output dir: outputs_<algorithm>/
# Intermediates go to outputs_<algorithm>/work/ (isolated per algorithm).
# iFOD2 and iFOD1 use a finer step (0.2 mm) and wider max angle (50°) to
# better track Meyer's loop.
set -e

DATA=/home/gamorosino/data/optic_radiation_VnH
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# iFOD2 iFOD1 SD_Stream SD_Det FACT Tensor_Det Tensor_Prob dipy_prob dipy_det dipy_eudx dipy_pft
ALGORITHMS=(
    iFOD2
    iFOD1
    SD_Stream
    FACT
    Tensor_Det
    Tensor_Prob
    dipy_prob
    dipy_det
    dipy_eudx
    dipy_pft
)

for ALG in "${ALGORITHMS[@]}"; do
    echo ""
    echo "========================================================"
    echo "  Algorithm: ${ALG}"
    echo "========================================================"

    OUT="${DATA}/app-optic-radiation-track_outputs_${ALG}"
    mkdir -p "${OUT}"

    if [ -f "${OUT}/wmc/classification.mat" ]; then
        echo "  [skip] wmc/classification.mat exists — already completed"
        continue
    fi

    # Reuse 5TT and FOD if already computed by a previous run
    FIVETT_ARG=""
    [ -f "${DATA}/app-optic-radiation-track_outputs_iFOD2/5tt/5tt.nii.gz" ] && \
        FIVETT_ARG="--fivett ${DATA}/app-optic-radiation-track_outputs_iFOD2/5tt/5tt.nii.gz"

    LMAX_ARGS=""
    for order in 2 4 6 8 10 12 14; do
        f="${DATA}/app-optic-radiation-track_outputs_iFOD2/work/mrtrix/wm_fod_lmax${order}.nii.gz"
        [ -f "$f" ] && LMAX_ARGS="${LMAX_ARGS} --lmax${order} ${f}"
    done

    # iFOD2 and iFOD1: finer step + wider angle for Meyer's loop
    STEP_SIZE=0.5
    MAX_ANGLE=45
    if [[ "$ALG" == "iFOD2" || "$ALG" == "iFOD1" ]]; then
        STEP_SIZE=0.2
        MAX_ANGLE=50
    fi

    bash "${SCRIPT_DIR}/main_cli.sh" \
        --dwi          "${DATA}/dwi/dwi.nii.gz" \
        --bvec         "${DATA}/dwi/dwi.bvecs" \
        --bval         "${DATA}/dwi/dwi.bvals" \
        --t1           "${DATA}/t1/t1.nii.gz" \
        --freesurfer   "${DATA}/freesurfer/output" \
        --eccentricity "${DATA}/prf/eccentricity.nii.gz" \
        --varea        "${DATA}/prf/varea.nii.gz" \
        --ecc_bins     "0-3,3-7,7-15,15-30,30-90" \
        --algorithm    "${ALG}" \
        --n_streamlines 5000 \
        --step_size    "${STEP_SIZE}" \
        --max_angle    "${MAX_ANGLE}" \
        --output_dir   "${OUT}" \
        --nthreads     12 \
        ${FIVETT_ARG} \
        ${LMAX_ARGS}

    echo "  [done] ${ALG} → ${OUT}"
done

echo ""
echo "All algorithms complete."
