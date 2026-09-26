export PATH="$HOME/.local/bin:$PATH"
export EDITOR=nvim VISUAL=nvim
export ZSH="${XDG_DATA_HOME:-$HOME/.local/share}/dotifails/tools/ohmyzsh"
export ZSH_CUSTOM="${XDG_DATA_HOME:-$HOME/.local/share}/dotifails/zsh-custom"
ZSH_THEME=""
plugins=(sudo copypath copybuffer zsh-autosuggestions zsh-syntax-highlighting aliases dirhistory fancy-ctrl-z git)
[[ -f "$ZSH/oh-my-zsh.sh" ]] && source "$ZSH/oh-my-zsh.sh"
alias vim=nvim cat=batcat
alias ls='eza --color=always --icons=always'
alias ll='eza -la --color=always --icons=always --git --header'
alias lt='eza --tree --color=always --icons=always'
alias la='eza -A --color=always --icons=always'
alias tree='eza --tree --git --color=always --icons=always'
[[ -f /usr/share/doc/fzf/examples/completion.zsh ]] && source /usr/share/doc/fzf/examples/completion.zsh
[[ -f /usr/share/doc/fzf/examples/key-bindings.zsh ]] && source /usr/share/doc/fzf/examples/key-bindings.zsh
[[ -f "${XDG_CONFIG_HOME:-$HOME/.config}/fzf/config.zsh" ]] && source "${XDG_CONFIG_HOME:-$HOME/.config}/fzf/config.zsh"
export NVM_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/dotifails/tools/nvm"
nvm() { unfunction nvm; source "$NVM_DIR/nvm.sh"; nvm "$@"; }
command -v starship >/dev/null && eval "$(starship init zsh)"
[[ -f "${XDG_CONFIG_HOME:-$HOME/.config}/dotifails/local.zsh" ]] && source "${XDG_CONFIG_HOME:-$HOME/.config}/dotifails/local.zsh"
