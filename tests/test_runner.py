import os

import pytest

import run


@pytest.mark.parametrize("environment", run.SUPPORTED_ENVIRONMENTS)
def test_runner_selects_environment_and_starts_uvicorn(
    environment: str,
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(run.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    run.main([environment])

    assert os.environ["APP_ENV"] == environment
    assert calls == [
        (
            ("app.main:app",),
            {
                "host": "127.0.0.1",
                "port": 8000,
                "reload": True,
            },
        )
    ]


@pytest.mark.parametrize("arguments", [[], ["invalid"]])
def test_runner_rejects_missing_or_invalid_environment(arguments, monkeypatch) -> None:
    called = False

    def fail_if_called(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(run.uvicorn, "run", fail_if_called)

    with pytest.raises(SystemExit) as exc_info:
        run.main(arguments)

    assert exc_info.value.code != 0
    assert called is False
