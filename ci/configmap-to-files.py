"""Write each key of a ConfigMap from rendered Kubernetes YAML (for example
`helm template` output) to a file, so tools can check the real config.

Usage: python3 ci/configmap-to-files.py <rendered.yaml> <configmap-name> <out-dir>
"""
import os
import sys

import yaml

path, name, out = sys.argv[1:4]
with open(path) as f:
    docs = [d for d in yaml.safe_load_all(f) if d]
cms = [d for d in docs if d.get("kind") == "ConfigMap" and d["metadata"]["name"] == name]
assert len(cms) == 1, "expected one ConfigMap named %s, found %d" % (name, len(cms))
os.makedirs(out, exist_ok=True)
for key, value in cms[0]["data"].items():
    with open(os.path.join(out, key), "w") as f:
        f.write(value)
    print("wrote %s" % os.path.join(out, key))
