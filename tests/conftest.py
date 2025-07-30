import os

import pytest


def get_fixture_paths(path):
    if not os.path.isdir(path):
        return [path]
    fixture_paths = []
    for p in os.listdir(path):
        p = os.path.join(path, p)
        if os.path.isfile(p):
            fixture_paths.append(p)
    return fixture_paths


def parametrize_with_fixtures(
    path, base_path="tests/fixtures", argname="fixture", only_filenames=None
):
    path = os.path.join(base_path, path)
    fixture_paths = get_fixture_paths(path)
    argvalues = []
    for path in fixture_paths:
        with open(path, "r") as f:
            content = "".join(f.readlines())
        filename = os.path.basename(path)
        if only_filenames and filename not in only_filenames:
            continue
        param = pytest.param(content, id=filename)
        argvalues.append(param)

    def _decorator(test_function):
        return pytest.mark.parametrize(argname, argvalues)(test_function)

    return _decorator
