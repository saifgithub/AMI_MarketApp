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
    "AMI_BETA_APPLE_TEAM_ID": "ABCDE12345",
    "AMI_BETA_APP_STORE_API_KEY_ID": "ZZ99YY88XX",
    "AMI_BETA_APP_STORE_API_ISSUER": "00000000-1111-2222-3333-444444444444",
    "AMI_BETA_ONESIGNAL_APP_ID": "11111111-2222-3333-4444-555555555555",
    "AMI_BETA_ANDROID_KEYSTORE_PROPERTIES": "/nonexistent/company/keystore.properties",
    "AMI_BETA_PLAY_SERVICE_ACCOUNT_JSON": "/nonexistent/company/play.json",
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
def test_the_real_project_files_do_not_block_a_fully_configured_beta(real_ids, script):
    """WP-49 prep: the project files keep the personal (Alpha) IDs; the Beta
    build applies the company IDs itself at build time, so a fully configured
    Beta dry-run passes against the unchanged personal project files."""
    r = _run(real_ids, script, *_beta_args(script), env=_BETA_ENV)
    assert r.returncode == 0, r.stderr


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
    assert "PERSONAL-account" in r.stderr
    assert f"{env_name}={personal}" in r.stderr


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


# ── WP-49 prep: company-account values come from a gitignored env file ─────

_PERSONAL_BY_KEY = {
    "AMI_BETA_APPLE_TEAM_ID": "S7RBWM4879",
    "AMI_BETA_APP_STORE_API_KEY_ID": "44VJ5WADL2",
    "AMI_BETA_APP_STORE_API_ISSUER": "289e6201-8fc9-44a3-abde-59e8e278527c",
    "AMI_BETA_ONESIGNAL_APP_ID": "3c2020b6-d8b0-493f-b0e3-5d6ede868d7b",
    "AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID": (
        "153141744056-03d6sabmvita0a2civs6e0ngjoac54v7.apps.googleusercontent.com"
    ),
}

_IOS_KEYS = (
    "AMI_BETA_IOS_BUNDLE_ID",
    "AMI_BETA_APPLE_TEAM_ID",
    "AMI_BETA_APP_STORE_API_KEY_ID",
    "AMI_BETA_APP_STORE_API_ISSUER",
    "AMI_BETA_ONESIGNAL_APP_ID",
)
_ANDROID_KEYS = (
    "AMI_BETA_ANDROID_APPLICATION_ID",
    "AMI_BETA_ANDROID_KEYSTORE_PROPERTIES",
    "AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID",
    "AMI_BETA_ONESIGNAL_APP_ID",
)


def test_beta_names_every_missing_key_in_one_refusal(real_ids):
    r = _run(
        real_ids, "build_testflight.sh", *_beta_args("x"), env={"SENTRY_DSN": _DSN}
    )
    assert r.returncode == 1
    for key in _IOS_KEYS:
        assert key in r.stderr, key
    assert "beta_accounts.env" in r.stderr
    r = _run(
        real_ids, "publish_playstore.sh", *_beta_args("x"), env={"SENTRY_DSN": _DSN}
    )
    assert r.returncode == 1
    for key in (*_ANDROID_KEYS, "AMI_BETA_PLAY_SERVICE_ACCOUNT_JSON"):
        assert key in r.stderr, key


def test_build_playstore_does_not_need_the_service_account(real_ids):
    env = {k: v for k, v in _BETA_ENV.items() if k != "AMI_BETA_PLAY_SERVICE_ACCOUNT_JSON"}
    assert _run(real_ids, "build_playstore.sh", *_beta_args("x"), env=env).returncode == 0
    r = _run(real_ids, "publish_playstore.sh", *_beta_args("x"), env=env)
    assert r.returncode == 1
    assert "AMI_BETA_PLAY_SERVICE_ACCOUNT_JSON" in r.stderr


@pytest.mark.parametrize("key,personal", sorted(_PERSONAL_BY_KEY.items()))
def test_beta_refuses_every_personal_account_value(real_ids, key, personal):
    script = "build_playstore.sh" if key == "AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID" else "build_testflight.sh"
    r = _run(real_ids, script, *_beta_args(script), env={**_BETA_ENV, key: personal})
    assert r.returncode == 1
    assert f"{key}={personal}" in r.stderr


def test_beta_refuses_a_malformed_team_id(real_ids):
    r = _run(
        real_ids,
        "build_testflight.sh",
        *_beta_args("x"),
        env={**_BETA_ENV, "AMI_BETA_APPLE_TEAM_ID": "short"},
    )
    assert r.returncode == 1
    assert "AMI_BETA_APPLE_TEAM_ID must be 10" in r.stderr


def _write_env_file(tree: Path, body: str) -> Path:
    f = tree / "mobile" / "beta_accounts.env"
    f.write_text(body)
    return f


def test_beta_reads_the_accounts_env_file(real_ids):
    body = "# comment\n" + "\n".join(f'{k}="{v}"' for k, v in _BETA_ENV.items()) + "\n"
    _write_env_file(real_ids, body)
    r = _run(real_ids, "build_testflight.sh", *_beta_args("x"), env={})
    assert r.returncode == 0, r.stderr
    assert "bundle id        : co.example.amibeta" in r.stdout
    assert "apple team id    : ABCDE12345" in r.stdout
    assert "abc123secretkey" not in r.stdout


def test_exported_env_wins_over_the_file_and_the_file_is_never_executed(real_ids, tmp_path):
    marker = tmp_path / "executed"
    body = "AMI_BETA_IOS_BUNDLE_ID=co.example.fromfile\n"
    body += "\n".join(f"{k}={v}" for k, v in _BETA_ENV.items() if k != "AMI_BETA_IOS_BUNDLE_ID")
    body += f"\n$(touch {marker})\n`touch {marker}`\n"
    _write_env_file(real_ids, body)
    # exported bundle id wins over the file's
    r = _run(
        real_ids,
        "build_testflight.sh",
        *_beta_args("x"),
        env={"AMI_BETA_IOS_BUNDLE_ID": "co.example.exported"},
    )
    assert r.returncode == 0, r.stderr
    assert "bundle id        : co.example.exported" in r.stdout
    assert not marker.exists()


def test_empty_values_in_the_template_are_treated_as_missing(real_ids):
    shutil.copy(_REPO / "mobile" / "beta_accounts.env.example", real_ids / "mobile" / "beta_accounts.env")
    r = _run(real_ids, "build_testflight.sh", *_beta_args("x"), env={"SENTRY_DSN": _DSN})
    assert r.returncode == 1
    for key in _IOS_KEYS:
        assert key in r.stderr


def test_the_template_lists_every_key_the_lib_reads_and_marks_requirements():
    template = (_REPO / "mobile" / "beta_accounts.env.example").read_text()
    lib = (_REPO / "scripts" / "lib" / "release_channel.sh").read_text()
    block = lib.split("AMI_BETA_ACCOUNT_KEYS=(")[1].split(")")[0]
    for key in block.split():
        assert f"\n{key}=\n" in template, key
    assert template.count("[REQUIRED") >= 9


def test_the_accounts_file_is_gitignored_and_the_template_is_not():
    ignore = (_REPO / ".gitignore").read_text().splitlines()
    assert "mobile/beta_accounts.env" in ignore
    assert (_REPO / "mobile" / "beta_accounts.env.example").exists()


# ── Alpha is unchanged by all of the above ─────────────────────────────────


@pytest.mark.parametrize("script", _SCRIPTS)
def test_alpha_ignores_the_accounts_file_and_beta_env(real_ids, script):
    clean = _run(real_ids, script, "--dry-run")
    body = "\n".join(f"{k}={v}" for k, v in _BETA_ENV.items())
    _write_env_file(real_ids, body)
    polluted = _run(real_ids, script, "--dry-run", env=_BETA_ENV)
    assert clean.returncode == polluted.returncode == 0
    assert clean.stdout == polluted.stdout
    assert "accounts env" not in polluted.stdout


def test_the_committed_project_files_still_carry_the_personal_ids():
    pbx = (_REPO / "mobile/ios/Runner.xcodeproj/project.pbxproj").read_text()
    assert "PRODUCT_BUNDLE_IDENTIFIER = ai.agenticmarketintel.amiTrade;" in pbx
    assert "DEVELOPMENT_TEAM = S7RBWM4879;" in pbx
    gradle = (_REPO / "mobile/android/app/build.gradle.kts").read_text()
    assert 'System.getenv("AMI_GRADLE_APPLICATION_ID") ?: "ai.agenticmarketintel.ami_trade"' in gradle
    assert '?: "${System.getProperty("user.home")}/.android-keys/keystore.properties"' in gradle
    appfile = (_REPO / "mobile/android/fastlane/Appfile").read_text()
    assert 'ENV["AMI_PLAY_PACKAGE_NAME"] || "ai.agenticmarketintel.ami_trade"' in appfile
    export = (_REPO / "mobile/ios/ExportOptions.plist").read_text()
    assert "<string>S7RBWM4879</string>" in export


# ── the Beta wiring functions, run for real against a throwaway tree ───────


def _call(tree: Path, snippet: str, env: dict[str, str] | None = None):
    script = f"""
set -euo pipefail
PROJECT_ROOT="{tree}"
source "{tree}/scripts/lib/release_channel.sh"
{snippet}
"""
    full_env = {"PATH": "/usr/bin:/bin", "HOME": str(tree), "TMPDIR": str(tree)}
    full_env.update(env or {})
    return subprocess.run(
        ["bash", "-c", script], cwd=tree, env=full_env, capture_output=True, text=True, timeout=60
    )


def _pbx(tree: Path) -> Path:
    return tree / "mobile" / "ios" / "Runner.xcodeproj" / "project.pbxproj"


def test_ios_patch_sets_company_ids_then_restores_the_project_byte_for_byte(real_ids):
    before = _pbx(real_ids).read_text()
    pbx = '"$PROJECT_ROOT/mobile/ios/Runner.xcodeproj/project.pbxproj"'
    r = _call(
        real_ids,
        "CHANNEL=beta\nami_beta_ios_patch_project\n"
        f'grep -q "PRODUCT_BUNDLE_IDENTIFIER = co.example.amibeta;" {pbx}\n'
        f'grep -q "DEVELOPMENT_TEAM = ABCDE12345;" {pbx}\n'
        f'grep -q "co.example.amibeta.RunnerTests" {pbx}\n'
        f'! grep -q "S7RBWM4879" {pbx}\n'
        'echo PATCHED_OK',
        env={**_BETA_ENV},
    )
    assert r.returncode == 0, r.stderr
    assert "PATCHED_OK" in r.stdout
    assert "restored the Xcode project" in r.stdout
    assert _pbx(real_ids).read_text() == before


def test_ios_patch_restores_even_when_the_build_dies(real_ids):
    before = _pbx(real_ids).read_text()
    r = _call(real_ids, "CHANNEL=beta\nami_beta_ios_patch_project\nfalse", env={**_BETA_ENV})
    assert r.returncode != 0
    assert _pbx(real_ids).read_text() == before


def test_ios_patch_refuses_a_project_that_is_not_pristine(real_ids):
    _pbx(real_ids).write_text(_PBX_COMPANY)
    r = _call(real_ids, "CHANNEL=beta\nami_beta_ios_patch_project", env={**_BETA_ENV})
    assert r.returncode == 1
    assert "pristine" in r.stderr


def test_ios_patch_is_a_noop_for_alpha(real_ids):
    before = _pbx(real_ids).read_bytes()
    r = _call(real_ids, "CHANNEL=alpha\nami_beta_ios_patch_project\nami_beta_ios_prepare")
    assert r.returncode == 0, r.stderr
    assert _pbx(real_ids).read_bytes() == before
    assert not (real_ids / "mobile" / "build" / "ExportOptions.beta.plist").exists()


def test_ios_prepare_writes_company_export_options_and_never_inherits_alpha_keys(real_ids):
    (real_ids / "mobile" / "ios" / "ExportOptions.plist").write_text(
        (_REPO / "mobile/ios/ExportOptions.plist").read_text()
    )
    r = _call(
        real_ids,
        "CHANNEL=beta\nAPP_STORE_API_KEY_ID=44VJ5WADL2\nREVENUECAT_IOS_SDK_KEY=appl_alpha\n"
        "ami_beta_ios_prepare\n"
        'echo "KEY=$APP_STORE_API_KEY_ID ISSUER=$APP_STORE_API_ISSUER RC=[$REVENUECAT_IOS_SDK_KEY]"',
        env={**_BETA_ENV},
    )
    assert r.returncode == 0, r.stderr
    assert "KEY=ZZ99YY88XX" in r.stdout
    assert "ISSUER=00000000-1111-2222-3333-444444444444" in r.stdout
    assert "RC=[]" in r.stdout
    plist = (real_ids / "mobile" / "build" / "ExportOptions.beta.plist").read_text()
    assert "<string>ABCDE12345</string>" in plist
    assert "S7RBWM4879" not in plist


def test_android_prepare_refuses_a_missing_company_keystore(real_ids):
    r = _call(real_ids, "CHANNEL=beta\nami_beta_android_prepare", env={**_BETA_ENV})
    assert r.returncode == 1
    assert "DEBUG signing" in r.stderr


def test_android_prepare_exports_company_values_for_beta(real_ids, tmp_path):
    props = tmp_path / "company.properties"
    props.write_text("storeFile=/k/company.jks\n")
    sa = tmp_path / "play.json"
    sa.write_text("{}")
    env = {
        **_BETA_ENV,
        "AMI_BETA_ANDROID_KEYSTORE_PROPERTIES": str(props),
        "AMI_BETA_PLAY_SERVICE_ACCOUNT_JSON": str(sa),
    }
    r = _call(
        real_ids,
        "CHANNEL=beta\nAMI_CHANNEL_NEEDS_PLAY_UPLOAD=1\nami_beta_android_prepare\n"
        'echo "ID=$AMI_GRADLE_APPLICATION_ID PKG=$AMI_PLAY_PACKAGE_NAME KS=$AMI_GRADLE_KEYSTORE_PROPERTIES SA=$SUPPLY_JSON_KEY"',
        env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "ID=co.example.amibeta PKG=co.example.amibeta" in r.stdout
    assert f"KS={props}" in r.stdout
    assert f"SA={sa}" in r.stdout


def test_android_prepare_clears_stray_exports_for_alpha(real_ids):
    r = _call(
        real_ids,
        "CHANNEL=alpha\nami_beta_android_prepare\n"
        'echo "ID=[${AMI_GRADLE_APPLICATION_ID:-}] PKG=[${AMI_PLAY_PACKAGE_NAME:-}] KS=[${AMI_GRADLE_KEYSTORE_PROPERTIES:-}]"',
        env={
            "AMI_GRADLE_APPLICATION_ID": "co.example.stray",
            "AMI_PLAY_PACKAGE_NAME": "co.example.stray",
            "AMI_GRADLE_KEYSTORE_PROPERTIES": "/stray",
        },
    )
    assert r.returncode == 0, r.stderr
    assert "ID=[] PKG=[] KS=[]" in r.stdout
