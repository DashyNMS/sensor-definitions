# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security problem. Report privately through [Security → Report a vulnerability](https://github.com/DashyNMS/sensor-definitions/security/advisories/new).

Include the affected generator commit or catalogue version, relevant source path, reproduction steps using synthetic data and potential impact. Do not include credentials or customer network data.

We aim to acknowledge reports within **5 working days**, keep you informed during investigation and confirm when a fix is available. Credit is optional. Please allow time to release a fix before public disclosure.

## Supported versions and scope

Security fixes go into `main` and the next published catalogue as appropriate. Immutable releases are not edited. The active version is in `feeds/v1/stable.json`; enabled consumers receive updates on their normal sync schedule.

In scope: the importer, schemas, workflows, stable feed and generated data, including unsafe parsing, malicious definitions, incorrect provenance, compromised dependencies and publication integrity.

Reader/updater issues belong in [Core](https://github.com/DashyNMS/core); app-specific issues can be reported through [Desktop security](https://github.com/DashyNMS/desktop/security). LibreNMS vulnerabilities belong with [LibreNMS](https://github.com/librenms/librenms/security). Test only systems and repositories you own or have permission to test.

## Checks and trust

CI runs CodeQL for Python and Actions, dependency vulnerability audits, Bandit with a medium/high severity gate, secret detection, importer tests and deterministic builds. Dependabot checks requirements and workflow actions weekly. GitHub secret scanning and push protection provide additional checks.

Clients receive data, never executable discovery code. Hashes detect corruption; they do not authenticate a compromised publisher. Custom repositories trust their publisher. Signature verification is not implemented.

See [the developer guide](docs/DEVELOPMENT.md#security-checks) for local checks. Passing scans document the checks performed, not a guarantee that no vulnerabilities exist.
