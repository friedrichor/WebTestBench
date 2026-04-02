import os
import copy
import json
import re
import sys
import time
import subprocess
import shutil
from urllib.parse import urlparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Literal

from utils import *


@dataclass
class APIConfig:
    base_url: str
    api_key: str
    model: str


StageStatus = Literal["running", "complete", "skip", "error"]


class BaseAgent:

    def __init__(
        self,
        instruction: str,
        api_config: APIConfig,
        output_dir: str | Path,
        server_url: str,
        local_project_dir: str | Path,
        event_log_stream: Optional[Any] = None,
    ) -> None:
        self.instruction = instruction
        self.api_config = api_config
        self.server_url = server_url
        self.local_project_dir = local_project_dir

        self.event_log_stream = event_log_stream

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.current_stage: Optional[str] = None

        self.checklist_path = self.output_dir / "checklist.md"
        self.result_path = self.output_dir / "result.md"
        self.result_extracted_path = self.output_dir / "result_extracted.md"
        self.session_meta_path = self.output_dir / "session_meta.json"
    
    async def extract_result_file(self) -> bool:
        stage = "result_extract"
        self.current_stage = stage

        if self._should_skip_stage(self.result_extracted_path, stage):
            return True

        self._write_stage_success(stage, True)
        try:
            content = self._load_file_content(self.result_path)
        except Exception as exc:
            self._mark_stage(stage=stage, status="error", message=f"Failed to read result.md: {exc}")
            return False

        extracted = self._extract_test_result_section(content)
        if extracted is None or extracted.strip() == "":
            if self.result_path.exists():
                timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
                # result 
                error_path = self.result_path.with_name(f"result-error_{timestamp}.md")
                self.result_path.rename(error_path)
                # session
                session_error_path = self.session_meta_path.with_name(f"session_meta-error_{timestamp}.json")
                shutil.copy2(self.session_meta_path, session_error_path)
            self._mark_stage(stage=stage, status="error", message="Missing '# Test Result' section.")
            return False

        self.result_extracted_path.write_text(extracted, encoding="utf-8")
        if self._verify_output_file(self.result_extracted_path):
            self._emit_file_event(stage, self.result_extracted_path)
            return True
        else:
            self._mark_stage(stage=stage, status="error", message=f"Stage {stage} did not produce {self.result_extracted_path}.")
            return False

    def _extract_test_result_section(self, content: str) -> str:
        lines = content.splitlines()
        start_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith("# Test Result"):
                start_idx = i
                break
        if start_idx is None:
            return ""

        extracted_lines = lines[start_idx:]
        last_item_idx = None
        for i, line in enumerate(extracted_lines):
            if line.lstrip().startswith("- [") and "]" in line:
                last_item_idx = i

        if last_item_idx is None:
            trimmed = "\n".join(extracted_lines).strip()
            return f"{trimmed}\n" if trimmed else ""

        end_idx = last_item_idx + 1
        while end_idx < len(extracted_lines):
            line = extracted_lines[end_idx]
            if line.strip() == "" or line[0].isspace():
                end_idx += 1
                continue
            break

        trimmed = "\n".join(extracted_lines[:end_idx]).strip()
        return f"{trimmed}\n" if trimmed else ""

    # ------------------------------------------------------------------ #
    # Server Deployment
    # ------------------------------------------------------------------ #

    async def server_deploy(self):
        """
        Ensure project dev server is up.

        Rules:
        - Kill previous dev server on port 5173.
        - If `dev_server.log` already exists and curl succeeds, we skip.
        - Otherwise install deps and run dev server in background.
        """
        stage = "server_deploy"
        if not self.server_url.startswith('http://localhost'):
            self._mark_stage(stage=stage, status="skip", message=f"⏭️ Skipping {stage}: server_url is an online webpage, skipping server deployment: {self.server_url}")
            return True

        if not self.local_project_dir:
            self._mark_stage(stage=stage, status="error", message=f"{stage}: local_project_dir is not set.")
            return False
        
        self._mark_stage(stage=stage, status="running", message="🚀 Starting Server Deployment ...")
        
        # Extract port from server_url
        parsed_url = urlparse(self.server_url)
        port = parsed_url.port

        self._kill_exist_port(port)
        self._deploy_local_server(port)

        return True

    def _kill_exist_port(self, port: int, stage: str = "server_deploy") -> None:
        """Kill old dev server process on the given port if it exist."""
        self._mark_stage(stage=stage, message=f"🧹 Checking old dev server on port {port} ...")
        try:
            # Kill the process running on the extracted port
            result = subprocess.run(
                f"lsof -ti:{port} | xargs kill -9",
                shell=True, capture_output=True, text=True,
            )
            if result.returncode == 0:
                self._mark_stage(stage=stage, message=f"🧹 Killed process on port {port}.")
            else:
                self._mark_stage(stage=stage, message=f"✅ No process found on port {port}.")
                pass  # It's okay if nothing was running on the port
        except Exception as e:
            self._mark_stage(stage=stage, status="error", message=f"Failed to kill old server process: {e}")
    
    def _deploy_local_server(self, port: int, stage: str = "server_deploy"):
        """Start dev server in background on the given port and wait until it responds."""
        project_dir = Path(self.local_project_dir)
        if not project_dir.exists():
            raise FileNotFoundError(f"local_project_dir not found: {project_dir}")
        
        self._mark_stage(stage=stage, message=f"📦 Installing dependencies (npm install) in {project_dir} ...")
        subprocess.run(["npm", "install"], cwd=str(project_dir), check=True)

        log_path = self.output_dir / "dev_server.log"
        self._mark_stage(stage=stage, message=f"🚀 Starting dev server on port {port} (log: {log_path}) ...")

        self._dev_server_log_handle = open(log_path, "w", encoding="utf-8")
        self.dev_server_process = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", str(port)],
            cwd=str(project_dir), stdout=self._dev_server_log_handle, stderr=subprocess.STDOUT, preexec_fn=os.setsid,
        )
        
        # step 3: wait for server to respond
        print("⏳ Waiting for server to start...")
        time.sleep(20)
        for _ in range(60):  # 60 sec
            time.sleep(1)
            try:
                response = subprocess.run(
                    ["curl", "-s", self.server_url],
                    capture_output=True, timeout=2
                )
                if response.returncode == 0:
                    self._mark_stage(stage=stage, status="complete", message=f"✅ Server is ready at {self.server_url}")
                    self._mark_stage(stage=stage, message=f"✅ Dev server started (PID: {self.dev_server_process.pid})")
                    return True
            except:
                continue
        
        raise RuntimeError(f"Dev server failed to start within 60s. See log: {log_path}")

    def kill_local_server(self) -> None:
        """Cleanup for local dev server."""
        if not self.server_url.startswith("http://localhost"):
            return

        self._kill_exist_port(urlparse(self.server_url).port, stage="server_cleanup")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _log_instruction(self) -> None:
        """Persist and display the input instruction for traceability."""
        print("=" * 20, "Instruction", "=" * 20)
        print(self.instruction)
        print("=" * 50)
    
    def _should_skip_stage(self, file_path: Path, stage: str) -> bool:
        """Skip a stage if its output file already exists."""
        if file_path.exists():
            self._mark_stage(stage=stage, status="skip", message=f"⏭️ Skipping {stage}: output already exists at {file_path}.")
            self._emit_file_event(stage, file_path)
            return True
        return False

    def _handle_message(self, message, stage: str):
        """Emit structured events while streaming assistant messages and tool usage."""
        pass

    def _mark_stage(self, stage: str, status: Optional[StageStatus] = None, message: Optional[str] = None) -> None:
        """Emit structured stage updates."""
        self.current_stage = stage
        if status is None:
            status = "running"

        if message:
            print_red(message) if status == "error" else print(message)

        self._emit_event(type_name="stage_status", stage=stage, status=status, message=message)
    
    def _emit_event(self, type_name: str, stage: str, status: Optional[StageStatus] = None,
                    message: Optional[str] = None, payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a single structured event.
        {
            "type": <type name>,
            "stage": <stage name>,
            "status": <optional status string>,
            "message": <optional human readable string>,
            "payload": <optional structured data dict>
        }
        - Console: truncated content for readability (written directly to the real stdout).
        - Log file: full content (appended to `event_log_path`).
        """
        event_stage = stage or self.current_stage
        base_event: Dict[str, Any] = {
            "type": type_name, "stage": event_stage, "status": status, "message": message, "payload": payload
        }

        if status == "error":
            self._write_stage_success(stage, False)
        else:
            self._write_stage_success(stage, True)

        display_event = self._to_display_event(base_event)

        # Console-friendly event (bypass Tee to avoid duplicating truncated content in logs)
        try:
            sys.__stdout__.write(f"__EVENT__ {json.dumps(display_event, ensure_ascii=False)}\n")
            sys.__stdout__.flush()
        except Exception as exc:
            print_red(f"Failed to encode event {display_event}: {exc}")

        # Full event log for later debugging
        try:
            self.event_log_stream.write("__EVENT__ " + json.dumps(base_event, ensure_ascii=False, indent=2) + "\n")
            self.event_log_stream.flush()
        except Exception as exc:
            print_red(f"Failed to write full event: {exc}")
    
    def _to_display_event(self, event: Dict[str, Any], limit: int = 200) -> Dict[str, Any]:
        """Return a console-friendly copy of the event with long strings truncated."""

        def truncate(value: Any) -> Any:
            if isinstance(value, str) and len(value) > limit:
                truncated = value[:limit]
                truncated = truncated.rsplit(" ", 1)[0] or truncated
                return f"{truncated} ... (truncated)"
            if isinstance(value, list):
                return [truncate(item) for item in value]
            if isinstance(value, dict):
                return {k: truncate(v) for k, v in value.items()}
            return value

        return truncate(copy.deepcopy(event))

    def _emit_file_event(self, stage: str, path: Path) -> None:
        """Emit a file event with a predictable payload."""
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:
            self._emit_event(
                type_name="file_generate", stage=stage, status="error",
                message=f"Unable to read generated file {path}: {exc}",
            )
            return

        self._emit_event(
            type_name="file_generate", stage=stage, status="complete",
            payload={"file": {"name": path.name, "path": str(path), "content": content}},
        )

    def _write_stage_success(self, stage: str, success: bool) -> None:
        session_meta: Dict[str, Any] = {}
        if self.session_meta_path.exists():
            try:
                session_meta = json.loads(self.session_meta_path.read_text(encoding="utf-8"))
            except Exception as exc:
                print_red(f"Failed to read session meta from {self.session_meta_path}: {exc}")
        if not isinstance(session_meta, dict):
            session_meta = {}

        stage_success = session_meta.get("stage_success")
        if not isinstance(stage_success, dict):
            stage_success = {}
        current_value = stage_success.get(stage)
        if isinstance(current_value, bool):
            stage_success[stage] = current_value and bool(success)
        else:
            stage_success[stage] = bool(success)
        session_meta["stage_success"] = stage_success
        try:
            self.session_meta_path.write_text(
                json.dumps(session_meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            print_red(f"Failed to write session meta to {self.session_meta_path}: {exc}")

    def _verify_output_file(self, file_path: Path) -> bool:
        """Verify that an output file exists and is non-empty."""
        if not file_path.exists():
            return False
        
        try:
            size = file_path.stat().st_size
            return size > 0
        except Exception as e:
            print_red(f"Error verifying file {file_path}: {e}")
            return False
    
    def _load_file_content(self, file_path: Path) -> str:
        """Load the complete content of a file."""
        return file_path.read_text(encoding="utf-8")
        
    def _load_file_until_marker(self, filepath: Path, marker: str) -> str:
        """Load file content up to a marker line (exclusive). Returns full file if the marker is missing."""
        if not filepath.exists():
            print_red(f"⚠️  File not found: {filepath}")
            return ""
        
        content_lines = []
        with filepath.open('r', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith(marker):
                    break
                content_lines.append(line)
        
        return ''.join(content_lines)
    
    def write_markdown(self, path: Path, text: str) -> None:
        """Persist markdown content, unwrapping ```markdown fences when present."""
        m = re.search(r"```(?:markdown|md)\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        content = m.group(1).strip() if m else text.strip()
        path.write_text(content, encoding="utf-8")

    def _has_required_checklist(self, content: str | None) -> bool:
        if content:
            for line in content.splitlines():
                if line.strip().startswith("# Test Checklist"):
                    return True
        return False
    
    def _has_required_result(self, content: str | None) -> bool:
        if content:
        #     for line in content.splitlines():
        #         if line.strip().startswith("# Test Result"):
        #             return True
        # return False
            for line in content.splitlines():
                s = line.strip()
                if s.startswith("#") and s.lstrip("#").strip().startswith("Test Result"):
                    return True
        return False
    
    
