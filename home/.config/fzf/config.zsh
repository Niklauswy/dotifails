# Búsqueda rápida; los nombres de archivos y consultas se pasan como argumentos.
export FZF_DEFAULT_OPTS="--height=60% --layout=reverse --border=rounded --info=inline --color=fg:#c0caf5,bg:#1a1b26,hl:#7aa2f7,fg+:#c0caf5,bg+:#292e42,hl+:#7dcfff --color=border:#3b4261,prompt:#7dcfff,pointer:#f7768e --preview-window=right:50% --bind=ctrl-/:toggle-preview"
export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git'
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
export FZF_ALT_C_COMMAND='fd --type d --hidden --exclude .git'
export FZF_CTRL_T_OPTS="--preview 'bat --style=numbers --color=always --line-range :500 -- {}'"
export FZF_ALT_C_OPTS="--preview 'eza --tree --level=2 --color=always --icons=always -- {}'"

fv() {
    local selected
    IFS= read -r -d '' selected < <(fd -0 --type f --hidden --exclude .git | fzf --read0 --print0 --preview 'bat --style=numbers --color=always --line-range :500 -- {}') || return
    nvim -- "$selected" </dev/tty
}

fcd() {
    local selected
    IFS= read -r -d '' selected < <(fd -0 --type d --hidden --exclude .git | fzf --read0 --print0 --preview 'eza --tree --level=2 --color=always --icons=always -- {}') || return
    cd -- "$selected"
}

fif() {
    (( $# )) || { print 'Uso: fif texto que quieres buscar'; return 1; }
    local selected
    local -x ORBIT_FZF_QUERY="$*"
    IFS= read -r -d '' selected < <(rg -0 --files-with-matches --no-messages -- "$ORBIT_FZF_QUERY" | fzf --read0 --print0 --preview 'rg --color=always --context=8 -- "$ORBIT_FZF_QUERY" {}') || return
    nvim -- "$selected" </dev/tty
}

fzf_git_files() {
    local selected
    IFS= read -r -d '' selected < <(git ls-files -z | fzf --read0 --print0 --header='Archivos del repositorio' --preview 'bat --style=numbers --color=always --line-range :500 -- {}') || return
    nvim -- "$selected" </dev/tty
    zle reset-prompt
}

fzf_files_widget() { fv; zle reset-prompt; }
zle -N fzf_git_files
zle -N fzf_files_widget
bindkey '^g' fzf_git_files
bindkey '^e' fzf_files_widget
alias ff=fv
fkill() { orbit processes; }
