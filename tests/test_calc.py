import pytest

from src.calc import add


def test_add_with_non_number_raises_type_error():
    # 预期对非数字输入抛出类型错误
    with pytest.raises(TypeError):
        add("2", 3)
