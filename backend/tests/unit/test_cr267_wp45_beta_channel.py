"""CR267 WP-45 — the mobile build scripts' `--channel alpha|beta`.

A Beta build is a different binary from an Alpha one in four ways that can each
ship wrong without anything failing: the URL it talks to, whether the Alpha
backend can be switched to, whether it reports crashes (WP-53's crash-free
figure is Sentry release health), and which store-account identifiers it is
signed under (WP-49 / gate S7). These tests EXECUTE the real scripts through
their `--dry-run`, which parses arguments, applies the channel refusals, prints
the resolved configuration and exits 0 before any gate, pubspec bump, build or
upload. Asserting on the source text would test a citation, not the control
(see DEF296's test for the same reasoning).

The scripts derive their project root from their own location, so each test
copies them into a throwaway tree whose Xcode project / Gradle file declare
whatever IDs the case needs. That is how a *passing* Beta run is reachable
today, while the real repo (still on the personal IDs) refuses every Beta
build, which is the point and is asserted against the real files.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = ("build_testflight.sh", "build_playstore.sh", "publish_playstore.sh")

_ALPHA_URL = "https://api-alpha.agenticmarketintel.ai"
_BETA_URL = "https://api-beta.agenticmarketintel.ai"
_DSN = "https://abc123secretkey@o0.ingest.example.invalid/1"

_CO_IOS = "co.example.amibeta"
_CO_ANDROID = "co.example.amibeta"

_PBX_COMPANY = f"""\
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = {_CO_IOS};
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = {_CO_IOS}.RunnerTests;
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = {_CO_IOS};
"""
_GRADLE_COMPANY = f"""\
android {{
    defaultConfig {{
        applicationId = "{_CO_ANDROID}"
    }}
}}
"""

#: Everything a Beta build needs, supplied. Individual tests remove one thing.
_BETA_ENV = {
    "AMI_BETA_IOS_BUNDLE_ID": _CO_IOS,
    "AMI_BETA_ANDROID_APPLICATION_ID": _CO_ANDROID,
    "AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID": "company-client.apps.example.invalid",
    "SENTRY_DSN": _DSN,
}


def _make_tree(root: Path, *, company_ids: bool) -> Path:
    (root / "scripts" / "lib").mkdir(parents=True)
    for name in _SCRIPTS:
        shutil.copy(_REPO / "scripts" / name, root / "scripts" / name)
    shutil.copy(
        _REPO / "scripts" / "lib" / "release_channel.sh",
        root / "scripts" / "lib" / "release_channel.sh",
    )
    pbx = root / "mobile" / "ios" / "Runner.xcodeproj" / "project.pbxproj"
    gradle = root / "mobile" / "android" / "app" / "build.gradle.kts"
    pbx.parent.mkdir(parents=True)
    gradle.parent.mkdir(parents=True)
    if company_ids:
        pbx.write_text(_PBX_COMPANY)
        gradle.write_text(_GRADLE_COMPANY)
    else:
        shutil.copy(_REPO / "mobile/ios/Runner.xcodeproj/project.pbxproj", pbx)
        shutil.copy(_REPO / "mobile/android/app/build.gradle.kts", gradle)
    return root


@pytest.fixture
def real_ids(tmp_path):
    return _make_tree(tmp_path / "real", company_ids=False)


@pytest.fixture
def company_ids(tmp_path):
    return _make_tree(tmp_path / "company", company_ids=True)


def _run(tree: Path, script: str, *args: str, env: dict[str, str] | None = None):
    full_env = {"PATH": "/usr/bin:/bin", "HOME": str(tree)}
    full_env.update(env or {})
    return subprocess.run(
        ["bash", str(tree / "scripts" / script), *args],
        cwd=tree,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _beta_args(script: str) -> tuple[str, ...]:
    return ("--dry-run", "--channel", "beta", "--no-games")


# ── default channel is alpha and unchanged ─────────────────────────────────


@pytest.mark.parametrize("script", _SCRIPTS)
def test_default_channel_is_alpha_with_the_legacy_defines(real_ids, script):
    r = _run(real_ids, script, "--dry-run")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "release channel: alpha" in out
    assert "--dart-define=ALLOW_BACKEND_SWITCH=true" in out
    assert f"--dart-define=AMI_API_URL_ALPHA={_ALPHA_URL}" in out
    assert "AMI_BETA" not in out
    assert "AMI_API_URL_PROD" not in out
    assert "api-beta" not in out


@pytest.mark.parametrize("script", _SCRIPTS)
def test_explicit_alpha_equals_the_default(real_ids, script):
    default = _run(real_ids, script, "--dry-run")
    explicit = _run(real_ids, script, "--dry-run", "--channel", "alpha")
    equals_form = _run(real_ids, script, "--dry-run", "--channel=alpha")
    assert default.returncode == explicit.returncode == equals_form.returncode == 0
    assert default.stdout == explicit.stdout == equals_form.stdout


def test_alpha_keeps_sentry_optional(real_ids):
    r = _run(real_ids, "build_playstore.sh", "--dry-run", env={"SENTRY_DSN": ""})
    assert r.returncode == 0, r.stderr


def test_alpha_does_not_demand_company_ids(real_ids):
    for script in _SCRIPTS:
        assert _run(real_ids, script, "--dry-run").returncode == 0


@pytest.mark.parametrize("script", ("build_testflight.sh", "build_playstore.sh"))
def test_the_flutter_build_takes_its_channel_defines_from_the_one_place(script):
    """A hard-coded ALLOW_BACKEND_SWITCH=true left beside the channel array
    would silently re-enable the switcher in Beta; what dry-run prints is only
    what the build gets if the build reads the same array."""
    text = (_REPO / "scripts" / script).read_text()
    assert '"${CHANNEL_DEFINES[@]}"' in text
    assert "--dart-define=ALLOW_BACKEND_SWITCH=true" not in text
    assert '--dart-define=AMI_API_URL_ALPHA="' not in text


# ── beta bakes the beta URL and the CR278 define, switcher off ─────────────


@pytest.mark.parametrize("script", _SCRIPTS)
def test_beta_bakes_the_beta_url_the_define_and_no_switcher(company_ids, script):
    r = _run(company_ids, script, *_beta_args(script), env=_BETA_ENV)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "release channel: beta" in out
    assert f"--dart-define=AMI_API_URL_PROD={_BETA_URL}" in out
    assert "--dart-define=AMI_BETA=true" in out
    assert "--dart-define=AMI_ENV=beta" in out
    assert "--dart-define=ALLOW_BACKEND_SWITCH=false" in out
    # Cannot be pointed at Alpha: the switch is off and the Alpha host is not
    # among the defines at all.
    assert "ALLOW_BACKEND_SWITCH=true" not in out
    assert "api-alpha" not in out
    assert "AMI_API_URL_ALPHA" not in out
    # The DSN is reported as present, never echoed.
    assert "abc123secretkey" not in out
    assert "SENTRY_DSN" in out


def test_beta_url_can_be_overridden_by_env(company_ids):
    r = _run(
        company_ids,
        "build_playstore.sh",
        *_beta_args("build_playstore.sh"),
        env={**_BETA_ENV, "AMI_API_URL_BETA": "https://beta.example.invalid"},
    )
    assert r.returncode == 0, r.stderr
    assert "AMI_API_URL_PROD=https://beta.example.invalid" in r.stdout


def test_beta_rejects_a_non_https_url(company_ids):
    r = _run(
        company_ids,
        "build_playstore.sh",
        *_beta_args("build_playstore.sh"),
        env={**_BETA_ENV, "AMI_API_URL_BETA": "http://insecure.example.invalid"},
    )
    assert r.returncode == 1
    assert "https" in r.stderr


# ── beta refuses without a DSN ─────────────────────────────────────────────


@pytest.mark.parametrize("script", _SCRIPTS)
@pytest.mark.parametrize("dsn", [None, ""])
def test_beta_refuses_an_empty_or_missing_dsn(company_ids, script, dsn):
    env = {k: v for k, v in _BETA_ENV.items() if k != "SENTRY_DSN"}
    if dsn is not None:
        env["SENTRY_DSN"] = dsn
    r = _run(company_ids, script, *_beta_args(script), env=env)
    assert r.returncode == 1
    assert "SENTRY_DSN is empty" in r.stderr
    assert "release channel: beta" not in r.stdout


def test_beta_refuses_a_malformed_dsn(company_ids):
    r = _run(
        company_ids,
        "build_testflight.sh",
        *_beta_args("build_testflight.sh"),
        env={**_BETA_ENV, "SENTRY_DSN": "not-a-dsn"},
    )
    assert r.returncode == 1
    assert "does not look like a DSN" in r.stderr


# ── beta refuses without the WP-49 identifiers ─────────────────────────────


@pytest.mark.parametrize(
    "script,env_name",
    [
        ("build_testflight.sh", "AMI_BETA_IOS_BUNDLE_ID"),
        ("build_playstore.sh", "AMI_BETA_ANDROID_APPLICATION_ID"),
        ("publish_playstore.sh", "AMI_BETA_ANDROID_APPLICATION_ID"),
    ],
)
def test_beta_refuses_without_company_ids_and_names_wp49(company_ids, script, env_name):
    env = {k: v for k, v in _BETA_ENV.items() if k != env_name}
    r = _run(company_ids, script, *_beta_args(script), env=env)
    assert r.returncode == 1
    assert env_name in r.stderr
    assert "WP-49" in r.stderr
    assert "S7" in r.stderr


@pytest.mark.parametrize("script", _SCRIPTS)
def test_the_real_repo_still_refuses_every_beta_build(real_ids, script):
    """The project files in this checkout still carry the personal IDs, so with
    the env supplied and everything else in order, Beta must still refuse."""
    env = {
        **_BETA_ENV,
        "AMI_BETA_IOS_BUNDLE_ID": "co.example.amibeta",
        "AMI_BETA_ANDROID_APPLICATION_ID": "co.example.amibeta",
    }
    r = _run(real_ids, script, *_beta_args(script), env=env)
    assert r.returncode == 1
    assert "project declares" in r.stderr


@pytest.mark.parametrize(
    "script,env_name,personal",
    [
        ("build_testflight.sh", "AMI_BETA_IOS_BUNDLE_ID", "ai.agenticmarketintel.amiTrade"),
        ("build_playstore.sh", "AMI_BETA_ANDROID_APPLICATION_ID", "ai.agenticmarketintel.ami_trade"),
    ],
)
def test_beta_refuses_the_personal_account_id(real_ids, script, env_name, personal):
    r = _run(real_ids, script, *_beta_args(script), env={**_BETA_ENV, env_name: personal})
    assert r.returncode == 1
    assert "personal-account ID" in r.stderr


def test_beta_refuses_when_env_and_project_disagree(company_ids):
    r = _run(
        company_ids,
        "build_testflight.sh",
        *_beta_args("build_testflight.sh"),
        env={**_BETA_ENV, "AMI_BETA_IOS_BUNDLE_ID": "co.example.other"},
    )
    assert r.returncode == 1
    assert "project declares" in r.stderr


def test_beta_android_refuses_without_the_company_google_client(company_ids):
    env = {k: v for k, v in _BETA_ENV.items() if k != "AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID"}
    r = _run(company_ids, "build_playstore.sh", *_beta_args("build_playstore.sh"), env=env)
    assert r.returncode == 1
    assert "AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID" in r.stderr


# ── other refusals ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("script", _SCRIPTS)
def test_beta_refuses_with_games_on(company_ids, script):
    r = _run(company_ids, script, "--dry-run", "--channel", "beta", env=_BETA_ENV)
    assert r.returncode == 1
    assert "AMI_GAMES is on" in r.stderr


@pytest.mark.parametrize("script", _SCRIPTS)
def test_unknown_channel_is_a_usage_error(real_ids, script):
    r = _run(real_ids, script, "--dry-run", "--channel", "gamma")
    assert r.returncode == 2
    assert "unknown --channel" in r.stderr


@pytest.mark.parametrize("script", _SCRIPTS)
def test_channel_flag_without_a_value_is_a_usage_error(real_ids, script):
    r = _run(real_ids, script, "--dry-run", "--channel")
    assert r.returncode == 2


@pytest.mark.parametrize("script", _SCRIPTS)
def test_every_script_still_parses(script):
    r = subprocess.run(["bash", "-n", str(_REPO / "scripts" / script)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run(
        ["bash", "-n", str(_REPO / "scripts" / "lib" / "release_channel.sh")],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
