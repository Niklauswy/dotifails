-- Run explicitly. Never installs tools automatically when an ordinary file opens.
require("lazy").install { wait = true, show = false, lockfile = true }
require("mason").setup { max_concurrent_installers = 3 }
local registry = require "mason-registry"
local refreshed, registry_ok = false, false
registry.refresh(function(ok)
  refreshed = true
  registry_ok = ok
end)
assert(
  vim.wait(90000, function()
    return refreshed
  end, 100),
  "Mason registry timed out"
)
assert(registry_ok, "Could not refresh the Mason registry")
require("lazy").restore { wait = true, show = false }
local versions = vim.json.decode(table.concat(vim.fn.readfile(vim.fn.stdpath "config" .. "/mason-lock.json"), "\n"))
local packages = vim.tbl_keys(versions)
local remaining, failed = 0, {}
for _, name in ipairs(packages) do
  if not registry.has_package(name) then
    failed[#failed + 1] = name
    print("UNKNOWN_PACKAGE " .. name)
  else
    local pkg = registry.get_package(name)
    local installed = nil
    local receipt_path = vim.fn.stdpath "data" .. "/mason/packages/" .. name .. "/mason-receipt.json"
    if vim.fn.filereadable(receipt_path) == 1 then
      local receipt = vim.json.decode(table.concat(vim.fn.readfile(receipt_path), "\n"))
      installed = receipt.source.id:match("@([^@]+)$")
    end
    if installed == versions[name] then
      print("PRESENT " .. name)
    else
      remaining = remaining + 1
      pkg:install({ version = versions[name] }, function(success)
        remaining = remaining - 1
        if not success then
          failed[#failed + 1] = name
        end
        print((success and "INSTALLED " or "FAILED ") .. name)
      end)
    end
  end
end
assert(
  vim.wait(900000, function()
    return remaining == 0
  end, 100),
  "Tool installation timed out"
)
assert(#failed == 0, "Tools failed: " .. table.concat(failed, ", "))
require("lazy").load { plugins = { "nvim-treesitter" } }
local missing = {}
for _, lang in ipairs {
  "javascript",
  "typescript",
  "tsx",
  "python",
  "c",
  "cpp",
  "lua",
  "luadoc",
  "vim",
  "vimdoc",
  "query",
  "json",
  "jsonc",
  "html",
  "css",
  "bash",
  "markdown",
  "markdown_inline",
  "yaml",
  "toml",
  "regex",
} do
  if #vim.api.nvim_get_runtime_file("parser/" .. lang .. ".so", false) == 0 then
    missing[#missing + 1] = lang
  end
end
if #missing > 0 then
  vim.cmd("TSInstallSync " .. table.concat(missing, " "))
end
require("base46").load_all_highlights()
print "NVIM_TOOLCHAIN_INSTALLED"
