# Introduction

pytest_terraform is a pytest plugin that enables executing terraform
to provision infrastructure in a unit/functional test as a fixture.

This plugin features uses a fixture factory pattern to enable dynamic
construction of fixtures as either as test decorators or module level
variables.


## Philosophy

The usage/philosophy of this plugin is based on using flight recording
for unit tests against cloud infrastructure. In flight recording rather
than mocking or stubbing infrastructure, actual resources are created
and interacted with with responses recorded, with those responses
subsequently replayed for fast test execution. Beyond the fidelity
offered, this also enables these tests to be executed/re-recorded against
live infrastructure for additional functional/release testing.


## Decorator Usage

```python
from pytest_terraform import terraform
from boto3 import Session

@terraform('aws_sqs')
def test_sqs(aws_sqs):
   queue_url = aws_sqs['test_queue.queue_url']
   print(queue_url)


def test_sqs_deliver(aws_sqs):
   # once a fixture has been defined with a decorator
   # it can be reused in the same module by name
   pass

@terraform('aws_sqs')
def test_sqs_dlq(aws_sqs):
   # or referenced again via decorator, if redefined
   # with decorator the fixture parameters much match.
   pass
```

*Note* the fixture name should match the terraform module name.

## Variable Usage

```python
from pytest_terraform import terraform

gcp_pub_sub = terraform.fixture('gcp_pub_sub')

def test_queue(gcp_pub_sub):
	print(gcp_pub_sub.resources)
```

*Note* the fixture variable name should match the terraform module name.

## Fixture Usage

The pytest fixtures have access to everything within the terraform
state file, with some helpers.

```
def test_

```

*Note* The terraform state file is considered an internal
implementation detail of terraform, not a stable interface. Also


## Fixture support

- This plugin supports all the standard pytest scopes, scope names can
  be passed into the constructors.

- It does not currently support parameterization of terraform fixtures,
  although test functions can freely usee both.

## Replay Support

By default fixtures will save a `tf_resources.json` back to the module
directory, that will be used when in replay mode.

## Rewriting recorded

TODO

## XDist Compatibility

pytest_terraform supports pytest-xdist in multi-process (not distributed)
mode

When run with python-xdist, pytest_terraform treats all non functional
scopes as per test run fixtures across all workers, honoring their
original scope lifecycle but with global semantics, instead of once
per worker. ie. terraform non function scope fixtures are run once
per test run, not per worker.

This in contrast to what regular fixtures do by default with
pytest-xdist, where they are executed at least once per worker. for
infrastructure thats potentially time instensive to setup, this can
negate some of the benefits of running tests in parallel, which is
why pytest-terraform uses global semantics.


### Fixture Resources

the tests will need to access fixture provisioned resources, to do so
the fixture will return a terraform resources instance for each
terraform root module fixture which will have available a mapping of
terraform resource type names to terraform resource names to provider
ids, which will be inferred from the tfstate.json.

### Replay support

For tests executing with replay we'll need to store the fixture
resource id mapping and serialize them to disk from a live
provisioning run to enable a replay run. On replay we'll pick up the
serialized resource ids and return them as the fixture results. We'll
need to do this once per scope instantiation (session, module,
package, function). Note this will be effectively be an independent
mechanism from the existing one as it needs to handled pre test
execution, where as the current record/replay mechanism is done within
a test execution. Some of the DRY violation could be addressed by
refactoring the existing mechanisms to look at fixture decorated
attribute on the test instance.

Configuring record vs replay

```
--tf-record=false|no
--tf-replay=yes
```

### Root module references

`terraform_remote_state` can be used to introduce a dependency between
a scoped root modules on an individual test, note we are not
attempting to support same scope inter fixture dependencies as that
imposes additional scheduling constraints outside of pytest native
capabilities. The higher scoped root module will need to have output
variables to enable this consumption.



