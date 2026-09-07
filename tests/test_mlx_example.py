import json
import sys
from types import SimpleNamespace

import pytest

from examples import measure_mlx
from tracarbon import EnergyUsage
from tracarbon import IOReportEnergy


@pytest.mark.parametrize("missing", ["cpu", "gpu", "memory", None])
def test_mlx_example_rejects_missing_counters_but_accepts_zero_gpu_power(mocker, capsys, missing):
    response = SimpleNamespace(text="text", prompt_tokens=2, generation_tokens=1)
    core = SimpleNamespace(
        gpu="gpu",
        set_default_device=mocker.Mock(),
        synchronize=mocker.Mock(),
        device_info=lambda: {"device_name": "test"},
    )
    mocker.patch.dict(
        sys.modules,
        {
            "mlx": SimpleNamespace(core=core),
            "mlx.core": core,
            "mlx_lm": SimpleNamespace(
                load=mocker.Mock(return_value=(object(), mocker.Mock(apply_chat_template=lambda *a, **kw: [1, 2]), {})),
                stream_generate=lambda *a, **kw: iter([response]),
            ),
            "mlx_lm.generate": SimpleNamespace(GenerationResponse=SimpleNamespace),
            "mlx_lm.sample_utils": SimpleNamespace(make_sampler=lambda **kw: None),
        },
    )
    mocker.patch.object(sys, "argv", ["measure_mlx.py", "--country", "fr", "--repeats", "1"])
    mocker.patch.object(measure_mlx, "version", return_value="test")
    mocker.patch.object(IOReportEnergy, "is_available", return_value=True)
    mocker.patch.object(IOReportEnergy, "__init__", return_value=None)
    mocker.patch.object(IOReportEnergy, "close")
    usage = EnergyUsage(host_energy_usage=60.0, cpu_energy_usage=20.0, memory_energy_usage=40.0, gpu_energy_usage=0.0)
    if missing is not None:
        setattr(usage, f"{missing}_energy_usage", None)
    mocker.patch.object(IOReportEnergy, "get_energy_report", return_value=usage)

    if missing is not None:
        with pytest.raises(RuntimeError, match="Energy sampling failed"):
            measure_mlx.main()
        assert capsys.readouterr().out == ""
    else:
        measure_mlx.main()
        result = json.loads(capsys.readouterr().out)
        assert result["output_tokens"] == 1
        assert result["energy_wh"] > 0
