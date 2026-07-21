# Mod Update Checker for The Sims 4

Mod Update Checker, or **MUC**, is a transparent update-notification framework for script and tuning mods made for **The Sims 4**.

MUC checks one public central registry, compares its contents with the versions declared by installed compatible mods, and informs the player when updates are available.

> **Development status**
>
> Mod Update Checker is currently under active development.
> The public registry connection is functional, while cryptographic registry verification is still being implemented. This status will be updated before the first public release.

## What MUC does

MUC is designed to:

* perform one registry request instead of one request per installed mod;
* compare versions locally in the game;
* create a readable update report;
* display one summary notification when updates are available;
* direct players to the official update pages declared by each mod creator.

MUC only retrieves public version information. It does **not** download, install, import, or execute mod files.

```text
Compatible installed mods
          +
One public registry document
          ↓
Local version comparisons
          ↓
One update report
          ↓
One optional summary notification
```

## Project links

| Resource               | Link                                                                                              |
| ---------------------- | ------------------------------------------------------------------------------------------------- |
| Mod source code        | [Mod-Update-Checker on GitHub](https://github.com/Demeterio/Mod-Update-Checker)                   |
| Registry repository    | [Mod-Update-Checker_registry on GitHub](https://github.com/Demeterio/Mod-Update-Checker_registry) |
| Live registry document | [View registry-v1.json](http://muc-registry.demeterio.cc/generated/registry-v1.json)              |
| Registry pull requests | [View proposed registry changes](https://github.com/Demeterio/Mod-Update-Checker_registry/pulls)  |
| Creator website        | [Demeterio on Tumblr](https://demeterio.tumblr.com/)                                              |

## Network and privacy transparency

MUC makes one fixed HTTP request to:

```text
http://muc-registry.demeterio.cc/generated/registry-v1.json
```

The request is made only after the player has allowed registry checks.

### Information sent by the request

As with any standard web request, the hosting service may receive basic technical connection information such as:

* the player’s public IP address;
* the request date and time;
* the fixed registry path;
* the MUC user agent.

The configured user agent is:

```text
Demeterio-Mod-Update-Checker
```

### Information MUC does not send

MUC does not send:

* the player’s EA account name;
* the player’s local computer username;
* the contents of the Mods folder;
* the list of installed mods;
* installed mod versions;
* save-game information;
* gameplay information;
* hardware identifiers;
* advertising identifiers;
* analytics or telemetry;
* cookies or authentication credentials.

All version comparisons are performed locally after the single registry document has been retrieved.

MUC does not attempt to bypass firewalls, privacy or security tools such as ModGuard or Privacy Protector, network protection mods, or operating-system security settings. If a request is blocked, the update check simply stops and no additional data is retrieved.

## Why the registry uses HTTP instead of HTTPS

The Python runtime included with The Sims 4 does not provide the native `_ssl` extension required by Python’s `ssl` module.

Because of that limitation, a script mod cannot establish a normal Python HTTPS connection using the game’s bundled runtime.

The registry is therefore served through a dedicated custom domain over plain HTTP:

```text
muc-registry.demeterio.cc
```

This is a technical compatibility decision, not an attempt to hide the connection.

HTTP does not provide transport encryption or built-in response authentication. The registry contains only public mod-version metadata, but transport integrity still matters.

For that reason, MUC is being designed to verify a cryptographic signature before using a retrieved registry document.

## Registry authenticity and public verification

The completed signing system will publish three separate elements:

| Element                     | Purpose                                                    | Publication status |
| --------------------------- | ---------------------------------------------------------- | ------------------ |
| Public key                  | Allows MUC and third parties to verify registry signatures | Planned            |
| Public-key fingerprint      | Allows the exact public key to be identified easily        | Planned            |
| Detached registry signature | Authenticates the current registry document                | Planned            |

The planned public files are:

```text
security/muc-registry-public-key.pem
security/muc-registry-public-key.sha256
generated/registry-v1.json.sig
```

The private signing key will never be included in the mod, the public registry, or either GitHub repository.

Once signing is enabled, MUC will reject a registry when:

* its signature is missing;
* its signature is invalid;
* its contents were modified after signing;
* its signature does not match the public key included with MUC;
* its schema or required fields are invalid.

> Until signature verification is implemented, the HTTP registry transport must not be described as tamper-resistant.

## Additional network restrictions

The MUC network client accepts only the configured registry request.

It rejects:

* HTTPS URLs;
* alternate domains;
* alternate ports;
* credentials embedded in URLs;
* query strings;
* URL fragments;
* alternate registry paths;
* redirects;
* compressed responses;
* unsupported transfer encodings;
* oversized responses;
* responses that are not JSON.

The registry cannot provide arbitrary download links. Player-facing update pages remain defined locally by the compatible mod’s integration package.

## Installation

The public release will contain the following files, where X is the release version number:

```text
Demeterio_ModUpdateChecker_vX.ts4script
Demeterio_ModUpdateChecker_vX.package
```

Place both files in:

```text
Documents/Electronic Arts/The Sims 4/Mods
```

They may be placed directly in the Mods folder or inside one subfolder.

Make sure that **Script Mods Allowed** and **Enable Custom Content and Mods** are enabled in the game options.

When updating MUC, remove the previous version before installing the new files.

## First launch and consent

On first launch, MUC asks whether registry checks are allowed.

The available choices are:

* **Allow registry checks**: enables registry requests and automatic checks;
* **Ask again in 7 days**: pauses registry checks and asks again after seven days.

Notification preferences are managed separately:

* **Enable summaries**: displays a summary when updates are available;
* **Mute for 7 days**: continues checking and writing reports without displaying summaries.

Preferences can be reopened with:

```text
demeterio.muc_settings
```

## Commands

```text
demeterio.muc_version
demeterio.muc_getlist
demeterio.muc_check
demeterio.muc_settings
demeterio.muc_alerton *
demeterio.muc_alertoff *
demeterio.muc_alerton creator.mod_name.0123456789ABCDEF
demeterio.muc_alertoff creator.mod_name.0123456789ABCDEF
demeterio.muc_openreport
demeterio.muc_openlogfolder
demeterio.muc_openlog
```

## Reports and logs

The player-facing update report is overwritten after every completed check:

```text
demeterio_modupdatechecker_updates.txt
```

The technical log is stored separately:

```text
demeterio_modupdatechecker_log.txt
```

MUC also maintains local settings and cache files. These files remain on the player’s computer and are not uploaded.

## Support for mod creators

A compatible mod can provide a small optional integration package containing a MUC declaration.

The declaration identifies:

* the mod ID;
* the displayed mod name;
* the installed version;
* the release channel;
* the official player-facing update page.

The custom tuning class is:

```text
mod_update_checker.tuning.ModUpdateCheckerDeclaration
```

Flat tuning examples and the complete central-registry schema are available in the Modder ZIP archive.

## Add or update a mod in the registry

Registry changes are submitted through GitHub Pull Requests.

1. Read the [contribution guide](https://github.com/Demeterio/Mod-Update-Checker_registry/blob/main/CONTRIBUTING.md).
2. Copy the [mod entry template](https://github.com/Demeterio/Mod-Update-Checker_registry/blob/main/templates/mod-entry.template.json).
3. Validate the entry against the [mod entry schema](https://github.com/Demeterio/Mod-Update-Checker_registry/blob/main/schemas/mod-entry.schema.json).
4. Review the [example entries](https://github.com/Demeterio/Mod-Update-Checker_registry/tree/main/examples).
5. [Fork the registry repository](https://github.com/Demeterio/Mod-Update-Checker_registry/fork).
6. Submit the change through a [Pull Request](https://github.com/Demeterio/Mod-Update-Checker_registry/compare).

Existing proposals can be reviewed on the [Pull Requests page](https://github.com/Demeterio/Mod-Update-Checker_registry/pulls).

All submissions must pass automated validation before they can be merged into the generated registry.

## Registry document

The generated registry uses schema version 1:

```json
{
  "schema": 1,
  "generated_at": "2026-07-20T12:05:00Z",
  "entries": [
    {
      "mod_id": "creator.mod_name.0123456789ABCDEF",
      "release_channel": "stable",
      "version": "1.1.0",
      "release_tag": "v1.1.0",
      "checked_at": "2026-07-20T12:00:00Z"
    }
  ]
}
```

The registry contains public version metadata only. It does not contain player information.

## Development

The project targets:

* The Sims 4 Python 3.7 runtime;
* Python 3.7-compatible syntax;
* Sims 4 Studio;
* Sims 4 Toolkit package generation.

The source code is available in the [main GitHub repository](https://github.com/Demeterio/Mod-Update-Checker).

## Disclaimer

Mod Update Checker is an unofficial fan-made project.

It is not affiliated with, authorized by, sponsored by, or endorsed by Electronic Arts or Maxis.

The Sims and all related names and trademarks belong to their respective owners.

## Copyright

Copyright © Demeterio.

Do not redistribute, copy, modify, or repackage this project without permission.
