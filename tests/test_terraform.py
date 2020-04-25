# -*- coding: utf-8 -*-
import os

import pytest

from pytest_terraform import tf


@tf.terraform("local_bar", scope="session")
def test_tf_user_a(local_bar):
    print("test invoked a")


@tf.terraform("local_foo", scope="function")
def test_tf_user_b(local_foo):
    print("test invoked b")


@tf.terraform("local_foo", scope="function")
def test_tf_user_c(local_foo):
    print("test invoked c")


def test_tf_resources():
    state = tf.TerraformState.load(
        os.path.join(os.path.dirname(__file__), "burnify.tfstate")
    )

    assert len(state.resources) == 9
    assert state.get("aws_api_gateway_rest_api.rest_api.id") == "7bnxriulj5"
    assert state.get("sfn_account_create_poll") == {
        "filename": "./deployment.zip",
        "id": "burnify-dev-sfn_account_create_poll",
    }
    with pytest.raises(AssertionError) as excinfo:
        state.get("rest_api")

    assert str(excinfo.value).splitlines()[0] == "Ambigious resource name rest_api"


@pytest.mark.skipif(not tf.find_binary("terraform"), reason="Terraform binary missing")
def test_tf_runner(testdir, tmpdir):
    # ** requires network access to install plugin **
    with open(tmpdir.join("resources.tf"), "w") as fh:
        fh.write(
            """
resource "local_file" "foo" {
    content     = "foo!"
    filename = "${path.module}/foo.bar"
}
"""
        )

    trunner = tf.TerraformRunner(tmpdir.strpath, tf_bin=tf.find_binary("terraform"))
    trunner.init()
    state = trunner.apply()
    assert state.get("foo")["content"] == "foo!"
    with open(tmpdir.join("foo.bar")) as fh:
        assert fh.read() == "foo!"

    trunner.destroy()
    assert False is tmpdir.join("foo.bar").exists()


def xtest_bar_fixture(testdir):
    """Make sure that pytest accepts our fixture."""

    # create a temporary pytest test module
    testdir.makepyfile(
        """
        def test_sth(bar):
            assert bar == "terraform"
    """
    )

    # run pytest with the following cmd args
    result = testdir.runpytest("--tf-binary=terraform", "-v")

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(["*::test_sth PASSED*"])

    # make sure that that we get a '0' exit code for the testsuite
    assert result.ret == 0


def test_help_message(testdir):
    result = testdir.runpytest("--help",)
    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(["terraform:", ("*--tf-binary=DEST_TF_BINARY*")])


def test_plugins_ini_setting(testdir):
    testdir.makeini(
        """
        [pytest]
        terraform-plugins =
            aws ~> 2.2.0
            github
    """
    )

    testdir.makepyfile(
        """
        import pytest

        @pytest.fixture
        def hello(request):
            return request.config.getini('terraform-mod-dir')

        def test_hello_world(hello):
            assert hello == ''
            return
    """
    )

    result = testdir.runpytest("-v", "-s")

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(["*::test_hello_world PASSED*"])

    # make sure that that we get a '0' exit code for the testsuite
    assert result.ret == 0
