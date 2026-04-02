import argparse
import asyncio
import json
import logging
import sys
import time
import traceback
from pathlib import Path
from typing import Dict, Optional, Set, Type

from agent import APIConfig, BaseAgent, AGENT_REGISTRY
from utils import *


AgentCls = Type[BaseAgent]


def _parse_filter_ids(raw: Optional[str]) -> Optional[Set[str]]:
    if not raw:
        return None
    ids = {item.strip() for item in raw.split(",") if item.strip()}
    return ids or None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified entrypoint to run different WebProber agents."
    )
    parser.add_argument(
        "--agent", required=True, type=str,
        help=(
            "Agent key (built-in: "
            + ", ".join(sorted(AGENT_REGISTRY.keys()))
            + ") or module:Class path (e.g. claude_code, openhands)."
        ),
    )
    parser.add_argument("--data_jsonl_path", required=True, type=str,
                        help="Path to the dataset JSONL file (each line is a record).")
    parser.add_argument("--output_root", required=True, type=str,
                        help="Root directory for all generated outputs.")
    parser.add_argument("--log_root", required=True, type=str,
                        help="Root directory for all log files produced during execution.")
    parser.add_argument("--project_root", type=str, default=None,
                        help="Root directory containing local projects (used when --use_web_url is not set).")
    parser.add_argument("--version", required=True, type=str,
                        help="Version label used to group outputs/logs.")
    parser.add_argument("--base_port", type=int, default=6000,
                        help="Base port offset for local servers (port = base_port + int(record_id[-4:])).")

    parser.add_argument("--api_base_url", required=True, type=str,
                        help="Base URL for API server.")
    parser.add_argument("--api_key", required=True, type=str,
                        help="API key for API server.")
    parser.add_argument("--model", required=True, type=str,
                        help="Model name, e.g., claude-sonnet-4-5.")

    return parser.parse_args()


async def _run_record(
    agent_cls: AgentCls,
    record: Dict[str, str],
    api_config: APIConfig,
    args: argparse.Namespace,
    output_root: Path,
    log_root: Path,
) -> None:
    record_id = record.get("index", "")
    instruction = record.get("instruction", "")

    if not record_id:
        raise ValueError(f"Invalid record without 'index': {record}")
    if not instruction:
        raise ValueError(f"Record {record_id} missing 'instruction'.")
    
    local_project_dir = Path(args.project_root) / record_id
    server_url = f"http://localhost:{args.base_port + int(record_id[-4:])}/"
    # server_url = record.get("webpage_url", f"http://localhost:{args.base_port + int(record_id[-4:])}/")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / record_id
    log_dir = log_root / record_id
    log_file = log_dir / f"{timestamp}-eval.log"

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    log_f = None
    tee_out = None
    tee_err = None

    try:
        probe_agent = agent_cls(
            instruction=instruction,
            api_config=api_config,
            server_url=server_url,
            local_project_dir=local_project_dir,
            output_dir=output_dir,
            event_log_stream=None,
        )
        if probe_agent.result_extracted_path.exists():
            return

        log_dir.mkdir(parents=True, exist_ok=True)
        log_f = open(log_file, "w", encoding="utf-8")
        tee_out = Tee(original_stdout, log_f)
        tee_err = Tee(original_stderr, log_f)
        sys.stdout = tee_out
        sys.stderr = tee_err

        running_info = (
            f"Agent: {agent_cls.__name__}\n"
            f"Index: {record_id}\n"
            f"Instruction: {instruction}\n"
            f"Server URL: {server_url}\n"
            f"Output Dir: {output_dir}\n"
            f"Log Dir: {log_dir}"
        )
        print_boxed(running_info)

        agent = agent_cls(
            instruction=instruction,
            api_config=api_config,
            server_url=server_url,
            local_project_dir=local_project_dir,
            output_dir=output_dir,
            event_log_stream=log_f,
            record=record,
        )
        await agent.run()

    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        if tee_out or tee_err:
            for handler in logging.getLogger().handlers:
                if getattr(handler, "stream", None) is tee_out:
                    handler.stream = original_stdout
                elif getattr(handler, "stream", None) is tee_err:
                    handler.stream = original_stderr
        if log_f:
            try:
                log_f.close()
            except Exception:
                pass


async def main() -> None:
    args = parse_args()

    agent_name = args.agent
    if agent_name in AGENT_REGISTRY:
        agent_cls = AGENT_REGISTRY[agent_name]
    else:
        raise KeyError(f"Unknown agent '{agent_name}'. Available: {', '.join(sorted(AGENT_REGISTRY.keys()))}")

    api_config = APIConfig(base_url=args.api_base_url, api_key=args.api_key, model=args.model)

    data_jsonl_path = Path(args.data_jsonl_path)
    if not data_jsonl_path.exists():
        raise FileNotFoundError(f"Dataset not found: {data_jsonl_path}")

    output_root = Path(args.output_root) / args.version
    output_root.mkdir(parents=True, exist_ok=True)
    log_root = Path(args.log_root) / args.version
    log_root.mkdir(parents=True, exist_ok=True)

    with open(data_jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            record_id = record.get("index") or record.get("id")

            try:
                await _run_record(
                    agent_cls=agent_cls,
                    record=record,
                    api_config=api_config,
                    args=args,
                    output_root=output_root,
                    log_root=log_root,
                )
            except Exception:
                traceback.print_exc()
                sys.exit(1)

    print_green("🎉 All tasks finished.")


if __name__ == "__main__":
    asyncio.run(main())
