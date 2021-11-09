# -*- coding: utf-8 -*-
import json
import os
import shutil
from pathlib import Path

import pytest
from pytest_terraform import tf
from pytest_terraform.exceptions import InvalidState


def test_frame_walk():
    class Frame:
        def __init__(self, f_locals, f_back=None):
            self.f_locals = f_locals
            self.f_back = f_back

    parent = Frame({"__file__": "/tmp/file.py"})
    child = Frame({}, parent)
    assert tf._frame_path(child) == "/tmp/file.py"

    with pytest.raises(RuntimeError):
        tf._frame_path(Frame({}))


@tf.terraform("local_bar", scope="session")
def test_tf_user_a(local_bar):
    print("test invoked a")


@tf.terraform("local_foo", scope="function")
def test_tf_user_b(local_foo):
    print("test invoked b")


@tf.terraform("local_foo", scope="function")
def test_tf_user_c(local_foo):
    print("test invoked c")


def test_fixture_factory():
    with pytest.raises(KeyError):
        tf.terraform.get_fixture("abc")


def test_tf_resources():
    state = tf.TerraformState.from_file(
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


def test_tf_string_resources():
    with open(os.path.join(os.path.dirname(__file__), "burnify.tfstate")) as f:
        burnify = f.read()

    state = tf.TerraformState.from_string(burnify)
    save_state = str(state.save())
    reload = tf.TerraformState.from_string(save_state)

    assert len(state.resources) == 9
    assert len(reload.resources) == 9

    assert save_state == reload.save()


def test_tf_statejson_resources():
    with open(os.path.join(os.path.dirname(__file__), "burnify.tfstate")) as f:
        burnify = f.read()

    state = tf.TerraformState.from_string(burnify)
    save_state = state.save()
    reload = tf.TerraformState.from_string(save_state)

    assert len(state.resources) == 9
    assert len(reload.resources) == 9

    assert save_state == reload.save()


def test_tf_state_bad_file():
    with pytest.raises(InvalidState):
        tf.TerraformState.from_file("/not-exists1")


def test_tf_statejson_from_dict():
    obj = {
        "test": "foo",
        "nested": {"bar": "baz"},
    }

    statejson = tf.TerraformStateJson.from_dict(obj)
    assert str(statejson) == json.dumps(obj, indent=4)
    assert statejson.dict == obj


def test_tf_statejson_bad_dict():
    obj = {
        "test": "foo",
        "nested": {"bar": "baz"},
        "embed": tf.PlaceHolderValue("test"),
    }

    statejson = tf.TerraformStateJson("")
    with pytest.raises(ValueError):
        statejson.dict = obj


def test_tf_statejson_update():
    newobj = {
        "differet": True,
    }

    newstr = json.dumps(newobj)

    statejson = tf.TerraformStateJson("")
    statejson.update(newstr)

    assert str(statejson) == newstr


def test_tf_statejson_update_dict():
    newobj = {
        "differet": True,
    }

    statejson = tf.TerraformStateJson("")
    statejson.update_dict(newobj)

    assert statejson.dict == newobj


def test_tf_statejson_update_bad():

    statejson = tf.TerraformStateJson("hello")

    with pytest.raises(ValueError):
        statejson.update({"hello": "world"})


@pytest.mark.skipif(not shutil.which("terraform"), reason="Terraform binary missing")
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

    trunner = tf.TerraformRunner(tmpdir.strpath, tf_bin=shutil.which("terraform"))
    trunner.init()
    state = trunner.apply()
    assert state.get("foo")["content"] == "foo!"
    with open(tmpdir.join("foo.bar")) as fh:
        assert fh.read() == "foo!"

    assert state.work_dir is not None
    assert isinstance(state.terraform.show(), dict)
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


@pytest.mark.skipif(not shutil.which("terraform"), reason="Terraform binary missing")
def test_plugins_ini_setting_terraform_mod_dir(testdir):
    mod_dir = Path(__file__).parent / "data" / "mrofarret"
    testdir.makeini(
        f"""
        [pytest]
        terraform-mod-dir = {mod_dir}
    """
    )

    testdir.makepyfile(
        """
        import pytest
        from pytest_terraform import terraform

        @terraform("local_baz")
        def test_local_baz(local_baz):
            assert local_baz['local_file.baz.content'] == 'baz!'
            return
    """
    )

    result = testdir.runpytest("-v", "-s", "-k", "terraform")

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(["*::test_local_baz PASSED*"])

    # make sure that that we get a '0' exit code for the testsuite
    assert result.ret == 0


@pytest.mark.skipif(not shutil.which("terraform"), reason="Terraform binary missing")
def test_hook_modify_state_copy(testdir):
    """Test that modify_state hook does not modify state
    for function under test
    """

    mod_dir = Path(__file__).parent / "terraform"
    testdir.makeini(
        f"""
        [pytest]
        terraform-mod-dir = {mod_dir}
    """
    )

    testdir.makeconftest(
        """
        def pytest_terraform_modify_state(tfstate):
            tfstate.update(str(tfstate).replace('buz!', 'fiz!'))
    """
    )

    testdir.makepyfile(
        """
        import pytest
        from pytest_terraform import terraform

        @terraform("local_buz")
        def test_local_buz(local_buz):
            assert local_buz['local_file.buz.content'] == 'buz!'
            return
    """
    )

    result = testdir.runpytest("-v", "-s")

    result.stdout.fnmatch_lines(["*::test_local_buz PASSED*"])
    assert result.ret == 0

    state = tf.TerraformState.from_file(mod_dir / "local_buz" / "tf_resources.json")
    assert state["local_file.buz.content"] == "fiz!"
