from app.tools.base import Tool
from app.tools.calculator import calculator_tool

calc = Tool("calculator", "", "", calculator_tool)


def test_basic_arithmetic_and_precedence():
    assert calc.run({"expression": "2 + 3 * 4"}) == "14"
    assert calc.run({"expression": "(2 + 3) * 4"}) == "20"
    assert calc.run({"expression": "10 / 4"}) == "2.5"


def test_business_helpers():
    assert calc.run({"expression": "pct_change(120, 150)"}) == "25"
    assert calc.run({"expression": "round(pct_change(4200000, 4610000), 2)"}) == "9.76"
    assert calc.run({"expression": "sum([1, 2, 3])"}) == "6"
    assert calc.run({"expression": "mean([2, 4, 6])"}) == "4"
    assert calc.run({"expression": "sqrt(16)"}) == "4"


def test_code_injection_is_impossible():
    for evil in ["__import__('os').system('echo hi')", "open('/etc/passwd')", "().__class__", "x + 1", "lambda: 1"]:
        assert calc.run({"expression": evil}).startswith("ERROR"), evil


def test_resource_bombs_are_rejected():
    assert calc.run({"expression": "2 ** 100000"}).startswith("ERROR")
    assert calc.run({"expression": "((2 ** 1000) ** 1000) ** 1000"}).startswith("ERROR")
    assert calc.run({"expression": "9" * 600}).startswith("ERROR")


def test_errors_are_reported_not_raised():
    assert "division by zero" in calc.run({"expression": "1 / 0"})
    assert calc.run({"expression": ""}).startswith("ERROR")
    assert calc.run({"expression": "2 +"}).startswith("ERROR")
    assert calc.run({"expression": "mean([])"}).startswith("ERROR")
