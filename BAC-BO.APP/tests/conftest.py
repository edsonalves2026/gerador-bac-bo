"""Fixtures compartilhadas + fakes."""
import pytest

from bacbo.config import BacBoConfig
from bacbo.db import Database
from bacbo.worker import BacBoWorker


class FakeClient:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def buscar_historico(self, **kwargs):
        self.calls.append(kwargs)
        if self.responses:
            return self.responses.pop(0)
        return [], [], [], [], []


class FakeNotifier:
    def __init__(self, succeed=True):
        self.messages = []
        self.succeed = succeed

    def send(self, texto: str) -> bool:
        self.messages.append(texto)
        return self.succeed


def make_payload(cores, uuids, pontos):
    return (
        list(cores),
        list(uuids),
        list(pontos),
        [f"{c} {p}" for c, p in zip(cores, pontos)],
        [f"{c} ({p})" for c, p in zip(cores, pontos)],
    )


@pytest.fixture
def fake_client():
    return FakeClient()


@pytest.fixture
def fake_notifier():
    return FakeNotifier()


@pytest.fixture
def memory_db():
    db = Database(":memory:")
    yield db
    db.close()


@pytest.fixture
def config():
    return BacBoConfig(
        intervalo_verificacao=1,
        sensibilidade_minima=65.0,
        tamanho_padrao=3,
        min_operacoes_ranking=2,
    )


@pytest.fixture
def worker(fake_client, fake_notifier, memory_db, config):
    return BacBoWorker(fake_client, fake_notifier, memory_db, config)