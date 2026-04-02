#!/bin/bash
set -euo pipefail
set -x
# ======================================================================
API_BASE_URL=XXX  # e.g., https://openrouter.ai/api
API_KEY=XXX       # e.g., sk-or-v1-XXX
MODEL=XXX         # e.g., z-ai/glm-5
VERSION=claudecode-${MODEL##*/}
# ======================================================================
export ANTHROPIC_DEFAULT_SONNET_MODEL=$MODEL
export ANTHROPIC_DEFAULT_OPUS_MODEL=$MODEL
export ANTHROPIC_DEFAULT_HAIKU_MODEL=$MODEL
# ======================================================================
DATA_JSONL_PATH=./data/WebTestBench/WebTestBench.jsonl
PROJECT_ROOT=./data/WebTestBench/web_applications
OUTPUT_ROOT=./outputs
LOG_ROOT=./logs/eval
# ======================================================================
# Parallel settings
JOBS=8
BASE_PORT=6000

num_lines=$(wc -l < $DATA_JSONL_PATH)
if [ $num_lines -le 0 ]; then
  echo Empty dataset: $DATA_JSONL_PATH
  exit 1
fi

lines_per_job=$(( (num_lines + JOBS - 1) / JOBS ))
split_prefix=${DATA_JSONL_PATH}.part_

split -l $lines_per_job -d -a 3 $DATA_JSONL_PATH $split_prefix
trap 'rm -f ${split_prefix}*' EXIT

idx=0
for part in ${split_prefix}*; do
  if [ ! -s $part ]; then
    continue
  fi
  echo Running shard $part with base_port=$BASE_PORT
  python eval/run_agent.py \
    --agent claude_code \
    --data_jsonl_path $part \
    --project_root $PROJECT_ROOT \
    --output_root $OUTPUT_ROOT \
    --log_root $LOG_ROOT \
    --version $VERSION \
    --base_port $BASE_PORT \
    --api_base_url $API_BASE_URL \
    --api_key $API_KEY \
    --model $MODEL &
  idx=$((idx + 1))
done

wait