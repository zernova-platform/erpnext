"""Small shared validation/command helpers. Never shell-interpolate user inputs."""
import json
import re
import subprocess

IMAGE_REPOSITORY = 'ghcr.io/zernova-platform/ibtinex-erpnext'

def valid_project(value):
    if not re.fullmatch(r'ibtinex-[a-z0-9][a-z0-9-]{1,45}', value):
        raise ValueError('Project must start ibtinex- and use lowercase letters, digits and hyphens.')
    return value

def valid_site(value):
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,120}[a-z0-9]', value) or '..' in value:
        raise ValueError('Invalid site name.')
    return value

def valid_image(value, *, ci=False):
    if ci and re.fullmatch(r'ibtinex-ci:[a-f0-9]{40}', value):
        return value
    if not re.fullmatch(re.escape(IMAGE_REPOSITORY) + r'@sha256:[a-f0-9]{64}', value):
        raise ValueError('Use the published IBTINEX image with its full sha256 digest.')
    return value

def valid_dependency(value):
    if not re.fullmatch(r'(?:[a-z0-9./_-]+)@sha256:[a-f0-9]{64}', value):
        raise ValueError('Dependency images must use a full sha256 digest.')
    return value

def redact(text, secrets=()):
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, '[REDACTED]')
    return text

def run(args, *, cwd=None, env=None, secrets=(), capture=True, input=None):
    result = subprocess.run([str(x) for x in args], cwd=cwd, env=env, input=input,
                            text=True, stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.STDOUT if capture else None)
    if result.returncode:
        output = redact(result.stdout or '', secrets)[-18000:]
        raise RuntimeError(f'Command failed (exit {result.returncode}): {args[0]}\n{output}')
    return result.stdout or ''

def write_json(path, data):
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n', encoding='utf-8')
