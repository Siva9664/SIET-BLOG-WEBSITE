"""Tests for PEFT LoRA Adapter Swapper and VRAM Guard."""

import pytest
from app.modules.datasets.lora_swapper import get_lora_swapper


def test_adapter_swapper_swap_cycle():
    swapper = get_lora_swapper()

    # Initial status
    status0 = swapper.get_status()
    assert status0["status"] == "OK"

    # Swap to fact_extraction
    res1 = swapper.swap_adapter("fact_extraction")
    assert res1 is True
    assert swapper.active_adapter_name == "fact_extraction"

    # Swap to verification
    res2 = swapper.swap_adapter("verification")
    assert res2 is True
    assert swapper.active_adapter_name == "verification"

    # Swap back to fact_extraction
    res3 = swapper.swap_adapter("fact_extraction")
    assert res3 is True
    assert swapper.active_adapter_name == "fact_extraction"


def test_adapter_swapper_invalid_adapter_raises():
    swapper = get_lora_swapper()
    with pytest.raises(ValueError, match="Unknown adapter"):
        swapper.swap_adapter("invalid_adapter_name")
