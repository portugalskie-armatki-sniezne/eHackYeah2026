#!/usr/bin/env bash

set -eu

command_exists() {
    command -v "$1" &>/dev/null
}

activate_mise_on_shell_startup() {
    echo "Activating mise on shell startup..."
    case "${SHELL:-}" in
    */zsh)
        zshrc="${ZDOTDIR:-$HOME}/.zshrc"
        line_to_add='eval "$(~/.local/bin/mise activate zsh)"'
        grep -Fxq "$line_to_add" "$zshrc" || printf '\n%s\n' "$line_to_add" >>"$zshrc"
        ;;
    */bash)
        line_to_add='eval "$(~/.local/bin/mise activate bash)"'
        grep -Fxq "$line_to_add" ~/.bashrc || printf '\n%s\n' "$line_to_add" >>~/.bashrc
        ;;
    */fish)
        line_to_add='~/.local/bin/mise activate fish | source'
        grep -Fxq "$line_to_add" ~/.config/fish/config.fish || printf '\n%s\n' "$line_to_add" >>~/.config/fish/config.fish
        ;;
    *)
        echo "Unsupported shell configuration - activate mise manually: https://mise.jdx.dev/getting-started.html"
        ;;
    esac
}

main() {
    cd "$(dirname "$0")"

    needs_shell_restart=false
    if ! command_exists mise; then
        echo "Mise isn't installed. Installing mise..."
        curl https://mise.run | sh
        export PATH="$HOME/.local/bin:$PATH"

        activate_mise_on_shell_startup
        needs_shell_restart=true
    fi

    mise trust --yes
    mise install

    echo "Running setup task..."
    mise exec -- task setup

    if $needs_shell_restart; then
        echo "Please restart your shell!"
    fi
}

main
