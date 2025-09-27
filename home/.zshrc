if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi
export PATH="/opt/nvim/bin:$PATH"
export PATH="$HOME/.local/share/JetBrains/Toolbox/apps:$PATH"
export ZSH="$HOME/.oh-my-zsh"
export FZF_DEFAULT_COMMAND='find . -type f'

ZSH_THEME="powerlevel10k/powerlevel10k"
ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )


plugins=(
	sudo copypath copybuffer zsh-autosuggestions 
	zsh-syntax-highlighting aliases web-search dirhistory
	fancy-ctrl-z
) 

source $ZSH/oh-my-zsh.sh
source $HOME/.gh-completion.zsh


alias zshconfig="nano ~/.zshrc"
alias vimconfig="nano ~/.config/nvim/init.vim"
alias cpath="copypath"
alias cfile="clipcopy $1"
alias ls='lsd'
alias vim='nvim'

alias ghs="gh copilot suggest"
alias ghe="gh copilot explain"
#---------------------------------------------------------------------------------
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh


source ~/.gh-completion.zsh

fzf_cd() {
    local dir
    dir=$(find . -type d | fzf) && cd "$dir"
    ls
}
zle -N fzf_cd
bindkey '^q' fzf_cd

fzf_file() {
    local file
    file=$(find . -type f | fzf)
    if [[ -n $file ]]; then
        vim "$file" < /dev/tty
    fi
}
zle -N fzf_file
bindkey '^w' fzf_file


fzf_cp() {
    local file
    file=$(find . -type f | fzf)
    if [[ -n $file ]]; then
        cfile "$file" < /dev/tty
    fi
}
zle -N fzf_cp
bindkey '^a' fzf_cp

alias gacp='gitAddCommitPush'

function gitAddCommitPush() {
    git add .
    commitMessage=$1
    git commit -m "$commitMessage"
    git push
}


