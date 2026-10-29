from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path("data/college")
    state_dir: Path = Path(".runtime/college")
    host: str = "http://127.0.0.1:11434"
    model: str = "qwen3:8b"
    embed_model: str = "nomic-embed-text"
    semester: str = ""
    programme: str = "B.Tech"
    cohort: str = ""
    branch: str = ""
    temperature: float = 0.0
    context: int = 8192
    timeout: float = 180.0
    verify: bool = True
    think: bool = False
    top_k: int = 6

    @classmethod
    def from_env(cls):
        load_dotenv()
        return cls(
            data_dir=Path(os.getenv("HELPDESK_DATA_DIR", "data/college")),
            state_dir=Path(os.getenv("HELPDESK_STATE_DIR", ".runtime/college")),
            host=os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434").rstrip("/"),
            model=os.getenv("HELPDESK_MODEL", "qwen3:8b"),
            embed_model=os.getenv("HELPDESK_EMBED_MODEL", "nomic-embed-text"),
            semester=os.getenv("HELPDESK_SEMESTER", ""),
            programme=os.getenv("HELPDESK_PROGRAMME", "B.Tech"),
            cohort=os.getenv("HELPDESK_COHORT", ""),
            branch=os.getenv("HELPDESK_BRANCH", ""),
            temperature=float(os.getenv("HELPDESK_TEMPERATURE", "0")),
            context=int(os.getenv("HELPDESK_CONTEXT", "8192")),
            timeout=float(os.getenv("HELPDESK_TIMEOUT", "180")),
            verify=os.getenv("HELPDESK_VERIFY", "true").lower() == "true",
            think=os.getenv("HELPDESK_THINK", "false").lower() == "true",
        )
