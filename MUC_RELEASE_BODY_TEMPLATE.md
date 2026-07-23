# Mod Update Checker

> [!IMPORTANT]
> Download only one of the two official MUC ZIP archives attached to this Release.
>
> Do **not** download GitHub's automatic **Source code (zip)** or **Source code (tar.gz)** archives.
> They are repository snapshots and are not ready-to-install versions of the mod.

## Changelog

### Added

- Add changes here.

### Changed

- Add changes here.

### Fixed

- Add changes here.

### Removed

- Add changes here.

Delete any unused changelog section before publishing the Release.

---

## Which ZIP should I download?

All versioned filenames end with `vX`, where `X` represents the version included in this Release.

### Players

Download:

`Demeterio_ModUpdateChecker_PLAYER_vX.zip`

Use this archive when you only want to install and use Mod Update Checker in The Sims 4.

```text
Demeterio_ModUpdateChecker_PLAYER_vX.zip
├─ Demeterio_ModUpdateChecker_Script_vX.ts4script
├─ Demeterio_ModUpdateChecker_Generic_vX.package
├─ Demeterio_ModUpdateChecker_Installation_vX.txt
└─ Demeterio_ModUpdateChecker_Compatibility_vX.txt
```

The installation method and current compatibility information are included inside the ZIP.

### Mod creators

Download:

`Demeterio_ModUpdateChecker_MODDER_vX.zip`

Use this archive when you want to add MUC support to your own mod or test a MUC declaration package.

```text
Demeterio_ModUpdateChecker_MODDER_vX.zip
├─ Demeterio_ModUpdateChecker_Script_vX.ts4script
├─ Demeterio_ModUpdateChecker_Generic_vX.package
├─ Demeterio_ModUpdateChecker_Installation_vX.txt
├─ Demeterio_ModUpdateChecker_Compatibility_vX.txt
├─ Documentation/
│  └─ Demeterio_ModUpdateChecker_Modder_Guide_vX.pdf
└─ Templates/
   └─ ModderName_ModName_ModUpdateChecker_vX.package
```

The MODDER ZIP contains the same runtime files as the PLAYER ZIP, plus the complete modder guide and the declaration package template.

Do not install or distribute the unchanged template. Copy it into your own project, rename it, replace every placeholder, and follow the Modder Guide.

---

## Other official download pages

- **Mod The Sims:** MOD_THE_SIMS_URL
- **SimFileShare:** https://simfileshare.net/folder/273522/

---

## Source code for this Release

To inspect the Python source for this exact version:

1. Open the Mod Update Checker GitHub repository.
2. Use the branch/tag selector near the top of the file list.
3. Select the same tag as this Release.
4. Open the `/src` folder.

The direct URL follows this format:

```text
https://github.com/Demeterio/Mod-Update-Checker/tree/<RELEASE_TAG>/src
```

Replace `<RELEASE_TAG>` with the exact tag shown at the top of this Release, for example `v1.0.1`.

---

## Problems and bug reports

For installation problems, compatibility reports, unexpected behavior, or confirmed bugs, use either:

- **GitHub Issues:** https://github.com/Demeterio/Mod-Update-Checker/issues
- the official **Mod The Sims page** linked above.

When reporting a problem, include the MUC version, The Sims 4 version, technical log, update report, and reproduction steps when available.
