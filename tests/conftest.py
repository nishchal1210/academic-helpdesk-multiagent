from dataclasses import replace
from pathlib import Path
import shutil

import pytest

from helpdesk.config import Settings
from helpdesk.retrieval import Retriever, ingest
from helpdesk.corpus import Registry
from helpdesk.tools import AcademicTools, EvidenceLedger


@pytest.fixture
def settings(tmp_path):
    data = tmp_path / "data"
    shutil.copytree(Path(__file__).parents[1] / "data/demo", data)
    return Settings(data_dir=data, state_dir=tmp_path / "state", semester="DEMO-2026-I", cohort="2023")


@pytest.fixture
def indexed(settings):
    ingest(settings, lexical_only=True)
    return settings


@pytest.fixture
def tools(indexed):
    registry = Registry(indexed.data_dir)
    return AcademicTools(indexed, registry, Retriever(indexed, registry), EvidenceLedger())


@pytest.fixture
def modify_settings():
    return replace
