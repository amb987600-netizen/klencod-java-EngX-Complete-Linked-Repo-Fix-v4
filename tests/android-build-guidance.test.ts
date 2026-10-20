import { describe, expect, it } from 'vitest';
import { readFileSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';

const root = resolve(process.cwd());
const script = join(root, 'scripts/android-apk.mjs');

describe('Capacitor Android build entry point', () => {
  it('uses Capacitor instead of Flutter in the workflow', () => {
    const workflow = readFileSync(join(root, '.github/workflows/android-apk.yml'), 'utf8');
    const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
    expect(workflow).not.toMatch(/flutter-action|flutter pub get|flutter build apk/);
    expect(workflow).toContain("java-version: '21'");
    expect(workflow).toContain("node-version: '22'");
    expect(workflow).toContain('run: npm ci');
    expect(workflow).toContain('run: npm run android:doctor');
    expect(workflow).toContain('run: npm test');
    expect(workflow).toMatch(/working-directory: \$\{\{ steps\.project\.outputs\.root \}\}\s+run: npm run android:sync/);
    expect(workflow).toMatch(/working-directory: \$\{\{ steps\.project\.outputs\.root \}\}\/android\s+shell: bash\s+run: \|/);
    expect(workflow).toContain('test -f settings.gradle');
    expect(workflow).toContain('sh ./gradlew --no-daemon :app:assembleDebug');
    expect(workflow.indexOf('run: npm run android:sync')).toBeLessThan(workflow.indexOf('sh ./gradlew --no-daemon :app:assembleDebug'));
    expect(workflow).not.toMatch(/\n\s+gradle --/);
    expect(workflow).toContain('/android/app/build/outputs/apk/debug/app-debug.apk');
    expect(workflow).toContain('cache-dependency-path:');
    expect(workflow).toContain("root='EngX'");
    expect(workflow).toContain('ENGX_CAPACITOR_REPO_FIX_V2');
    expect(workflow).toMatch(/push:\s+branches: \['\*\*'\]/);
    expect(workflow).toContain('workflow_dispatch:');
    expect(workflow).toContain('cancel-in-progress: true');
    expect(pkg.scripts['android:sync']).toBe('npm run build && cap sync android');
    expect(pkg.scripts['android:apk']).toBe('node scripts/android-apk.mjs');
  });

  it('overrides obsolete SDK defaults with only the required valid packages', () => {
    const workflow = readFileSync(join(root, '.github/workflows/android-apk.yml'), 'utf8');
    const sdkStep = workflow.match(/uses: android-actions\/setup-android@v3\s+with:\s+(?:#[^\n]*\n\s+)*packages: '([^']+)'/);
    expect(sdkStep).not.toBeNull();
    const packages = sdkStep![1].trim().split(/\s+/);
    expect(packages).toEqual(['platform-tools', 'platforms;android-35', 'build-tools;35.0.0']);
    expect(packages).not.toContain('tools');
    const variables = readFileSync(join(root, 'android/variables.gradle'), 'utf8');
    expect(variables).toMatch(/compileSdkVersion\s*=\s*35\b/);
    expect(variables).toMatch(/targetSdkVersion\s*=\s*35\b/);
  });

  it('prints help when launched outside the source directory', () => {
    const result = spawnSync(process.execPath, [script, '--help'], { cwd: tmpdir(), encoding: 'utf8' });
    expect(result.status).toBe(0);
    expect(result.stdout).toContain('NOT Flutter');
    expect(result.stdout).toContain('app-debug.apk');
  });

  it('fails clearly before building if the SDK is missing', () => {
    const missing = join(tmpdir(), 'engx-sdk-intentionally-missing');
    const result = spawnSync(process.execPath, [script, '--check'], {
      cwd: tmpdir(), encoding: 'utf8',
      env: { ...process.env, ANDROID_HOME: missing, ANDROID_SDK_ROOT: missing },
    });
    expect(result.status).toBe(1);
    expect(result.stdout).toContain(`Project root: ${root}`);
    expect(result.stdout).toContain('MISSING: Android SDK');
    expect(result.stderr).toContain('no build was started');
    expect(result.stdout).not.toContain('> engx@');
  });

  it('checks SDK structure without claiming compilation (mock SDK and Java)', () => {
    const fixture = mkdtempSync(join(tmpdir(), 'engx-prereq-test-'));
    try {
      mkdirSync(join(fixture, 'platforms/android-35'), { recursive: true });
      writeFileSync(join(fixture, 'platforms/android-35/android.jar'), 'mock');
      mkdirSync(join(fixture, 'build-tools/35.0.0'), { recursive: true });
      mkdirSync(join(fixture, 'jdk/bin'), { recursive: true });
      writeFileSync(join(fixture, 'jdk/bin/java'), '#!/bin/sh\necho \'openjdk version "21.0.1"\' >&2\n', { mode: 0o755 });
      const result = spawnSync(process.execPath, [script, '--check'], {
        cwd: tmpdir(), encoding: 'utf8',
        env: { ...process.env, JAVA_HOME: join(fixture, 'jdk'), ANDROID_HOME: fixture, ANDROID_SDK_ROOT: fixture },
      });
      expect(result.status).toBe(0);
      expect(result.stdout).toContain('APK compilation has NOT been tested');
    } finally {
      rmSync(fixture, { recursive: true, force: true });
    }
  });
});

describe('Android resources', () => {
  it('defines every @color/ resource referenced by the Android theme and manifest', () => {
    const res = join(root, 'android/app/src/main/res');
    const styles = readFileSync(join(res, 'values/styles.xml'), 'utf8');
    const colors = readFileSync(join(res, 'values/colors.xml'), 'utf8');
    const used = [...styles.matchAll(/@color\/(\w+)/g)].map((m) => m[1]);
    expect(used.length).toBeGreaterThan(0);
    for (const name of used) expect(colors).toContain(`name="${name}"`);
  });
});

describe('Root Gradle launcher for generic CI templates', () => {
  it('delegates ./gradlew from the repository root to android/ with JDK 21 and npm deps', () => {
    const launcher = readFileSync(join(root, 'gradlew'), 'utf8');
    expect(launcher).toContain('cd "$ROOT/android"');
    expect(launcher).toContain('exec sh ./gradlew "$@"');
    expect(launcher).toContain('JAVA_HOME_21_X64');
    expect(launcher).toContain('npm ci');
  });
});

describe('Android dependency compatibility', () => {
  it('pins androidx.browser to a release compatible with compileSdk 35 and AGP 8.7.2', () => {
    const gradle = readFileSync(join(root, 'android/build.gradle'), 'utf8');
    expect(gradle).toContain("force 'androidx.browser:browser:1.8.0'");
    expect(gradle).toContain('com.android.tools.build:gradle:8.7.2');
  });
});
