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
BASE_PORT=6000

python eval/run_agent.py \
    --agent claude_code \
    --data_jsonl_path $DATA_JSONL_PATH \
    --project_root $PROJECT_ROOT \
    --output_root $OUTPUT_ROOT \
    --log_root $LOG_ROOT \
    --version $VERSION \
    --base_port $BASE_PORT \
    --api_base_url $API_BASE_URL \
    --api_key $API_KEY \
    --model $MODEL 
