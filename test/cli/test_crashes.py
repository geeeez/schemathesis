from unittest import mock

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from hypothesis.provisional import urls
from requests import Response

from schemathesis.cli import ALL_CHECKS_NAMES


@pytest.fixture(scope="module")
def mocked_schema():
    """Module-level mock for fast hypothesis tests.

    We're checking the input validation part, what comes from the network is not important in this context,
    the faster run will be, the better.
    """
    response = Response()
    response._content = b"""openapi: 3.0.0
info:
  title: Sample API
  description: API description in Markdown.
  version: 1.0.0
paths: {}
servers:
  - url: https://api.example.com/{basePath}
    variables:
      basePath:
        default: v1
"""
    response.status_code = 200
    with mock.patch("schemathesis.loaders.requests.sessions.Session.send", return_value=response):
        yield


@st.composite
def delimited(draw):
    key = draw(st.text(min_size=1))
    value = draw(st.text(min_size=1))
    return f"{key}:{value}"


@st.composite
def paths(draw):
    path = draw(st.text()).lstrip("/")
    return "/" + path


# The following strategies generate CLI parameters, for example "--workers=5" or "--exitfirst"
@given(
    params=st.fixed_dictionaries(
        {},
        optional={
            "auth": delimited(),
            "auth-type": st.sampled_from(["basic", "digest", "BASIC", "DIGEST"]),
            "workers": st.integers(min_value=1, max_value=64),
            "request-timeout": st.integers(),
            "validate-schema": st.booleans(),
            "hypothesis-deadline": st.integers() | st.none(),
        },
    ).map(lambda params: [f"--{key}={value}" for key, value in params.items()]),
    flags=st.fixed_dictionaries(
        {}, optional={key: st.booleans() for key in ("show-errors-tracebacks", "exitfirst", "hypothesis-derandomize")}
    ).map(lambda flags: [f"--{flag}" for flag in flags]),
    multiple_params=st.fixed_dictionaries(
        {},
        optional={
            "checks": st.lists(st.sampled_from(ALL_CHECKS_NAMES + ("all",))),
            "header": st.lists(delimited()),
            "endpoint": st.lists(st.text(min_size=1)),
            "method": st.lists(st.text(min_size=1)),
            "tag": st.lists(st.text(min_size=1)),
        },
    ).map(lambda params: [f"--{key}={value}" for key, values in params.items() for value in values]),
)
@example(params=[], flags=[], multiple_params=["--header=0:0\r"])
@example(params=["--hypothesis-deadline=0"], flags=[], multiple_params=[])
@pytest.mark.usefixtures("mocked_schema")
def test_valid_parameters_combos(cli, schema_url, params, flags, multiple_params):
    result = cli.run(schema_url, *params, *multiple_params, *flags)
    check_result(result)


@given(schema=urls() | paths() | st.text())
@example("//bla")
@pytest.mark.usefixtures("mocked_schema")
def test_schema_validity(cli, schema):
    result = cli.run(schema)
    check_result(result)


def check_result(result):
    assert not (result.exception and not isinstance(result.exception, SystemExit)), result.stdout
