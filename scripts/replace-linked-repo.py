#!/usr/bin/env python3
"""Copy this complete source into an existing local clone. Preview by default."""
import argparse
import datetime
from pathlib import Path
import re
import shutil

SOURCE = Path(__file__).resolve().parent.parent
WORKFLOW = Path('.github/workflows/android-apk.yml')
SKIP = {'.git', 'node_modules', '.gradle', 'build', 'coverage', '__pycache__', '.engx-workflow-backups'}
ANDROID_MARKERS = re.compile(r'build\s+android\s+java\s+apk|setup-android|assemble(?:debug|release)|flutter\s+build\s+apk|klencod-gradle|gradle[^\n]*:app:', re.I)


def source_files():
    for path in sorted(SOURCE.rglob('*')):
        relative = path.relative_to(SOURCE)
        if any(part in SKIP for part in relative.parts):
            continue
        if path.is_symlink():
            raise SystemExit(f'Symlink in source is not allowed: {relative}')
        if path.is_file() and path.name not in {'local.properties', '.env'} and not path.name.endswith(('.log', '.sqlite', '.jks', '.keystore')):
            yield path, relative


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', help='Path to an existing local Git clone')
    parser.add_argument('--apply', action='store_true', help='Actually copy and back up conflicting Android workflows')
    args = parser.parse_args()
    target = Path(args.repository).expanduser().resolve()
    if target == SOURCE or SOURCE in target.parents or target in SOURCE.parents:
        parser.error('Source and target must be separate, non-nested directories.')
    if not target.is_dir() or not (target / '.git').exists():
        parser.error('Target must be an existing local Git clone; its .git will be preserved.')
    files = list(source_files())
    # Reject links before touching the destination, including symlinked parents.
    for _, relative in files:
        destination = target / relative
        if destination.is_symlink() or any(parent.is_symlink() for parent in destination.parents if parent != target and target in parent.parents):
            parser.error(f'Destination symlink is not allowed: {relative}')
    workflow_dir = target / '.github/workflows'
    conflicts = []
    if workflow_dir.exists():
        for old in sorted(workflow_dir.iterdir()):
            if old.is_file() and old.suffix.lower() in {'.yml', '.yaml'}:
                if old.relative_to(target) == WORKFLOW or ANDROID_MARKERS.search(old.read_text(encoding='utf-8-sig')):
                    conflicts.append(old)
    print(f'Source: {SOURCE}\nTarget: {target}\nFiles to copy: {len(files)}')
    print('Android workflows to back up and replace/disable:')
    for old in conflicts:
        print(f'  {old.relative_to(target)}')
    if not args.apply:
        print('PREVIEW ONLY. Review this list, then repeat with --apply. No files were changed.')
        return
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = target / '.engx-workflow-backups' / stamp
    for old in conflicts:
        backup.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old), str(backup / old.name))
    for path, relative in files:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    print('DONE. Existing application files with the same names were replaced. Other repository files were retained.')
    print(f'Workflow backups (not active): {backup}')
    print('Review git status and the diff before committing. No commit, push or APK build was performed.')
    print('Check .github/workflows manually for Android workflows not recognized by this tool.')


if __name__ == '__main__':
    main()
