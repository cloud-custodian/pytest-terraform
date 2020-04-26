from pytest_terraform.lock import lock_create, lock_delete


def test_lock_create(tmpdir):

    path = tmpdir / "foo"

    with lock_create(path) as (success, result):
        assert success
        result.write(b"hello world")

    assert path.exists()
    assert path.read_text("utf8") == "hello world"

    with lock_create(path) as (success, result):
        assert not success
        result == "hello world"


def test_lock_create_ctx_fail(tmpdir):

    path = tmpdir / "foo2"

    try:
        with lock_create(path) as (success, result):
            assert success
            result.write(b"partial")
            raise ValueError("something happened")
    except ValueError:
        assert not path.exists()
    else:
        assert 0, "Should have failed"


def test_lock_delete(tmpdir):
    path = tmpdir / "bar"

    with lock_delete(path) as success:
        assert success is False

    path.write(b"oops")

    with lock_delete(path) as success:
        assert success is True
