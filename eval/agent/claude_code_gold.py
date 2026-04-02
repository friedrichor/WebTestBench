import os
import json
import time
from pathlib import Path
from typing import Any, Callable, Optional, Dict, List
from dataclasses import asdict
from claude_agent_sdk import (
    query, ClaudeAgentOptions, 
    UserMessage, AssistantMessage, ResultMessage,
    TextBlock, ToolUseBlock, ToolResultBlock
)

from agent import APIConfig, BaseAgent
from prompt import USER_PROMPT
from tools import PlaywrightTools
from utils import *


class ClaudeCodeWebTester_Gold(BaseAgent):

    def __init__(
        self,
        instruction: str,
        api_config: APIConfig,
        server_url: str,
        local_project_dir: Optional[str] = None,
        output_dir: str | Path = "./output/results",
        event_log_stream: Optional[Any] = None,
        **kwargs,
    ) -> None:
        super().__init__(
            instruction=instruction,
            api_config=api_config,
            output_dir=output_dir,
            server_url=server_url,
            local_project_dir=local_project_dir,
            event_log_stream=event_log_stream,
        )

        self.result_path = self.output_dir / "result.md"
        self.message_class_counts: Dict[str, Dict[str, Any]] = {}
        self.session_success = True
        self.recent_assistant_text_blocks: Dict[str, List[str]] = {}
        self.record = kwargs.get("record")
        # defect detection stage setting
        self.max_turns = 150

        self.cwd_dir = "./claude_code_cwd"
        os.makedirs(self.cwd_dir, exist_ok=True)

    async def run(self) -> bool:
        """Run checklist generation then execution."""
        if self._should_skip_stage(self.result_extracted_path, stage="eval"):
            return True
        
        self._log_instruction()

        start_ts = time.time()
        stage_sequence = [
            self.server_deploy,
            self.checklist_generation,
            self.defect_detection,
            self.extract_result_file,
        ]

        success = True
        try:
            for stage_callable in stage_sequence:
                stage_result = await stage_callable()
                if stage_result is False:
                    success = False
                    break
        finally:
            end_ts = time.time()
            duration = end_ts - start_ts
            self.kill_local_server()

        completion_message = "✅ Web Testing completed." if success else "❌ Web Testing encountered errors."
        (print_green if success else print_red)(completion_message)
        self._emit_event(
            type_name="pipeline_status", stage="finish", status="complete" if success else "error", message=completion_message,
            payload=dict(
                start_time=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_ts)),
                end_time=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_ts)),
                duration=time.strftime("%H:%M:%S", time.gmtime(int(round(duration or 0)))),
            )
        )
        return success

    async def checklist_generation(self) -> bool:
        stage = "checklist_generation"
        target_file = self.checklist_path
        self.current_stage = stage

        if self._should_skip_stage(target_file, stage):
            return True

        self._write_stage_success(stage, True)
        self._mark_stage(stage=stage, status="running", message="🚀 Building checklist from record ...")

        record = self.record
        checklist_items = record.get("checklist", [])
        if not isinstance(checklist_items, list) or not checklist_items:
            self._mark_stage(stage=stage, status="error", message="Record missing checklist items.")
            return False

        class_map = {
            "functionality": ("Functionality", "FT"),
            "constraint": ("Constraint", "CS"),
            "interaction": ("Interaction", "IX"),
            "content": ("Content", "CT"),
        }
        class_order = ["functionality", "constraint", "interaction", "content"]

        lines: List[str] = ["# Test Checklist", ""]
        for class_key in class_order:
            section_items = [item for item in checklist_items if item.get("class") == class_key]
            if not section_items:
                continue
            section_title, prefix = class_map[class_key]
            lines.append(f"## {section_title}")
            for idx, item in enumerate(section_items, start=1):
                content = str(item.get("content", "")).strip()
                if not content:
                    continue
                content = " ".join(content.splitlines()).strip()
                lines.append(f"- [ ] {prefix}-{idx:02d}: {content}")
                lines.append("")
            if lines[-1] == "":
                lines.pop()
            lines.append("")

        if lines and lines[-1] == "":
            lines.pop()

        standard_checklist = "\n".join(lines).strip()
        if not self._has_required_checklist(standard_checklist):
            self._mark_stage(stage=stage, status="error", message=f"Stage {stage} produced invalid checklist content",)
            return False

        self.write_markdown(target_file, standard_checklist)

        if self._verify_output_file(target_file):
            self._emit_file_event(stage, target_file)
            print_green("✅ Checklist Generation Completed.")
            return True
        else:
            self._mark_stage(stage=stage, status="error", message=f"Stage {stage} did not produce {target_file}.")
            return False

    async def defect_detection(self) -> bool:
        stage = "defect_detection"
        target_file = self.result_path
        self.current_stage = stage

        if self._should_skip_stage(target_file, stage):
            return True

        if not self.checklist_path.exists():
            self._mark_stage(stage=stage, status="error", message="Checklist not found; cannot execute actions.")
            return False

        self._write_stage_success(stage, True)
        self._mark_stage(stage=stage, status="running", message="🚀 Defect Detection ...")
        checklist_md = self._load_file_content(self.checklist_path)
        prompt = USER_PROMPT["test_based_gold"].substitute(
            instruction=self.instruction, server_url=self.server_url, checklist=checklist_md,
        )
        options = self._get_browser_agent_options(max_turns=100)

        async for message in query(prompt=prompt, options=options):
            self._log_session_id(message, session_name=stage, stage=stage, prompt=prompt)
            self._handle_message(message, stage=stage)
            if isinstance(message, ResultMessage):
                result_message = message.result
                num_turns = message.num_turns

        if num_turns > self.max_turns:
            self.write_markdown(target_file, "")
            self.write_markdown(self.result_extracted_path, "")
        else:
            final_result, from_result_message = self._extract_final_result(result_message, stage=stage)
            self._record_final_result_source(stage, from_result_message)
            self.write_markdown(target_file, final_result)
            if final_result == "":
                self._mark_stage(stage=stage, status="error", message=f"Stage {stage} produced invalid result content; missing '# Test Result'.",)
                return False

        if self._verify_output_file(target_file):
            self._emit_file_event(stage, target_file)
            print_green("✅ Action Execution Completed.")
            return True
        else:
            self._mark_stage(stage=stage, status="error", message=f"Stage {stage} did not produce {target_file}.")
            return False
    

    # ------------------------------------------------------------------ #
    # Conversation Helpers
    # ------------------------------------------------------------------ #

    def _log_session_id(self, message, session_name: str, stage: str, prompt: str, extra_meta: Optional[Dict] = None):
        if hasattr(message, "subtype") and message.subtype == "init":
            session_id = message.data.get("session_id")
            session_meta: Dict[str, Any] = {}
            if self.session_meta_path.exists():
                session_meta = json.loads(self.session_meta_path.read_text(encoding="utf-8"))
            if not isinstance(session_meta, dict):
                session_meta = {}

            session_entry = {"stage": stage, "session_id": session_id, "user_prompt": prompt}
            if extra_meta and isinstance(extra_meta, dict):
                session_entry.update(extra_meta)

            session_meta[session_name] = session_entry
            self.session_meta_path.write_text(json.dumps(session_meta, ensure_ascii=False, indent=2), encoding="utf-8")

            self._emit_event(
                type_name="log_session_id", stage=stage, payload=dict(session_id=session_id, extra_meta=extra_meta)
            )
    
    def _handle_message(self, message, stage: str):
        """Emit structured events while streaming assistant messages and tool usage."""
        self._record_message_count(message, stage=stage)

        text_content = ""
        if isinstance(message, UserMessage):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    self._emit_event(
                        type_name="message",
                        stage=stage,
                        payload=dict(role="user", type="user_tool_result", content=block.content)
                    )
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text_content += block.text
                    self._emit_event(
                        type_name="message",
                        stage=stage,
                        payload=dict(role="assistant", type="assistant_message", content=block.text)
                    )

                    recent_blocks = self.recent_assistant_text_blocks.get(stage)
                    if not isinstance(recent_blocks, list):
                        recent_blocks = []
                        self.recent_assistant_text_blocks[stage] = recent_blocks
                    recent_blocks.append(block.text)
                    if len(recent_blocks) > 5:
                        del recent_blocks[:-5]

                elif isinstance(block, ToolUseBlock):
                    self._emit_event(
                        type_name="message",
                        stage=stage,
                        payload=dict(role="assistant", type="assistant_tool", content=block.name)
                    )
        
        elif isinstance(message, ResultMessage):
            print("Result message received.")
            self._emit_event(
                type_name="message",
                stage=stage,
                payload=dict(role="assistant", type="result_message", content=asdict(message))
            )

            cost_content = (
                f"total_cost_usd: {message.total_cost_usd}\n"
                f"token usage: {json.dumps(message.usage, ensure_ascii=False, indent=2)}"
            )
            print_boxed(cost_content)

            session_meta: Dict[str, Any] = {}
            if self.session_meta_path.exists():
                try:
                    session_meta = json.loads(self.session_meta_path.read_text(encoding="utf-8"))
                except Exception as exc:
                    print_red(f"Failed to read session meta from {self.session_meta_path}: {exc}")
            if not isinstance(session_meta, dict):
                session_meta = {}

            stage_entry = session_meta.get(stage)
            if not isinstance(stage_entry, dict):
                stage_entry = {}

            stage_entry.update(
                {
                    "duration_ms": message.duration_ms,
                    "is_error": message.is_error,
                    "num_turns": message.num_turns,
                    "total_cost_usd": message.total_cost_usd,
                    "token_usage": message.usage,
                }
            )
            session_meta[stage] = stage_entry

            try:
                self.session_meta_path.write_text(
                    json.dumps(session_meta, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as exc:
                print_red(f"Failed to write session meta to {self.session_meta_path}: {exc}")
        
        return text_content

    def _extract_final_result(self, result_text: str, stage: str) -> tuple[str, bool]:
        check_final_fun = {
            "checklist_generation": self._has_required_checklist,
            "defect_detection": self._has_required_result,
        }
        if stage in check_final_fun.keys():
            if check_final_fun[stage](result_text):
                return result_text, True
            
            recent_blocks = self.recent_assistant_text_blocks.get(stage, [])
            for candidate in reversed(recent_blocks):
                if check_final_fun[stage](candidate):
                    return candidate, False
            else:
                return result_text, True
        
        return result_text, True

    def _record_final_result_source(self, stage: str, from_result_message: bool) -> None:
        session_meta: Dict[str, Any] = {}
        if self.session_meta_path.exists():
            try:
                session_meta = json.loads(self.session_meta_path.read_text(encoding="utf-8"))
            except Exception as exc:
                print_red(f"Failed to read session meta from {self.session_meta_path}: {exc}")
        if not isinstance(session_meta, dict):
            session_meta = {}

        final_result_sources = session_meta.get("final_result_sources")
        if not isinstance(final_result_sources, dict):
            final_result_sources = {}

        final_result_sources[stage] = from_result_message
        session_meta["final_result_sources"] = final_result_sources

        try:
            self.session_meta_path.write_text(
                json.dumps(session_meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            print_red(f"Failed to write session meta to {self.session_meta_path}: {exc}")
    
    def _record_message_count(self, message, stage: str) -> None:
        msg_class = type(message).__name__
        stage_counts = self.message_class_counts.get(stage)
        if not isinstance(stage_counts, dict):
            stage_counts = {}
            self.message_class_counts[stage] = stage_counts

        if msg_class in ("UserMessage", "AssistantMessage"):
            entry = stage_counts.get(msg_class)
            if not isinstance(entry, dict):
                entry = {"total_count": 0}
                stage_counts[msg_class] = entry
            entry["total_count"] = entry.get("total_count", 0) + 1
            if hasattr(message, "content"):
                for block in message.content:
                    block_class = type(block).__name__
                    entry[block_class] = entry.get(block_class, 0) + 1
        else:
            stage_counts[msg_class] = stage_counts.get(msg_class, 0) + 1

        self._write_message_statistics(stage)

    def _write_message_statistics(self, stage: str) -> None:
        session_meta: Dict[str, Any] = {}
        if self.session_meta_path.exists():
            try:
                session_meta = json.loads(self.session_meta_path.read_text(encoding="utf-8"))
            except Exception as exc:
                print_red(f"Failed to read session meta from {self.session_meta_path}: {exc}")
        if not isinstance(session_meta, dict):
            session_meta = {}

        message_statistics = session_meta.get("message_statistics")
        if not isinstance(message_statistics, dict):
            message_statistics = {}

        message_statistics[stage] = dict(self.message_class_counts.get(stage, {}))
        session_meta["message_statistics"] = message_statistics

        try:
            self.session_meta_path.write_text(
                json.dumps(session_meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            print_red(f"Failed to write session meta to {self.session_meta_path}: {exc}")

    # ------------------------------------------------------------------ #
    # Agent configuration
    # ------------------------------------------------------------------ #
    
    def _get_chat_agent_options(
        self, 
        system_prompt: Optional[str] = None,
        max_turns: int = 5,
        max_buffer_size: int = 1024*1024,
    ) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            system_prompt=system_prompt,
            allowed_tools=None,
            model=self.api_config.model,
            max_turns=max_turns,
            max_buffer_size=max_buffer_size,
            cwd=self.cwd_dir,
            env={
                "ANTHROPIC_BASE_URL": self.api_config.base_url,
                "ANTHROPIC_AUTH_TOKEN": self.api_config.api_key,
                "ANTHROPIC_API_KEY": ""
            }
        )

    def _get_browser_agent_options(
        self, 
        system_prompt: Optional[str] = None,
        max_turns: int = 5,
        max_buffer_size: int = 1024*1024,
    ) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            system_prompt=system_prompt,
            mcp_servers={
                "playwright": {
                    "type": "stdio",
                    "command": "npx",
                    "args": [
                        "-y", "@playwright/mcp@0.0.61", 
                        "--isolated",
                        "--headless",
                        "--viewport-size", "1280,720",
                    ]
                }
            },
            allowed_tools=PlaywrightTools,
            disallowed_tools=[
                "mcp__playwright__browser_take_screenshot",
            ],
            model=self.api_config.model,
            max_turns=max_turns,
            max_buffer_size=max_buffer_size,
            cwd=self.cwd_dir,
            env={
                "ANTHROPIC_BASE_URL": self.api_config.base_url,
                "ANTHROPIC_AUTH_TOKEN": self.api_config.api_key,
                "ANTHROPIC_API_KEY": "",
            }
        )
