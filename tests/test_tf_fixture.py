import subprocess
from unittest.mock import MagicMock, patch

import pytest
from pytest_terraform import tf

TF_REPLAY = True


@pytest.fixture(scope="module", params=list(range(10)))
def number_sequence(request):
    yield request.param


@tf.terraform("aws_sqs", scope="session", replay=TF_REPLAY)
def test_tf_user_a(aws_sqs):
    assert aws_sqs.resources["aws_sqs_queue"]["terraform_queue"]["tags"] == {
        "Environment": "production"
    }


@tf.terraform("aws_sns", scope="function", replay=TF_REPLAY)
def test_tf_user_b(aws_sqs, aws_sns):
    assert aws_sqs.resources["aws_sqs_queue"]["terraform_queue"]["tags"] == {
        "Environment": "production"
    }
    assert aws_sns["user_updates"]["name"].startswith("user-updates-topic")


@tf.terraform("aws_sns", scope="function", replay=TF_REPLAY)
def test_tf_user_c(aws_sqs, aws_sns):
    assert aws_sqs.resources["aws_sqs_queue"]["terraform_queue"]["tags"] == {
        "Environment": "production"
    }
    assert aws_sns["user_updates"]["name"].startswith("user-updates-topic")


def test_tf_user_many(aws_sqs, number_sequence):
    return number_sequence


def test_tf_teardown_register():
    fixture = tf.TerraformFixture(
        tf_bin="fakebin",
        plugin_cache="fakecache",
        scope="function",
        tf_root_module="fakeroot",
        test_dir="fakedir",
        replay=False,
        teardown=tf.td.ON,
        pytest_config=MagicMock(),
    )

    fixture.runner = MagicMock()
    request = MagicMock()

    fixture.create(request, MagicMock())

    request.addfinalizer.assert_called()


def test_tf_teardown_exception():
    import subprocess

    fixture = tf.TerraformFixture(
        tf_bin="fakebin",
        plugin_cache="fakecache",
        scope="function",
        tf_root_module="fakeroot",
        test_dir="fakedir",
        replay=False,
        teardown=tf.td.ON,
        pytest_config=MagicMock(),
    )

    request = MagicMock()
    fixture.runner = MagicMock()
    fixture.runner.destroy.side_effect = [subprocess.CalledProcessError(99, "test")]

    fixture.create(request, MagicMock())
    pytest.raises(tf.TerraformCommandFailed, fixture.tear_down)


def test_tf_teardown_register_ignore():

    fixture = tf.TerraformFixture(
        tf_bin="fakebin",
        plugin_cache="fakecache",
        scope="function",
        tf_root_module="fakeroot",
        test_dir="fakedir",
        replay=False,
        teardown=tf.td.IGNORE,
        pytest_config=MagicMock(),
    )

    request = MagicMock()
    fixture.runner = MagicMock()
    fixture.runner.destroy.side_effect = [subprocess.CalledProcessError(99, "test")]

    fixture.create(request, MagicMock())
    fixture.tear_down()

    request.addfinalizer.assert_called()


def test_tf_skip_teardown_register():
    fixture = tf.TerraformFixture(
        tf_bin="fakebin",
        plugin_cache="fakecache",
        scope="function",
        tf_root_module="fakeroot",
        test_dir="fakedir",
        replay=False,
        teardown=tf.td.OFF,
        pytest_config=MagicMock(),
    )

    fixture.runner = MagicMock()
    request = MagicMock()

    fixture.create(request, MagicMock())

    request.addfinalizer.assert_not_called()


def test_tf_hook_modify_state():
    pytest_config = MagicMock()
    fixture = tf.TerraformFixture(
        tf_bin="fakebin",
        plugin_cache="fakecache",
        scope="function",
        tf_root_module="fakeroot",
        test_dir="fakedir",
        replay=False,
        teardown=tf.td.DEFAULT,
        pytest_config=pytest_config,
    )

    fixture.runner = MagicMock()
    fixture.create(MagicMock(), MagicMock())

    tfstate_json = fixture.runner.apply.return_value.save.return_value
    hook = pytest_config.hook.pytest_terraform_modify_state
    hook.assert_called_with(tfstate=tfstate_json)


@patch.object(tf.TerraformFixture, "__call__")
@patch("pytest_terraform.tf._frame_path")
@patch("pytest_terraform.tf.pytest")
def test_tf_factory_teardown_config_default(_, frame_path_mock, fixture_call_mock):
    frame_path_mock.return_value = "."
    df = tf.FixtureDecoratorFactory()
    df(terraform_dir="test")
    assert df._fixtures[0].teardown_config == tf.td.ON
