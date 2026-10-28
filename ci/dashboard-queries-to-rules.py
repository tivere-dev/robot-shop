"""Turn every PromQL query in a Grafana dashboard into a recording rule, so
`promtool check rules` reports any query that does not parse.

Grafana variables are replaced with sample values first ($__rate_interval
-> 5m, $namespace -> robot-shop).

Usage: python3 ci/dashboard-queries-to-rules.py <dashboard.json> <out.yaml>
"""
import json
import sys

import yaml

VARIABLES = {"$__rate_interval": "5m", "$namespace": "robot-shop"}

with open(sys.argv[1]) as f:
    dashboard = json.load(f)

rules = []
for panel in dashboard["panels"]:
    for target in panel.get("targets", []):
        expr = target["expr"]
        for name, value in VARIABLES.items():
            expr = expr.replace(name, value)
        rules.append({"record": "dashboard:panel_%d_%s" % (panel["id"], target["refId"].lower()),
                      "expr": expr})

with open(sys.argv[2], "w") as f:
    yaml.safe_dump({"groups": [{"name": "dashboard-queries", "rules": rules}]}, f, sort_keys=False)
print("wrote %s: %d queries" % (sys.argv[2], len(rules)))
