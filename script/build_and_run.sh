#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="RSSReaderApp"
BUNDLE_ID="com.joaovalente.RSSReaderApp"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DERIVED_DATA="$ROOT_DIR/build/DerivedData"
APP_BUNDLE="$DERIVED_DATA/Build/Products/Debug/RSSReaderApp.app"
APP_BINARY="$APP_BUNDLE/Contents/MacOS/$APP_NAME"

pkill -x "$APP_NAME" >/dev/null 2>&1 || true

build_app() {
  DEVELOPER_DIR=/Applications/Xcode-beta3.app/Contents/Developer \
    xcodebuild \
      -project "$ROOT_DIR/RSSReaderApp.xcodeproj" \
      -scheme 'RSSReaderApp (macOS)' \
      -configuration Debug \
      -destination 'platform=macOS' \
      -derivedDataPath "$DERIVED_DATA" \
      -allowProvisioningUpdates
}

open_app() {
  /usr/bin/open -n "$APP_BUNDLE"
}

case "$MODE" in
  run)
    build_app
    open_app
    ;;
  --debug|debug)
    build_app
    lldb -- "$APP_BINARY"
    ;;
  --logs|logs)
    build_app
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$APP_NAME\""
    ;;
  --telemetry|telemetry)
    build_app
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"$BUNDLE_ID\""
    ;;
  --verify|verify)
    build_app
    open_app
    sleep 1
    pgrep -x "$APP_NAME" >/dev/null
    ;;
  *)
    echo "usage: $0 [run|--debug|--logs|--telemetry|--verify]" >&2
    exit 2
    ;;
esac
