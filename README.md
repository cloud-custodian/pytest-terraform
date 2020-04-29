# Introduction

[![CI](https://github.com/cloud-custodian/pytest-terraform/workflows/CI/badge.svg?branch=master&event=push)](https://github.com/cloud-custodian/pytest-terraform/actions?query=branch%3Amaster)
[![codecov](https://codecov.io/gh/cloud-custodian/pytest-terraform/branch/master/graph/badge.svg)](https://codecov.io/gh/cloud-custodian/pytest-terraform)

pytest_terraform is a pytest plugin that enables executing terraform
to provision infrastructure in a unit/functional test as a fixture.

This plugin features uses a fixture factory pattern to enable paramterized
construction of fixtures via decorators.

## Usage

```python
from boto3 import Session
from pytest_terraform import terraform


# We use the terraform decorator to create a fixture with the name of
# the terraform module.
#
# The test function will be invoked after the terraform module is provisioned
# with the results of the provisioning.
#
# The module `aws_sqs` will be searched for in several directories, the test
# file directory, a sub directory `terraform`.
#
# This fixture specifies a session scope and will be run once per test run.
#
@terraform('aws_sqs', scope='session')
def test_sqs(aws_sqs):
    # A test is passed a terraform resources class containing content from
    # the terraform state file.
    #
    # Note the state file contents may vary across terraform versions.
    #
    # We can access nested datastructures with a jmespath expression.
    assert aws_sqs["aws_sqs_queue.test_queue.tags"] == {
        "Environment": "production"
    }
   queue_url = aws_sqs['test_queue.queue_url']
   print(queue_url)


def test_sqs_deliver(aws_sqs):
   # Once a fixture has been defined with a decorator
   # it can be reused in the same module by name, with provisioning
   # respecting scopes.
   #
   boto3.Session().client('sqs')
   sqs.send_message(
       QueueUrl=aws_sqs['test_queue.queue_url'],
       MessageBody=b"123")

@terraform('aws_sqs')
def test_sqs_dlq(aws_sqs):
   # the fixture can also referenced again via decorator, if redefined
   # with decorator the fixture parameters much match (ie same session scope).

   # Module outputs are available as a separate mapping.
   aws_sqs.outputs['QueueUrl']
```

*Note* the fixture name should match the terraform module name

*Note* The terraform state file is considered an internal
implementation detail of terraform, not per se a stable public interface
across versions.

## Options

You can provide the path to the terraform binary else its auto discovered
```shell
--tf-binary=$HOME/bin/terraform
```

To avoid repeated downloading of plugins a plugin cache dir is utilized
by default this is `.tfcache` in the current working directory.
```shell
--tf-plugin-dir=$HOME/.cache/tfcache
```

Terraform modules referenced by fixtures are looked up in a few different
locations, directly in the same directory as the test module, in a subdir
named terraform, and in a sibling directory named terraform. An explicit
directory can be given which will be looked at first for all modules.

```shell
--tf-mod-dir=terraform
```

This plugin also supports flight recording (see next section)
```shell
--tf-replay=[record|replay|disable]
```

## Flight Recording

The usage/philosophy of this plugin is based on using flight recording
for unit tests against cloud infrastructure. In flight recording rather
than mocking or stubbing infrastructure, actual resources are created
and interacted with with responses recorded, with those responses
subsequently replayed for fast test execution. Beyond the fidelity
offered, this also enables these tests to be executed/re-recorded against
live infrastructure for additional functional/release testing.

### Replay Support

By default fixtures will save a `tf_resources.json` back to the module
directory, that will be used when in replay mode.

### Recording

TODO ~

## XDist Compatibility

pytest_terraform supports pytest-xdist in multi-process (not distributed)
mode.

When run with python-xdist, pytest_terraform treats all non functional
scopes as per test run fixtures across all workers, honoring their
original scope lifecycle but with global semantics, instead of once
per worker (xdist default).

To enable this the plugin does multi-process coodination using lock
files, a test execution log, and a dependency mapping of fixtures
to tests. Any worker can execute a module teardown when its done executing
the last test that depends on a given fixture. All provisioning and
teardown are guarded by atomic file locks in the pytest execution's temp
directory.

### Root module references

`terraform_remote_state` can be used to introduce a dependency between
a scoped root modules on an individual test, note we are not
attempting to support same scope inter fixture dependencies as that
imposes additional scheduling constraints outside of pytest native
capabilities. The higher scoped root module (ie session or module scoped)
will need to have output variables to enable this consumption.
