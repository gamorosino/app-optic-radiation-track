#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================================
# Usage
# ============================================================================

usage() {
cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Required inputs (dwi OR csd required):
  --dwi PATH            DWI image (.nii.gz, required unless CSD is provided)
  --bvec PATH           Gradient directions file (.bvec, required unless CSD is provided)
  --bval PATH           Gradient b-values file (.bval, required unless CSD is provided)
  --t1 PATH             T1-weighted anatomical image (.nii.gz)
  --freesurfer PATH     FreeSurfer output directory
  --eccentricity PATH   pRF eccentricity map (.nii.gz)
  --varea PATH          pRF visual area map (.nii.gz)
  --lgn_lh PATH         Left hemisphere LGN ROI (.nii.gz, optional — auto-extracted from thalamic nuclei)
  --lgn_rh PATH         Right hemisphere LGN ROI (.nii.gz, optional — auto-extracted from thalamic nuclei)
  --v1_lh PATH          Left hemisphere V1 ROI (.nii.gz, optional — auto-extracted from varea==1)
  --v1_rh PATH          Right hemisphere V1 ROI (.nii.gz, optional — auto-extracted from varea==1)
  --fivett PATH         5-tissue-type image (.nii.gz, optional — computed from T1 if absent)
  --response PATH       CSD response function file (response.txt, optional)
  --lmax2 PATH          CSD lmax2 FOD image (.nii.gz, optional)
  --lmax4 PATH          CSD lmax4 FOD image (.nii.gz, optional)
  --lmax6 PATH          CSD lmax6 FOD image (.nii.gz, optional)
  --lmax8 PATH          CSD lmax8 FOD image (.nii.gz, optional)
  --lmax10 PATH         CSD lmax10 FOD image (.nii.gz, optional)
  --lmax12 PATH         CSD lmax12 FOD image (.nii.gz, optional)
  --lmax14 PATH         CSD lmax14 FOD image (.nii.gz, optional)
  --lmax N              Force a specific lmax order (default: highest available)

Tracking options:
  --tractogram PATH     Pre-computed whole-brain tractogram (.tck); skips tckgen entirely
  --algorithm STR       Tracking algorithm (default: iFOD2)
                          MRtrix3: iFOD2, iFOD1, SD_Stream, FACT, Tensor_Det, Tensor_Prob
                          DIPY   : dipy_prob, dipy_det, dipy_eudx
  --seed_based          Seed from LGN, include V1 as waypoint (default: true)
  --no_seed_based       Whole-brain ACT tracking, filter afterward
  --n_streamlines N          Target number of streamlines (default: 50000)
  --seed_dynamic        Use dynamic seeding (default: true)
  --no_seed_dynamic     Disable dynamic seeding
  --sift2               Apply SIFT2 weights (default: true)
  --no_sift2            Disable SIFT2
  --pft_back_dist N     PFT back-tracking distance in mm (default: 2, dipy_pft only)
  --pft_front_dist N    PFT front-tracking distance in mm (default: 1, dipy_pft only)
  --pft_particles N     Particles per streamline (default: 15, dipy_pft only)
  --pft_max_cross N     Max crossings per voxel (default: 1, dipy_pft only)
  --step_size N         Tracking step size in mm (default: 0.2)
  --max_angle N         Maximum turning angle in degrees (default: 45)
  --min_length N        Minimum streamline length in mm (default: 10)
  --max_length N        Maximum streamline length in mm (default: 250)

Segmentation options:
  --hemispheres STR     Hemispheres to process, comma-separated (default: lh,rh)
  --ecc_bins STR        Eccentricity intervals as lo-hi pairs, e.g. "0-3,3-7,15-30,30-90" (default: 0-3,3-7,7-15,15-30,30-50,50-90)
  --clean_streamlines        Apply iterative fiber cleaning (default: true)
  --no_clean_streamlines     Disable fiber cleaning
  --clean_max_iter N    Maximum cleaning iterations (default: 5)
  --clean_min_streamlines N  Minimum fibers before stopping cleaning (default: 10)

5ttgen options (used only when --fivett is not provided):
  --nthreads N          Number of threads for MRtrix3 commands (default: 1)

Other:
  --output_dir PATH     Root directory for all outputs (default: . — use for local runs)
  --work_dir PATH       Directory for intermediate files (default: work inside output_dir)
  --force               Recompute all intermediate files (default: skip existing)
  -h, --help            Show this help and exit
EOF
}

# ============================================================================
# Defaults
# ============================================================================

dwi=""; bvec=""; bval=""
t1=""; freesurfer=""
eccentricity=""; varea=""
lgn_lh=""; lgn_rh=""; v1_lh=""; v1_rh=""
fivett=""
response=""
lmax2=""; lmax4=""; lmax6=""; lmax8=""
lmax10=""; lmax12=""; lmax14=""
lmax=""

tractogram=""
algorithm="iFOD2"
seed_based=true
n_streamlines=5000
seed_dynamic=true
sift2=false
step_size=0.5
pft_back_dist=2
pft_front_dist=1
pft_particles=15
pft_max_cross=1
max_angle=45
min_length=10
max_length=250

hemispheres="lh,rh"
ecc_bins="0-3,3-7,7-15,15-30,30-50,50-90"
clean_streamlines=false
clean_max_iter=5
clean_min_streamlines=10
premask=false
output_dir="."
work_dir=""
nthreads=1
force=false

# ============================================================================
# Parse arguments
# ============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dwi)              dwi="$2";              shift 2 ;;
        --bvec)             bvec="$2";             shift 2 ;;
        --bval)             bval="$2";             shift 2 ;;
        --t1)               t1="$2";               shift 2 ;;
        --freesurfer)       freesurfer="$2";       shift 2 ;;
        --eccentricity)     eccentricity="$2";     shift 2 ;;
        --varea)            varea="$2";            shift 2 ;;
        --lgn_lh)           lgn_lh="$2";           shift 2 ;;
        --lgn_rh)           lgn_rh="$2";           shift 2 ;;
        --v1_lh)            v1_lh="$2";            shift 2 ;;
        --v1_rh)            v1_rh="$2";            shift 2 ;;
        --fivett)           fivett="$2";    shift 2 ;;
        --response)         response="$2"; shift 2 ;;
        --lmax2)            lmax2="$2";    shift 2 ;;
        --lmax4)            lmax4="$2";    shift 2 ;;
        --lmax6)            lmax6="$2";    shift 2 ;;
        --lmax8)            lmax8="$2";    shift 2 ;;
        --lmax10)           lmax10="$2";   shift 2 ;;
        --lmax12)           lmax12="$2";   shift 2 ;;
        --lmax14)           lmax14="$2";   shift 2 ;;
        --lmax)             lmax="$2";     shift 2 ;;
        --tractogram)       tractogram="$2";        shift 2 ;;
        --algorithm)        algorithm="$2";        shift 2 ;;
        --seed_based)       seed_based=true;       shift   ;;
        --no_seed_based)    seed_based=false;      shift   ;;
        --n_streamlines)    n_streamlines="$2";    shift 2 ;;
        --seed_dynamic)     seed_dynamic=true;     shift   ;;
        --no_seed_dynamic)  seed_dynamic=false;    shift   ;;
        --sift2)            sift2=true;            shift   ;;
        --no_sift2)         sift2=false;           shift   ;;
        --pft_back_dist)    pft_back_dist="$2";    shift 2 ;;
        --pft_front_dist)   pft_front_dist="$2";   shift 2 ;;
        --pft_particles)    pft_particles="$2";    shift 2 ;;
        --pft_max_cross)    pft_max_cross="$2";    shift 2 ;;
        --step_size)        step_size="$2";        shift 2 ;;
        --max_angle)        max_angle="$2";        shift 2 ;;
        --min_length)       min_length="$2";       shift 2 ;;
        --max_length)       max_length="$2";       shift 2 ;;
        --hemispheres)      hemispheres="$2";      shift 2 ;;
        --ecc_bins)         ecc_bins="$2";         shift 2 ;;
        --clean_streamlines)     clean_streamlines=true;     shift   ;;
        --no_clean_streamlines)  clean_streamlines=false;    shift   ;;
        --clean_max_iter)   clean_max_iter="$2";   shift 2 ;;
        --clean_min_streamlines) clean_min_streamlines="$2"; shift 2 ;;
        --premask)          premask=true;          shift   ;;
        --output_dir)       output_dir="$2";        shift 2 ;;
        --work_dir)         work_dir="$2";          shift 2 ;;
        --nthreads)         nthreads="$2";         shift 2 ;;
        --force)            force=true;            shift   ;;
        -h|--help)          usage; exit 0 ;;
        *) echo "[ERROR] Unknown option: $1" >&2; usage; exit 1 ;;
    esac
done

# ============================================================================
# Validate required inputs
# ============================================================================

missing=()
for var in t1 freesurfer eccentricity varea; do
    [[ -z "${!var}" ]] && missing+=("--${var}")
done
# lgn/v1 ROIs are optional — auto-generated from thalamic nuclei + varea if absent

# dwi/bvec/bval required only when no CSD lmax is provided
has_csd=false
for lmax_var in lmax2 lmax4 lmax6 lmax8 lmax10 lmax12 lmax14; do
    [[ -n "${!lmax_var}" ]] && has_csd=true && break
done

if [[ "$has_csd" == "false" ]] && [[ -z "$tractogram" ]]; then
    for var in dwi bvec bval; do
        [[ -z "${!var}" ]] && missing+=("--${var}")
    done
fi

if [[ ${#missing[@]} -gt 0 ]]; then
    echo "[ERROR] Missing required inputs: ${missing[*]}" >&2
    usage
    exit 1
fi

# ============================================================================
# Build config.json
# ============================================================================

json_str()  { [[ -n "$1" ]] && printf '"%s"' "$1" || printf 'null'; }
json_bool() { printf '%s' "$1"; }

# Convert comma-separated hemispheres to JSON array
hemi_array=$(echo "$hemispheres" | jq -Rc 'split(",")')


config=$(jq -n \
    --argjson dwi            "$(json_str "$dwi")" \
    --argjson bvec           "$(json_str "$bvec")" \
    --argjson bval           "$(json_str "$bval")" \
    --argjson t1             "$(json_str "$t1")" \
    --argjson freesurfer     "$(json_str "$freesurfer")" \
    --argjson eccentricity "$(json_str "$eccentricity")" \
    --argjson varea        "$(json_str "$varea")" \
    --argjson lgn_lh         "$(json_str "$lgn_lh")" \
    --argjson lgn_rh         "$(json_str "$lgn_rh")" \
    --argjson v1_lh          "$(json_str "$v1_lh")" \
    --argjson v1_rh          "$(json_str "$v1_rh")" \
    --argjson fivett    "$(json_str "$fivett")" \
    --argjson response  "$(json_str "$response")" \
    --argjson lmax2     "$(json_str "$lmax2")" \
    --argjson lmax4     "$(json_str "$lmax4")" \
    --argjson lmax6     "$(json_str "$lmax6")" \
    --argjson lmax8     "$(json_str "$lmax8")" \
    --argjson lmax10    "$(json_str "$lmax10")" \
    --argjson lmax12    "$(json_str "$lmax12")" \
    --argjson lmax14    "$(json_str "$lmax14")" \
    --argjson lmax      "$(json_str "$lmax")" \
    --argjson tractogram  "$(json_str "$tractogram")" \
    --argjson algorithm   "$(json_str "$algorithm")" \
    --argjson seed_based  "$(json_bool "$seed_based")" \
    --argjson n_streamlines "$n_streamlines" \
    --argjson seed_dynamic "$(json_bool "$seed_dynamic")" \
    --argjson sift2          "$(json_bool "$sift2")" \
    --argjson pft_back_dist  "$pft_back_dist" \
    --argjson pft_front_dist "$pft_front_dist" \
    --argjson pft_particles  "$pft_particles" \
    --argjson pft_max_cross  "$pft_max_cross" \
    --argjson step_size      "$step_size" \
    --argjson max_angle      "$max_angle" \
    --argjson min_length     "$min_length" \
    --argjson max_length     "$max_length" \
    --argjson hemispheres    "$hemi_array" \
    --argjson ecc_bins       "$(json_str "$ecc_bins")" \
    --argjson clean_streamlines   "$(json_bool "$clean_streamlines")" \
    --argjson clean_max_iter "$clean_max_iter" \
    --argjson clean_min_streamlines "$clean_min_streamlines" \
    --argjson premask        "$(json_bool "$premask")" \
    --argjson output_dir     "$(json_str "$output_dir")" \
    --argjson work_dir       "$(json_str "${work_dir:-${output_dir}/work}")" \
    --argjson nthreads       "$nthreads" \
    --argjson force          "$(json_bool "$force")" \
    '{
        dwi:              $dwi,
        bvec:             $bvec,
        bval:             $bval,
        t1:               $t1,
        freesurfer:       $freesurfer,
        eccentricity:          $eccentricity,
        varea:        $varea,
        lgn_lh:           $lgn_lh,
        lgn_rh:           $lgn_rh,
        v1_lh:            $v1_lh,
        v1_rh:            $v1_rh,
        fivett:    $fivett,
        response:  $response,
        lmax2:     $lmax2,
        lmax4:     $lmax4,
        lmax6:     $lmax6,
        lmax8:     $lmax8,
        lmax10:    $lmax10,
        lmax12:    $lmax12,
        lmax14:    $lmax14,
        lmax:      $lmax,
        tractogram:    $tractogram,
        algorithm:     $algorithm,
        seed_based:    $seed_based,
        n_streamlines: $n_streamlines,
        seed_dynamic:  $seed_dynamic,
        sift2:            $sift2,
        pft_back_dist:    $pft_back_dist,
        pft_front_dist:   $pft_front_dist,
        pft_particles:    $pft_particles,
        pft_max_cross:    $pft_max_cross,
        step_size:        $step_size,
        max_angle:        $max_angle,
        min_length:       $min_length,
        max_length:       $max_length,
        hemispheres:      $hemispheres,
        ecc_bins:         $ecc_bins,
        clean_streamlines:     $clean_streamlines,
        clean_max_iter:   $clean_max_iter,
        clean_min_streamlines: $clean_min_streamlines,
        premask:          $premask,
        output_dir:       $output_dir,
        work_dir:         $work_dir,
        nthreads:         $nthreads,
        force:            $force
    }'
)

echo "$config" > "${SCRIPT_DIR}/config.json"
echo "[INFO] config.json written:"
echo "$config" | sed 's/^/  /'
echo ""

# ============================================================================
# Run main
# ============================================================================

bash "${SCRIPT_DIR}/main"
