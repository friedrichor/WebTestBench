#!/bin/bash
set -x
# ======================================================================
ts=`date +%Y_%m_%d_%H_%M`
log_dir=./logs/scoring_oracle
mkdir -p $log_dir
# ======================================================================
DATASET_PATH=./data/WebTestBench/WebTestBench.jsonl
OUTPUT_ROOT=./outputs

VERSION=claudecode_oracle-gpt-5.1
# ======================================================================
python eval/scoring_oracle.py \
    --dataset_path $DATASET_PATH\
    --output_root $OUTPUT_ROOT \
    --version $VERSION 2>&1 | tee ${log_dir}/log_${ts}_${VERSION}.log
