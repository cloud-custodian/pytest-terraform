# Copyright 2020 Kapil Thangavelu
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import subprocess
import sys
from collections import defaultdict

import jmespath
import pytest
from py.path import local


def find_binary(bin_name):
    parts = os.environ["PATH"].split(":")
    for p in parts:
        candidate = os.path.join(p, bin_name)
        if os.path.exists(candidate):
            return candidate


class ModuleNotFound(ValueError):
    """module not found"""


class TerraformRunner(object):

    command_templates = {
        "init": "init {input} {color} {plugin_dir}",
        "apply": "apply {input} {color} {state} {approve} {plan}",
        "plan": "plan {input} {color} {state} {output}",
        "destroy": "destroy {input} {color} {state} {approve}",
    }

    template_defaults = {
        "input": "-input=false",
        "color": "-no-color",
        "approve": "-auto-approve",
    }

    debug = False

    def __init__(
        self,
        work_dir,
        state_path=None,
        module_dir=None,
        plugin_cache=None,
        stream_output=None,
        tf_bin=None,
    ):

        self.work_dir = work_dir
        self.module_dir = module_dir
        # use parent dir of work/data dir to avoid
        # https://github.com/hashicorp/terraform/issues/22999
        self.state_path = state_path or os.path.join(work_dir, "..", "terraform.tfstate")
        self.stream_output = stream_output
        self.plugin_cache = plugin_cache or ""
        self.tf_bin = tf_bin

    def apply(self, plan=True):
        """run terraform apply"""
        if plan is True:
            plan_path = os.path.join(self.work_dir, "tfplan")
            self.plan(plan_path)
            apply_args = self._get_cmd_args("apply", plan=plan_path)
        elif plan:
            apply_args = self._get_cmd_args("apply", plan="")
        self._run_cmd(apply_args)
        return TerraformState.load(self.state_path)

    def plan(self, output=""):
        output = output and "-out=%s" % output or ""
        self._run_cmd(self._get_cmd_args("plan", output=output))

    def init(self):
        self._run_cmd(self._get_cmd_args("init", plugin_dir=""))

    def destroy(self):
        self._run_cmd(self._get_cmd_args("destroy"))

    def _get_cmd_args(self, cmd_name, tf_bin=None, env=None, **kw):
        tf_bin = tf_bin and tf_bin or self.tf_bin
        kw.update(self.template_defaults)
        kw["state"] = self.state_path and "-state=%s" % self.state_path or ""
        return [tf_bin] + list(
            filter(None, self.command_templates[cmd_name].format(**kw).split(" "))
        )

    def _run_cmd(self, args):
        env = dict(os.environ)
        if LazyPluginCacheDir.resolve():
            env["TF_PLUGIN_CACHE_DIR"] = LazyPluginCacheDir.resolve()
        env["TF_IN_AUTOMATION"] = "yes"
        if self.module_dir:
            env["TF_DATA_DIR"] = self.work_dir
        cwd = self.module_dir or self.work_dir
        print("run cmd", args, file=sys.stderr)
        run_cmd = self.debug and subprocess.check_call or subprocess.check_output
        run_cmd(args, cwd=cwd, stderr=subprocess.STDOUT, env=env)


class TerraformState(object):
    """Abstraction over a terrafrom state file with helpers.

    resources dict contains a minimal representation of a terraform
    state file with enough identity information to query a resource
    from the api.

    resources dict is a nested data structure corresponding to
       resource_type -> resource name -> resource attributes.

    by default all resources will have an 'id' attribute, additional
    attributes which contain the key 'name' will also be present.
    """

    def __init__(self, resources, outputs):
        self.outputs = outputs
        self.resources = resources

    def __getitem__(self, k):
        v = self.get(k)
        if v is None:
            raise KeyError(k)
        return v

    def get(self, k, default=None):
        """accessor to resource attributes.

        supports a few shortcuts for ease of use.

        key can be a jmespath expression in which case the evaluation
        is returned.

        if key is a unique resource name, then its data is returned, if
        the data is a singleton key dictionary with 'id', then just then
        the string value of 'id' is returned.
        """
        if "." in k:
            return jmespath.search(k, self.resources)
        found = False
        for rtype in self.resources:
            for rname in self.resources[rtype]:
                if rname == k:
                    assert found is False, "Ambigious resource name %s" % k
                    found = self.resources[rtype][rname]
        if found:
            if len(found) == 1:
                return found["id"]
            return found
        return default

    @classmethod
    def load(cls, state_file):
        resources = {}
        outputs = {}
        with open(state_file) as fh:
            data = json.load(fh)
            if "pytest-terraform" in data:
                return cls(data["resources"], data["outputs"])
            for r in data.get("resources", ()):
                rmap = resources.setdefault(r["type"], {})
                rmap[r["name"]] = dict(r["instances"][0]["attributes"])

            outputs = data.get("outputs", {})
            for m in data.get("modules", ()):
                for k, r in m.get("resources", {}).items():
                    if k.startswith("data"):
                        continue
                    module, rname = k.split(".", 1)
                    rmap = resources.setdefault(module, {})
                    rattrs = {"id": r["primary"]["id"]}
                    for kattr, vattr in r["primary"]["attributes"].items():
                        if "name" in kattr and vattr != rattrs["id"]:
                            rattrs[kattr] = vattr
                    rmap[rname] = rattrs
        return cls(resources, outputs)

    def save(self, state_path):
        with open(state_path, "w") as fh:
            json.dump(
                {
                    "pytest-terraform": 1,
                    "outputs": self.outputs,
                    "resources": self.resources,
                },
                fh,
            )


class TerraformTestApi(TerraformState):
    """public api to tests as fixture value."""


class PlaceHolderValue(object):
    """Lazy / Late resolved named values.

    many of our instantiations are at module import time, to support
    runtime configuration from cli/ini options we utilize a lazy
    loaded value set which is configured for final values via hooks
    (early, post conf, pre collection).)
    """

    def __init__(self, name):
        self.name = name
        self.value = None

    def resolve(self, default=None):
        if not self.value and default:
            raise ValueError("PlaceHolderValue %s not resolved" % self.name)
        return self.value or default


LazyReplay = PlaceHolderValue("tf_replay")
LazyModuleDir = PlaceHolderValue("module_dir")
LazyPluginCacheDir = PlaceHolderValue("plugin_cache")
LazyTfBin = PlaceHolderValue("tf_bin_path")


class TerraformFixture(object):

    _AutoTearDown = True

    def __init__(self, tf_bin, plugin_cache, scope, tf_root_module, test_dir, replay):
        self.tf_bin = tf_bin
        self.tf_root_module = tf_root_module
        self.test_dir = test_dir
        self.scope = scope
        self.replay = replay
        self.runner = None

    @property
    def name(self):
        return "%s" % self.tf_root_module

    __name__ = name

    def resolve_module_dir(self):
        candidates = [
            self.test_dir.join(self.tf_root_module),
            self.test_dir.join("terraform", self.tf_root_module),
            self.test_dir.dirpath().join(self.tf_root_module),
            self.test_dir.dirpath().join("terraform", self.tf_root_module),
        ]
        if LazyModuleDir.resolve():
            candidates.insert(0, local(LazyModuleDir.resolve()).join(self.tf_root_module))
        for candidate in candidates:
            if not candidate.check(exists=1, dir=1):
                continue
            return candidate
        raise ModuleNotFound(self.tf_root_module)

    def get_runner(self, module_dir, work_dir):
        return TerraformRunner(
            str(work_dir),
            module_dir=module_dir,
            plugin_cache=LazyPluginCacheDir.resolve(),
            tf_bin=LazyTfBin.resolve(),
        )

    def __call__(self, request, tmpdir_factory, worker_id):
        module_dir = self.resolve_module_dir()
        if self.replay:
            replay_resources = os.path.join(module_dir, "tf_resources.json")
            if not os.path.exists(replay_resources):
                raise ValueError(
                    "Replay resources don't exist for %s" % self.tf_root_module
                )
            return TerraformTestApi.load(os.path.join(module_dir, "tf_resources.json"))
        work_dir = tmpdir_factory.mktemp(self.tf_root_module, numbered=True).join("work")
        self.runner = self.get_runner(module_dir, work_dir)
        return self.create(request, module_dir)

    def create(self, request, module_dir):
        print("tf create %s" % self.tf_root_module, file=sys.stderr)
        self.runner.init()
        if self._AutoTearDown:
            request.addfinalizer(self.tear_down)
        try:
            test_api = self.runner.apply()
            test_api.save(module_dir.join("tf_resources.json"))
            return test_api
        except Exception:
            raise

    def tear_down(self):
        # config behavor on runner
        print("tf teardown %s" % self.tf_root_module, file=sys.stderr)
        self.runner.destroy()


class FixtureDecoratorFactory(object):
    """Generate fixture decorators on the fly.
    """

    scope_class_map = defaultdict(lambda: TerraformFixture)

    def __init__(self):
        self._fixtures = []

    def get_fixtures(self):
        return list(self._fixtures)

    def get_fixture(self, name):
        for f in self._fixtures:
            if f.name == name:
                return f
        raise KeyError(name)

    def __call__(self, terraform_dir, scope="function", replay=None, name=None):
        # We have to hook into where fixture discovery will find
        # our fixtures, the easiest option is to store on the module that
        # originated the call, all test modules get scanned for
        # fixtures. The alternative is to try and keep a set and
        # store. this particular setup is to support decorator usage.
        # ie. its gross on one hand and very pratical for consumers
        # on the other.
        f = sys._getframe(1)
        name = name or terraform_dir
        test_dir = local(_frame_path(f)).dirpath()
        if replay is None:
            replay = LazyReplay.resolve()
        found = None
        for tf in self._fixtures:
            if tf.tf_root_module == terraform_dir:
                assert scope == tf.scope, (
                    "Same tf module:%s used at different scopes"
                ) % (terraform_dir)
                found = tf
        if found:
            return self.nonce_decorator
        tclass = self.scope_class_map[scope]
        tfix = tclass(
            LazyTfBin, LazyPluginCacheDir, scope, terraform_dir, test_dir, replay,
        )
        self._fixtures.append(tfix)
        marker = pytest.fixture(scope=scope, name=terraform_dir)
        f.f_locals[name] = marker(tfix)
        return self.nonce_decorator

    @staticmethod
    def nonce_decorator(func):
        return func


def _frame_path(f):
    start = f
    while f:
        if "__file__" in f.f_locals:
            return f.f_locals["__file__"]
        f = f.f_back
    raise RuntimeError("frame path not found %s" % start)


terraform = FixtureDecoratorFactory()
