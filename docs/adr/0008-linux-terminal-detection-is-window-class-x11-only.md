# Linux terminal detection is window-class matching, X11 only

On Linux, `Ctrl+V` is not paste in a terminal — the terminal echoes a literal `^V`
and the text never arrives. The clipboard injection path must therefore know what
kind of window it is pasting into *before* choosing the chord. Decision: on
Linux, the focused window is queried for its `WM_CLASS` and matched against a
known-terminal allowlist; a match pastes with `Ctrl+Shift+V`, everything else
pastes with `Ctrl+V`. Detection is X11-only and runs at injection time. This is
accepted intent, not yet implemented: `ClipboardStrategy.type`
(`input_strategies.py:59-66`) sends `Ctrl+V` unconditionally on Linux today.

**Detection is a query, not a tracker.** The window is read at the moment of
injection — `_NET_ACTIVE_WINDOW` on the root window, then the `WM_CLASS` of that
window, in-process via python-xlib (microseconds, no subprocess). No focus-change
tracking, no cache keyed on window id: a cached classification goes stale across
workspace switches and is one more thing to invalidate, and the query is cheap
enough that caching buys nothing.

**Unknown windows are assumed non-terminal.** The two failure modes are not
symmetric: a false negative (an unknown terminal gets `Ctrl+V`) inserts visible
garbage that the user notices immediately and can fix by extending the list; a
false positive (an unknown editor gets `Ctrl+Shift+V`) makes text silently
missing — a failure nobody sees and nobody can diagnose. The allowlist covers the
common terminal emulators that bind `Ctrl+Shift+V` by default (gnome-terminal,
konsole, kitty, alacritty, foot, wezterm, …); the list is code-owned and
user-extendable through a setting in `system_input`, alongside `strategy`.

**The same chord choice serves Ghost and Final.** The Ghost path is hard-coded to
clipboard re-typing (`input_manager.py`), so terminal-aware chord selection lives
in the one place both paths paste through — otherwise Ghost typing would garble
terminals that the Final pass then types into correctly, or vice versa.

## Consequences

**Wayland is out of scope, deliberately.** pynput cannot synthesize keystrokes on
Wayland without an elevated uinput setup; if the paste chord cannot be sent at
all, choosing the right chord is moot. Compositor-specific focus queries
(`swaymsg -t get_tree`, `hyprctl -j activewindow`, `kdotool`) are not maintained
for this. If Wayland injection ever becomes real, this ADR is the one to reopen.

**Integrated terminals are invisible, and that is accepted.** Window-level
detection sees windows, not widgets: VS Code (`code`) and JetBrains IDEs host
integrated terminals whose focus is indistinguishable from editor focus at the
window level. AT-SPI2 could read the focused widget's terminal role, but its
accessibility bridges are off by default in Electron and Qt — rejected. The
escape hatch for IDE-terminal users is a manual paste-shortcut override in
`system_input`.

**xterm binds paste elsewhere by default.** Classic xterm's default bindings are
Shift+Insert and middle-click (PRIMARY), not `Ctrl+Shift+V` — correct detection
still finds no paste chord there. xterm users get the manual override; the
allowlist is not contorted around xterm.

**Rejected alternatives:** always `Ctrl+Shift+V` on Linux (silent missing text in
every editor — the failure mode nobody notices); config-only, no detection (zero
failure modes, but every terminal user must first discover the setting by being
garbled — detection plus a manual override ships both); title heuristics
(`WM_NAME` matching shell names and `user@host` — flakier than class); PRIMARY
selection plus `Shift+Insert` (covers xterm and avoids the clipboard clobber, but
does nothing in browsers and editors, so it still needs the same detection gate
and manages a second selection — revisit only if clipboard save/restore proves
unworkable); AT-SPI2 (see above).
