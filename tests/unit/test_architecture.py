import ast
import json
from pathlib import Path


SRC = Path(__file__).resolve().parents[2] / "src"


def python_files(layer):
    return [path for path in (SRC / layer).glob("*.py") if path.name != "__init__.py"]


def imported_roots(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_layers_only_depend_on_allowed_application_layers():
    allowed = {
        "middlewares": {"database", "errors", "utils"},
        "resources": {"controllers", "utils"},
        "controllers": {"database", "dtos", "errors", "repositories", "utils", "connectors"},
        "repositories": {"database", "models"},
        "models": {"models"},
        "dtos": {"models"},
        "connectors": {"errors", "utils"},
    }
    application_layers = set(allowed) | {"database", "app"}
    for layer, permitted in allowed.items():
        permitted = permitted | {layer}
        for path in python_files(layer):
            forbidden = (imported_roots(path) & application_layers) - permitted
            assert not forbidden, f"{path.relative_to(SRC)} imports forbidden layers: {sorted(forbidden)}"

    app_imports = imported_roots(SRC / "app.py") & application_layers
    assert app_imports <= {"middlewares", "resources"}


def test_controllers_do_not_call_other_controllers():
    for path in python_files("controllers"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        controller_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module.rsplit(".", 1)[-1]
                if node.module.startswith("controllers.") and module.endswith("_controller"):
                    controller_imports.append(module)
        assert controller_imports in ([], ["base_controller"]), (
            f"{path.relative_to(SRC)} calls another controller layer: {controller_imports}"
        )


def test_each_resource_method_calls_at_most_one_controller():
    for path in python_files("resources"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
            calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id.endswith("Controller")]
            assert len(calls) <= 1, f"{path.name}:{function.name} calls more than one controller"


def test_http_and_sql_stay_in_their_layers():
    for path in python_files("controllers"):
        source = path.read_text(encoding="utf-8")
        assert "from fastapi" not in source and "import fastapi" not in source
        assert ".query(" not in source and "session.execute(" not in source
        assert "request.headers" not in source and "request.url" not in source
    for path in python_files("resources"):
        source = path.read_text(encoding="utf-8")
        assert ".query(" not in source
        assert "session." not in source
    for path in python_files("repositories"):
        source = path.read_text(encoding="utf-8")
        assert "from fastapi" not in source and "import fastapi" not in source
        assert ".commit(" not in source and ".rollback(" not in source
    for layer in ("controllers", "repositories", "resources", "dtos", "models"):
        for path in python_files(layer):
            assert not (imported_roots(path) & {"requests", "httpx", "urllib3"})


def test_models_have_one_table_mapping_per_file():
    for path in python_files("models"):
        if path.name == "base.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        mappings = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        assert len(mappings) == 1, f"{path.name} must contain exactly one model"
        assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(mappings[0]))


def test_every_schema_is_valid_json():
    for path in (SRC / "schemas").glob("*.json"):
        with path.open(encoding="utf-8") as schema_file:
            json.load(schema_file)
