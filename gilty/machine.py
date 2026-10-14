"""Which cloud instance type GILty runs on, when it can tell.

In order:
  1. GILTY_INSTANCE_TYPE, if set;
  2. Kubernetes: the node.kubernetes.io/instance-type label of the node in
     NODE_NAME (set it from the downward API, spec.nodeName), read with the
     pod's service account, which needs `get` on nodes;
  3. the AWS instance metadata service (IMDSv2), outside Kubernetes or where
     pods may reach it.
Every lookup is quick (sub-second timeouts) and fails quietly: GILty then
names the CPU only.
"""

import json
import os
import ssl
import urllib.request

SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"
LABELS = ("node.kubernetes.io/instance-type", "beta.kubernetes.io/instance-type")
IMDS = "http://169.254.169.254"


def from_kubernetes(node, api=None, token_file=f"{SA_DIR}/token", ca_file=f"{SA_DIR}/ca.crt", timeout=2.0):
    """The instance-type label of a node, or None."""
    if api is None:
        host, port = os.environ.get("KUBERNETES_SERVICE_HOST"), os.environ.get("KUBERNETES_SERVICE_PORT", "443")
        if not host:
            return None
        api = f"https://[{host}]:{port}" if ":" in host else f"https://{host}:{port}"
    try:
        with open(token_file) as f:
            token = f.read().strip()
        req = urllib.request.Request(f"{api}/api/v1/nodes/{node}", headers={"Authorization": f"Bearer {token}"})
        ctx = ssl.create_default_context(cafile=ca_file) if api.startswith("https") else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            labels = json.load(resp).get("metadata", {}).get("labels", {})
    except (OSError, ValueError):  # no token, no access (403), no API, bad JSON
        return None
    for key in LABELS:
        if labels.get(key):
            return labels[key]
    return None


def from_aws_imds(base=IMDS, timeout=0.3):
    """The EC2 instance type from IMDSv2, or None."""
    try:
        req = urllib.request.Request(f"{base}/latest/api/token", method="PUT",
                                     headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            token = resp.read().decode()
        req = urllib.request.Request(f"{base}/latest/meta-data/instance-type",
                                     headers={"X-aws-ec2-metadata-token": token})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            value = resp.read().decode().strip()
    except (OSError, ValueError):
        return None
    return value if value and len(value) < 64 and " " not in value else None


def instance_type():
    if os.environ.get("GILTY_INSTANCE_TYPE"):
        return os.environ["GILTY_INSTANCE_TYPE"]
    node = os.environ.get("NODE_NAME")
    if node:
        found = from_kubernetes(node)
        if found:
            return found
    return from_aws_imds()
