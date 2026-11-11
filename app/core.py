"""Business logic: no hardware or network dependencies."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def now_iso():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Memory:
    notes: list[dict] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)
    last_hud: dict = field(default_factory=lambda: {"kind": "idle", "title": "AI/AR GLASSES", "lines": ["等待输入"]})

    def note(self, text: str) -> dict:
        if not text.strip():
            raise ValueError("笔记不能为空")
        record = {"id": uuid4().hex[:12], "text": text.strip(), "created_at": now_iso()}
        self.notes.append(record)
        return record

    def draft_task(self, text: str) -> dict:
        if not text.strip():
            raise ValueError("任务内容不能为空")
        record = {"id": uuid4().hex[:12], "text": text.strip(), "status": "awaiting_confirmation", "created_at": now_iso()}
        self.tasks.append(record)
        self.last_hud = {"kind": "task", "title": "任务待确认", "lines": [record["text"][:78]]}
        return record

    def confirm_task(self, task_id: str) -> dict:
        item = next((x for x in self.tasks if x["id"] == task_id), None)
        if not item:
            raise ValueError("找不到任务")
        if item["status"] != "awaiting_confirmation":
            raise ValueError("任务已处理")
        # This prototype only confirms locally. External actions require separate authorized adapters.
        item["status"] = "confirmed_local_only"
        item["confirmed_at"] = now_iso()
        self.last_hud = {"kind": "task", "title": "已确认（未外部执行）", "lines": [item["text"][:78]]}
        return item

    def wipe(self) -> dict:
        self.notes.clear()
        self.tasks.clear()
        self.last_hud = {"kind": "idle", "title": "数据已清除", "lines": ["原型进程中的笔记和任务已清除"]}
        return {"cleared": True, "scope": "local_prototype_memory_only"}

    def snapshot(self) -> dict:
        return {"notes": self.notes, "tasks": self.tasks, "hud": self.last_hud}


def to_hud(kind: str, text: str) -> dict:
    title = {"vision": "眼前识别", "translate": "AR 翻译", "chat": "AI 助手"}.get(kind, "智能提示")
    compact = " ".join(text.split())
    chunks = [compact[i:i+28] for i in range(0, len(compact), 28)][:3]
    truncated = len(compact) > 84
    if truncated:
        chunks[-1] = chunks[-1][:27] + "…"
    return {"kind": kind, "title": title, "lines": chunks or ["（无结果）"],
            "truncated": truncated, "time": now_iso()}
