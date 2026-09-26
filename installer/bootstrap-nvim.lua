-- Compile NvChad's theme before its UI is loaded in a fresh home.
local data = vim.fn.stdpath "data"
vim.g.base46_cache = data .. "/base46/"
vim.opt.rtp:prepend(vim.fn.stdpath "config")
for _, path in ipairs(vim.fn.glob(data .. "/lazy/*", false, true)) do
  vim.opt.rtp:append(path)
end
require("base46").load_all_highlights()
assert(vim.uv.fs_stat(vim.g.base46_cache .. "defaults"), "Theme cache was not built")
print "NVIM_THEME_BOOTSTRAPPED"
