# -*- coding: utf-8 -*-

import pytest
from pytest_terraform import options


def test_teardown_option_set_default():
    tdo = options.TeardownOption()
    assert tdo._default == options.TeardownOption.ON

    tdo.set_default(options.TeardownOption.OFF)
    assert tdo._default == options.TeardownOption.OFF


def test_teardown_option_set_default_with_default():
    """Make sure we maintain backwards compatibility with `on` as sensible default"""
    tdo = options.TeardownOption()
    tdo.set_default(options.TeardownOption.DEFAULT)
    assert tdo._default == options.TeardownOption.ON

    tdo.set_default(None)
    assert tdo._default == options.TeardownOption.ON


def test_teardown_option_resolve_default():
    """If a test option is set to default validate it resolves to the default option"""
    tdo = options.TeardownOption()
    assert tdo.resolve(options.TeardownOption.DEFAULT) == tdo._default


def test_teardown_option_resolve_valid():
    """Make sure resolver provides valid response for valid option"""
    tdo = options.TeardownOption()
    assert tdo.resolve(options.TeardownOption.OFF) == options.TeardownOption.OFF


def test_teardown_option_resolve_invalid():
    """If an option is invalid make sure an exception is raised"""
    tdo = options.TeardownOption()
    pytest.raises(options.InvalidTeardownMode, tdo.resolve, "INVALID---")
