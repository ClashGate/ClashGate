"""Byte-level checks for the panel split.

Imported by test_panel.py (CI) and tests/check_guard.py (local, no mihomo).
The golden files were generated from panel.py before the split.
"""
import inspect
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))

NODE = {
    "name": "VlessReality",
    "port": 28443,
    "uuid": "11111111-1111-4111-8111-111111111111",
    "priv": "YQdE8o0kC6k0m0s0kC6k0m0s0kC6k0m0s0kC6k0m0s0",
    "pub": "ZQdE8o0kC6k0m0s0kC6k0m0s0kC6k0m0s0kC6k0m0s0",
    "sid": "01234567",
    "sni": "www.microsoft.com",
    "dec": "mlkem768x25519plus.native.600s.fixed-dec",
    "enc": "mlkem768x25519plus.native.0rtt.fixed-enc",
}
INB = {
    "id": "fixed-ss",
    "name": "ss-fixed",
    "kind": "shadowsocks",
    "port": 30101,
    "listener": {
        "name": "ss-fixed",
        "type": "shadowsocks",
        "port": 30101,
        "listen": "0.0.0.0",
        "password": "fixed-secret",
        "cipher": "chacha20-ietf-poly1305",
        "udp": True,
    },
    "client": {
        "name": "ss-fixed",
        "type": "ss",
        "server": "1.2.3.4",
        "port": 30101,
        "cipher": "chacha20-ietf-poly1305",
        "password": "fixed-secret",
        "udp": True,
    },
}
PROXY = {"name": "out-fixed", "type": "socks5", "server": "9.9.9.9", "port": 1080, "udp": True}
CLUSTER = {
    "instance": "c" * 32,
    "links": [{
        "id": "abc123",
        "instance": "a" * 32,
        "name": "Tokyo-1",
        "url": "https://tokyo.example.com:8443",
        "key": "k" * 43,
        "version": "1.17",
        "created": 1,
        "seen": 1,
        "ok": True,
        "error": "",
        "missing": [],
        "in": {
            "port": 31001,
            "uuid": "66666666-7777-4888-9999-000000000000",
            "decryption": "mlkem768x25519plus.native.600s.fixed-in",
        },
        "out": {
            "server": "tokyo.example.com",
            "port": 31000,
            "uuid": "11111111-2222-4333-8444-555555555555",
            "encryption": "mlkem768x25519plus.native.0rtt.fixed-out",
        },
    }],
    "pending": [],
    "removed": {},
}


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def panel_names(P):
    out = []
    for name, obj in vars(P).items():
        if name.startswith("__") or inspect.ismodule(obj):
            continue
        out.append(name)
    return sorted(out)


def assert_surface(P):
    got = panel_names(P)
    want = _read(os.path.join(HERE, "api_surface.txt")).splitlines()
    missing = [n for n in want if n not in got]
    extra = [n for n in got if n not in want]
    if missing or extra:
        raise AssertionError(
            "panel namespace changed\nmissing: %s\nextra: %s" % (missing, extra)
        )


def assert_goldens(P):
    """Rewrite a fixed tree, compare config and subscription, then remove cluster files."""
    cluster_files = (P.CLUSTER_JSON, P.FRAG_CLUSTER_PROXIES, P.FRAG_CLUSTER_LISTENERS)
    routing_files = (P.ROUTING_JSON, P.FRAG_RULE_PROVIDERS, P.FRAG_PROXY_GROUPS, P.FRAG_RULES)
    for p in cluster_files + routing_files:
        if os.path.exists(p):
            os.remove(p)
    if os.path.isdir(P.ROUTING_DIR):
        shutil.rmtree(P.ROUTING_DIR)
    try:
        prov_name, prov = P.build_proxy_provider("https://example.com/sub.txt", "prov-fixed")
        env = P.read_env()
        P._write_template_state([NODE], [INB], [PROXY], {prov_name: prov}, env)
        conf = _read(P.CONF)
        sub = P.render_subscription(env, live=False)
        P.save_cluster(CLUSTER)
        clustered = P.assemble_config()
        golden = os.path.join(HERE, "golden")
        for name, text in (
            ("template.yaml", conf),
            ("subscription.yaml", sub),
            ("with-cluster.yaml", clustered),
        ):
            want = _read(os.path.join(golden, name))
            if text != want:
                raise AssertionError(name + " differs from tests/golden/" + name)
    finally:
        for p in cluster_files:
            if os.path.exists(p):
                os.remove(p)
        P.get_routing().ensure_seeded(force=True)
