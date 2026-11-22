# Hybrid Patch Compliance Auditor

Cross-platform, read-only patch posture auditing for Linux and Windows. It inventories pending Linux package updates and Windows installed KB hotfixes, then retrieves official security advisory reference data.

> **Scope note:** This first release is an inventory/compliance baseline. Linux pending updates are detected through the host's package manager and cached repository metadata. Debian/Ubuntu security feeds and the Microsoft Security Update Guide API are downloaded as reference context. It does **not** yet claim complete package/KB-to-advisory remediation correlation, since vendors backport fixes and applicability depends on distro release and Windows build.

## Features

- Linux: detects APT, DNF, or YUM and lists available package updates.
- Debian: retrieves the official Debian Security Tracker JSON feed.
- Ubuntu: retrieves the release-specific official OVAL feed.
- Windows: inventories installed KB hotfixes using PowerShell.
- Windows: fetches Microsoft Security Response Center update metadata.
- Human-readable terminal report, JSON output, and CSV export.
- Network timeout/error handling and a vendor-feed bypass switch.
- Read-only by design: no package installs, no service changes, and no automatic repository refresh.

## Requirements

- Python 3.9+
- Linux: APT/DNF/YUM tools (depending on distribution)
- Windows: Windows PowerShell or PowerShell 7
- Internet access for advisory reference requests (optional)

## Usage

Run directly:

```bash
python3 hybrid_patch_compliance_auditor.py
```

JSON report:

```bash
python3 hybrid_patch_compliance_auditor.py --json
```

CSV export:

```bash
python3 hybrid_patch_compliance_auditor.py --csv patch_report.csv
```

Skip online vendor requests (offline mode):

```bash
python3 hybrid_patch_compliance_auditor.py --no-vendor
```

Help:

```bash
python3 hybrid_patch_compliance_auditor.py --help
```

### Linux

Refresh repository metadata manually before running if you want current package candidates:

```bash
sudo apt update
python3 hybrid_patch_compliance_auditor.py
```

APT refresh is not performed by the auditor itself. DNF/YUM use their normal repository metadata and check-update operations.

### Windows

Open PowerShell, navigate to the script directory, and run:

```powershell
python .\hybrid_patch_compliance_auditor.py
python .\hybrid_patch_compliance_auditor.py --json
python .\hybrid_patch_compliance_auditor.py --csv patch_report.csv
```

## Interpreting statuses

- **PATCHES_PENDING**: package manager reports updates available.
- **NO_PENDING_UPDATES_IN_CACHED_METADATA**: no updates found in the metadata currently cached locally. This is not proof that the system is fully secure.
- **INVENTORY_ONLY**: Windows KB inventory is collected, but full KB applicability and OS-build remediation scoring is not implemented yet.

## API sources

- Debian Security Tracker: https://security-tracker.debian.org/tracker/data/json
- Ubuntu OVAL feeds: https://security.ubuntu.com/oval/
- Microsoft Security Update Guide / CVRF API: https://api.msrc.microsoft.com/cvrf/v3.0/updates

## Safety and limitations

- Read-only; never installs or removes patches.
- Does not run package metadata refresh automatically.
- API errors are reported, not treated as compliant.
- Distro-specific backports can make upstream version comparisons inaccurate; this tool intentionally avoids simplistic CVE version comparisons.
- Windows `Get-HotFix` does not represent every update class (for example, feature/servicing-stack/update history nuances); OS build and update applicability need more detailed Windows Update integration.

## Planned enhancements

- Full vendor advisory correlation with package source/version and fixed-version metadata.
- Windows Update/OS-build applicability correlation and KB supersedence.
- Multi-host inventory via SSH/WinRM with CSV host lists.
- Compliance policy profiles, severity filters, HTML reports, and scheduled runs.

## License

Use the repository's root license, if present.
