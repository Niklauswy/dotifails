vim.g.base46_cache = vim.fn.stdpath "data" .. "/base46/"
vim.g.mapleader = " "
vim.env.PATH = vim.fn.stdpath "data"
  .. "/tools/bin:"
  .. vim.fn.stdpath "data"
  .. "/mason/bin:"
  .. vim.env.PATH

-- bootstrap lazy and all plugins
local lazypath = vim.fn.stdpath "data" .. "/lazy/lazy.nvim"

if not vim.uv.fs_stat(lazypath) then
  local repo = "https://github.com/folke/lazy.nvim.git"
  vim.fn.system { "git", "clone", "--filter=blob:none", repo, lazypath }
  local lock = vim.json.decode(table.concat(vim.fn.readfile(vim.fn.stdpath "config" .. "/lazy-lock.json"), "\n"))
  vim.fn.system { "git", "-C", lazypath, "checkout", "--detach", lock["lazy.nvim"].commit }
end

vim.opt.rtp:prepend(lazypath)

local lazy_config = require "configs.lazy"

-- load plugins
require("lazy").setup({
  {
    "NvChad/NvChad",
    lazy = false,
    branch = "v2.5",
    pin = true,
    import = "nvchad.plugins",
  },

  { import = "plugins" },
}, lazy_config)

-- load theme
for _, file in ipairs { "defaults", "statusline" } do
  if vim.uv.fs_stat(vim.g.base46_cache .. file) then
    dofile(vim.g.base46_cache .. file)
  end
end

require "options"
require "autocmds"

vim.schedule(function()
  require "mappings"
end)
