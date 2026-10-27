"""Write the rule groups of a PrometheusRule (Kubernetes object) as a plain
Prometheus rules file, so promtool can check and unit-test them.

Usage: python3 ci/prometheusrule-to-rules.py <PrometheusRule.yaml> <out.yaml>
"""
import sys

import yaml

with open(sys.argv[1]) as f:
    obj = yaml.safe_load(f)
assert obj["kind"] == "PrometheusRule", "not a PrometheusRule"
with open(sys.argv[2], "w") as f:
    yaml.safe_dump({"groups": obj["spec"]["groups"]}, f, sort_keys=False)
print("wrote %s: %d groups" % (sys.argv[2], len(obj["spec"]["groups"])))
