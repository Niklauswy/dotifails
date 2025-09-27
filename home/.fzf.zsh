# Setup fzf
# ---------
if [[ ! "$PATH" == */home/klaus/.fzf/bin* ]]; then
  PATH="${PATH:+${PATH}:}/home/klaus/.fzf/bin"
fi

# Auto-completion
# ---------------
source "/home/klaus/.fzf/shell/completion.zsh"

# Key bindings
# ------------
source "/home/klaus/.fzf/shell/key-bindings.zsh"
