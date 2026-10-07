# Supplemental GNOME smoke reproduction

These scripts explain the independent fixture observations attached to the scaling and punctuation drafts. They are supplemental diagnostics, not the canonical desktop harness or cross-platform certification.

Use a native GNOME/Wayland desktop with the Cua WinRects helper and an existing portal/libei input grant. Build the selected candidate with `cargo build --locked -p cua-driver --features portal-input`. Dependencies: Python with Pillow for the controller, and `/usr/bin/python3` with GTK3/PyGObject for the repository fixture.

```sh
python3 probe.py /path/to/source-built/cua-driver /path/to/cua-checkout scaling
python3 probe.py /path/to/source-built/cua-driver /path/to/cua-checkout punctuation
```

The controller starts the repository GTK3 fixture with a magenta Increment marker and an independent journal, plus a temporary-socket driver using temporary XDG configuration directories. It enables the existing native-Wayland opt-in. Scaling uses the desktop PNG marker to choose a point and observes the counter, PNG sizes, crop bounds, and marker content. Punctuation sends three foreground shortcuts to the exact fixture pid/window id and observes Ctrl-held key events. Both processes close when the probe completes.

Raw PNGs, tool output, and logs stay in a private temporary directory. The published observations contain only fixture state, numeric geometry, candidate identities, and outcome summaries. The native before punctuation record used 0.28.1; the patched after record used the stated 0.34.0 source candidate. Current-main mapping failure is independently covered by the regression and its original-mapping mutation.

The scripts were published with only the fixture-path lookup made relative to this directory; the tested driver candidates and observation logic are unchanged.
