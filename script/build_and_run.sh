#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="RSSReaderApp"
BUNDLE_ID="com.joaovalente.RSSReaderApp"
PROJECT="RSSReaderApp.xcodeproj"
SCHEME="RSSReaderApp (macOS)"
CONFIGURATION="Debug"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DERIVED_DATA_PATH="$ROOT_DIR/build/DerivedData-MacRun"
PRODUCTS_DIR="$DERIVED_DATA_PATH/Build/Products/$CONFIGURATION"
APP_BUNDLE="$PRODUCTS_DIR/$APP_NAME.app"

cd "$ROOT_DIR"

pkill -x "$APP_NAME" >/dev/null 2>&1 || true

xcodebuild \
  -project "$PROJECT" \
  -scheme "$SCHEME" \
  -configuration "$CONFIGURATION" \
  -destination 'platform=macOS' \
  -derivedDataPath "$DERIVED_DATA_PATH" \
  SWIFT_ENABLE_EXPLICIT_MODULES=NO \
  build

if [[ ! -d "$APP_BUNDLE" ]]; then
  APP_BUNDLE="$(find "$PRODUCTS_DIR" -maxdepth 1 -name '*.app' -type d | head -n 1)"
fi

if [[ -z "${APP_BUNDLE:-}" || ! -d "$APP_BUNDLE" ]]; then
  echo "Unable to find built .app bundle in $PRODUCTS_DIR" >&2
  exit 1
fi

open_app() {
  /usr/bin/open -n "$APP_BUNDLE"
}

case "$MODE" in
  run)
    open_app
    ;;
  --debug|debug)
    lldb -- "$APP_BUNDLE/Contents/MacOS/$APP_NAME"
    ;;
  --logs|logs)
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$APP_NAME\""
    ;;
  --telemetry|telemetry)
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"$BUNDLE_ID\""
    ;;
  --verify|verify)
    open_app
    sleep 1
    pgrep -x "$APP_NAME" >/dev/null
    ;;
  *)
    echo "usage: $0 [run|--debug|--logs|--telemetry|--verify]" >&2
    exit 2
    ;;
esac
