#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

BIN_DIR="$TMP_DIR/bin"
mkdir -p "$BIN_DIR"

write_fake_cmd() {
    local name="$1"
    cat >"$BIN_DIR/$name" <<'SH'
#!/usr/bin/env bash
exit 0
SH
    chmod +x "$BIN_DIR/$name"
}

write_fake_cmd python3
write_fake_cmd ffmpeg
write_fake_cmd curl
write_fake_cmd yt-dlp

cat >"$BIN_DIR/pip" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"${PIP_LOG:?}"
exit 0
SH
chmod +x "$BIN_DIR/pip"

run_setup() {
    PATH="$BIN_DIR:/usr/bin:/bin" PIP_LOG="$TMP_DIR/pip.log" /bin/bash "$ROOT_DIR/setup.sh" "$@"
}

assert_contains() {
    local file="$1"
    local pattern="$2"
    if ! grep -q "$pattern" "$file"; then
        echo "Expected $file to contain: $pattern" >&2
        echo "--- $file ---" >&2
        cat "$file" >&2
        exit 1
    fi
}

test_unknown_skill_fails() {
    if run_setup not-a-skill >"$TMP_DIR/unknown.out" 2>"$TMP_DIR/unknown.err"; then
        echo "Expected unknown skill to fail" >&2
        exit 1
    fi
    assert_contains "$TMP_DIR/unknown.err" "未知 skill"
}

test_full_skill_names_install_expected_dependency_groups() {
    : >"$TMP_DIR/pip.log"
    run_setup douyin-transcribe x-ingest wechat-article-ingest >"$TMP_DIR/install.out"

    assert_contains "$TMP_DIR/pip.log" "funasr"
    assert_contains "$TMP_DIR/pip.log" "beautifulsoup4"
}

test_zero_dependency_skill_does_not_require_ffmpeg() {
    rm -f "$BIN_DIR/ffmpeg"
    : >"$TMP_DIR/pip.log"
    run_setup content-enrich >"$TMP_DIR/content.out"

    if [[ -s "$TMP_DIR/pip.log" ]]; then
        echo "Expected content-enrich to install no pip dependencies" >&2
        cat "$TMP_DIR/pip.log" >&2
        exit 1
    fi
    write_fake_cmd ffmpeg
}

test_unknown_skill_fails
test_full_skill_names_install_expected_dependency_groups
test_zero_dependency_skill_does_not_require_ffmpeg

echo "setup.sh tests passed"
