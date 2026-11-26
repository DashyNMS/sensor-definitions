# Accessibility

The catalogue supports apps and services that read the versioned sensor catalogue; current platform requirements are in
[the developer guide](docs/DEVELOPMENT.md). We have not completed a formal
accessibility conformance audit and do not claim WCAG conformance.

Report a barrier through [a bug report](https://github.com/DashyNMS/sensor-definitions/issues/new?template=bug_report.yml&labels=accessibility).
Include the version, platform, assistive technology and a minimal example with
synthetic data. You can also contact [dashynms@pckp.net](mailto:dashynms@pckp.net)
if a public report is unsuitable. The project maintainer reviews accessibility
reports alongside other bugs and records verified limitations in linked issues.

This repository has no graphical interface. Text, API and data contracts affect
accessibility in consuming apps; report the affected field, label or output and
the app or client that displays it. UI barriers belong in the consuming
[desktop](https://github.com/DashyNMS/desktop) or
[mobile](https://github.com/DashyNMS/mobile) repository.
