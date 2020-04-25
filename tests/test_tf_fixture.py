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
