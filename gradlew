#!/bin/sh
# EngX root Gradle launcher.
# Generic CI templates (e.g. Klencod) run "./gradlew :app:assembleDebug" from the npm
# repository root, but the real Gradle project is android/ and needs JDK 21 plus
# node_modules (Capacitor plugins are Gradle subprojects under ../node_modules).
# This script prepares both, then delegates to android/gradlew (Gradle 8.11.1).
set -e
ROOT=$(cd "$(dirname "$0")" && pwd)

java_major() {
  "$1" -version 2>&1 | sed -n 's/.*version "\([0-9]*\).*/\1/p' | head -n 1
}

# Prefer a JDK 21+ if the runner has one besides the (possibly older) default JAVA_HOME.
for candidate in "$JAVA_HOME_21_X64" "$JAVA_HOME_21_ARM64" "$JAVA_HOME_25_X64"; do
  if [ -n "$candidate" ] && [ -x "$candidate/bin/java" ]; then
    export JAVA_HOME="$candidate"
    PATH="$JAVA_HOME/bin:$PATH"
    export PATH
    break
  fi
done

JAVA_BIN=java
[ -n "$JAVA_HOME" ] && [ -x "$JAVA_HOME/bin/java" ] && JAVA_BIN="$JAVA_HOME/bin/java"
MAJOR=$(java_major "$JAVA_BIN")
if [ -z "$MAJOR" ] || [ "$MAJOR" -lt 21 ]; then
  echo "ERROR: EngX needs JDK 21 or newer (found: ${MAJOR:-none}). Set JAVA_HOME to JDK 21." >&2
  exit 1
fi

cd "$ROOT"
if [ ! -d node_modules/@capacitor/android ]; then
  echo "EngX: installing npm dependencies (npm ci)..."
  npm ci --no-audit --no-fund
fi

cd "$ROOT/android"
exec sh ./gradlew "$@"
