# OMX Intraday

This repository includes a small set of Bash terminal helpers for faster, safer day-to-day work. The helpers live in:

```bash
/home/en23/.bash_aliases
```

After changing that file, reload your shell with:

```bash
source ~/.bash_aliases
```

Or open a new terminal.

## Safer Defaults

These commands ask before overwriting existing files:

```bash
cp source.txt target.txt
mv old-name.txt new-name.txt
```

Create directories with parent folders automatically:

```bash
mkdir nested/folder/path
```

Show each `PATH` entry on its own line:

```bash
path
```

## File Listing

If `eza` is installed, these commands use nicer output with icons, Git status, and directories first:

```bash
ls
ll
tree
```

Fallbacks are provided when `eza` is not installed:

```bash
ll
la
l
```

## Search And Reading

If `bat` or `batcat` is installed, `cat` uses `bat` without paging:

```bash
cat app.py
```

If `ripgrep` is installed, `grep` is mapped to `rg`:

```bash
grep "pattern" .
```

If your system installs `fd` as `fdfind`, the helpers expose it as:

```bash
fd filename
```

## Git Shortcuts

Common Git commands have short aliases:

| Alias | Command |
| --- | --- |
| `gs` | `git status --short --branch` |
| `ga` | `git add` |
| `gc` | `git commit` |
| `gd` | `git diff` |
| `gds` | `git diff --staged` |
| `gl` | `git log --oneline --decorate --graph --all -20` |
| `gp` | `git pull --ff-only` |
| `gpf` | `git push --force-with-lease` |

Example workflow:

```bash
gs
gd
ga README.md
gc -m "Add terminal helper README"
```

## Navigation Helpers

Create a directory and move into it:

```bash
mkcd analysis/new-run
```

Move up one or more directories:

```bash
up
up 2
```

## Fuzzy Finder Helpers

These commands require `fzf`.

Jump to a directory:

```bash
fcd
```

Find a file and open it in your editor:

```bash
fopen
```

Search with `ripgrep`, pick a result, and open the file at that line:

```bash
frg "search text"
```

Pick a running process and kill it:

```bash
fkill
```

Use `fkill` carefully because it sends `kill -9` to the selected process.

## Editor Selection

The helpers set `EDITOR` automatically:

1. `nvim` if available
2. `vim` if available
3. `nano` as the fallback

Commands like `fopen` and `frg` use this editor.

## Optional Integrations

These integrations turn on only if the tools are installed:

| Tool | What it adds |
| --- | --- |
| `zoxide` | Smarter directory jumping |
| `starship` | Rich shell prompt |
| `fzf` key bindings | Keyboard shortcuts for fuzzy file/history search |
| `fzf` completion | Tab completion powered by `fzf` |

## Suggested Installs

On Ubuntu/Debian-style systems:

```bash
sudo apt update
sudo apt install eza bat ripgrep fd-find fzf zoxide
```

`starship` is usually installed separately from its official installer or package manager.

## Quick Reference

| Task | Command |
| --- | --- |
| Reload aliases | `source ~/.bash_aliases` |
| Show Git status | `gs` |
| Show recent Git history | `gl` |
| Create and enter a folder | `mkcd folder-name` |
| Go up two directories | `up 2` |
| Fuzzy-find a directory | `fcd` |
| Fuzzy-open a file | `fopen` |
| Search and open a result | `frg "text"` |
| Show readable `PATH` | `path` |

