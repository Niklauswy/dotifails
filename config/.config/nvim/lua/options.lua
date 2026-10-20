require "nvchad.options"
local o = vim.opt
o.number = true
o.relativenumber = true
o.cursorline = true
o.cursorlineopt = "number,line"
o.signcolumn = "yes"
o.scrolloff = 6
o.sidescrolloff = 6
o.wrap = false
o.splitright = true
o.splitbelow = true
o.splitkeep = "screen"
o.ignorecase = true
o.smartcase = true
o.inccommand = "split"
o.updatetime = 250
o.timeoutlen = 400
o.undofile = true
o.undolevels = 10000
o.confirm = true
o.completeopt = { "menu", "menuone", "noselect" }
o.pumheight = 12
o.winborder = "rounded"
o.list = true
o.listchars = { tab = "  ", trail = "·", nbsp = "␣" }
o.fillchars:append { eob = " ", diff = "╱" }
o.sessionoptions = { "buffers", "curdir", "tabpages", "winsize", "help", "folds" }
o.exrc = false
vim.g.editorconfig = true
vim.g.disable_autoformat = false
