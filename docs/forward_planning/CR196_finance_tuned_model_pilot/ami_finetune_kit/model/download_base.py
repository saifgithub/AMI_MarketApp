#!/usr/bin/env python3
"""download_base.py — pull the training base checkpoint from Hugging Face and verify it.

CR196 offsite kit. Downloads fastino/Fastino-Nemotron-3.5-Lightning-Finance at the pinned
revision and SHA256-verifies every weight shard against expected_sha256.json (which was
machine-copied from the merge-provenance.json of an already-validated copy). A mismatch is
a hard stop: do NOT train on unverified weights — report the mismatch back instead.

Usage:  python3 download_base.py --dest /models/fastino-finance-bf16
Needs:  pip install huggingface_hub  (in setup.sh); ~70G free disk at --dest; internet.
"""
import argparse, hashlib, json, os, sys

MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expected_sha256.json")


def sha256_file(path, bufsize=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", required=True)
    ap.add_argument("--skip-download", action="store_true",
                    help="verify an existing directory only")
    args = ap.parse_args()

    m = json.load(open(MANIFEST))
    if not args.skip_download:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=m["hf_repo"],
            revision=m["pinned_revision"],
            local_dir=args.dest,
        )

    bad, missing = [], []
    for name, expected in sorted(m["weight_shard_sha256"].items()):
        p = os.path.join(args.dest, name)
        if not os.path.exists(p):
            missing.append(name)
            continue
        actual = sha256_file(p)
        status = "OK" if actual == expected else "MISMATCH"
        print(f"{status}  {name}")
        if actual != expected:
            bad.append((name, expected, actual))

    if missing or bad:
        print(f"\nVERDICT: FAIL — {len(missing)} missing, {len(bad)} mismatched shard(s).")
        for name, exp, act in bad:
            print(f"  {name}\n    expected {exp}\n    actual   {act}")
        print("Do not train. Report this output back.")
        sys.exit(1)
    print(f"\nVERDICT: PASS — all {len(m['weight_shard_sha256'])} shards verified against "
          f"{m['hf_repo']}@{m['pinned_revision'][:12]}.")


if __name__ == "__main__":
    main()
